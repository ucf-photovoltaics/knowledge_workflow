"""Offline access-boundary and revocation tests, including real ASGI WebSockets."""
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlencode

import pytest

from dpv_dashboard import access


PASSWORD = "synthetic-test-password-only"


@pytest.fixture(scope="module")
def encoded():
    return access.password_hash(PASSWORD)


@pytest.fixture
def setup(tmp_path, encoded):
    root = tmp_path / "shared"
    (root / "study").mkdir(parents=True)
    (root / "paper").mkdir()
    (root / "study" / "ontology.ttl").write_text("approved research")
    (root / "study" / "unlisted.txt").write_text("not shared")
    (root / "paper" / "release.ttl").write_text("published research")
    config = {"schema_version": 1, "session_key": "test-only-signing-material-never-deploy-this-value",
              "credentials": {
                  "team": {"role": "team", "password_hash": encoded, "version": "1"},
                  "alice": {"role": "collaborator", "password_hash": encoded, "version": "1", "shares": ["study"]},
                  "paper": {"role": "paper", "password_hash": encoded, "version": "1", "shares": ["release"]}},
              "shares": {"study": {"root": "study", "files": ["ontology.ttl"]},
                         "release": {"root": "paper", "files": ["release.ttl"]}}}
    path = tmp_path / "access.json"
    path.write_text(json.dumps(config))
    calls = []
    async def app(scope, receive, send):
        calls.append(scope["path"])
        if scope["type"] == "websocket":
            await receive()
            await send({"type": "websocket.accept"})
            while (await receive())["type"] != "websocket.disconnect":
                await send({"type": "websocket.send", "text": "team only"})
        else:
            await access.Response("team dashboard")(scope, receive, send)
    store = access.ConfigStore(path)
    gate = access.AccessGate(app, store, share_root=root, secure=False)
    return gate, config, path, root, calls


async def http_async(app, path="/", method="GET", body=b"", cookies="", headers=None):
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"}, "http_version": "1.1",
             "scheme": "http", "method": method, "path": path, "raw_path": path.encode(), "root_path": "",
             "query_string": b"", "headers": [(b"host", b"test.local"), (b"cookie", cookies.encode()),
                 (b"content-type", b"application/x-www-form-urlencoded"), *(headers or [])],
             "client": ("127.0.0.1", 1234), "server": ("test.local", 80)}
    events = asyncio.Queue()
    events.put_nowait({"type": "http.request", "body": body, "more_body": False})
    sent = []
    async def send(event):
        sent.append(event)
    await app(scope, events.get, send)
    status = sent[0]["status"]
    response_headers = sent[0]["headers"]
    content = b"".join(e.get("body", b"") for e in sent[1:])
    return status, response_headers, content


def http(*args, **kwargs):
    return asyncio.run(http_async(*args, **kwargs))


def token(config, identifier):
    return access.sign({"id": identifier, "revision": access.revision(config["credentials"][identifier]),
                        "exp": int(time.time()) + 3600}, config)


def cookie(config, identifier):
    return access.COOKIE + "=" + token(config, identifier)


def refresh(gate, config, path):
    path.write_text(json.dumps(config))
    gate.store._checked = float("-inf")


@pytest.mark.parametrize("path", ["/", "/documentation/library.html", "/research-media/token", "/session/123/download/file", "/dashboard.js"])
def test_anonymous_cannot_reach_any_shiny_route(setup, path):
    gate, _, _, _, calls = setup
    assert http(gate, path)[0] == 303
    assert not calls


def test_login_verifies_password_and_uses_secure_cookie(setup):
    gate, _, _, _, _ = setup
    gate.secure = True
    status, headers, body = http(gate, "/access/login")
    csrf = re.search(b"name=csrf value='([^']+)'", body)[1].decode()
    payload = urlencode({"identifier": "alice", "password": PASSWORD, "csrf": csrf}).encode()
    status, headers, _ = http(gate, "/access/login", method="POST", body=payload, cookies="dpv_login=" + csrf)
    assert status == 303
    cookies = [value.decode() for key, value in headers if key == b"set-cookie"]
    assert any("HttpOnly" in c and "Secure" in c and "SameSite=strict" in c and "dpv_access=" in c for c in cookies)
    assert PASSWORD.encode() not in body


def test_csrf_and_cross_origin_login_are_denied(setup):
    gate = setup[0]
    assert http(gate, "/access/login", method="POST", body=urlencode({"identifier": "team", "password": PASSWORD}).encode())[0] == 400
    assert http(gate, "/access/login", method="POST", headers=[(b"origin", b"https://other.example")])[0] == 400


def test_incorrect_password_is_rejected_and_attempts_are_throttled(setup):
    gate = setup[0]
    for index in range(11):
        _, _, body = http(gate, "/access/login")
        csrf = re.search(b"name=csrf value='([^']+)'", body)[1].decode()
        status, _, _ = http(gate, "/access/login", method="POST", cookies="dpv_login=" + csrf,
                            body=urlencode({"identifier": "alice", "password": "incorrect", "csrf": csrf}).encode())
        assert status == (401 if index < 10 else 429)


def test_team_reaches_shiny_but_collaborator_and_paper_do_not(setup):
    gate, config, _, _, calls = setup
    assert http(gate, cookies=cookie(config, "team"))[2] == b"team dashboard"
    calls.clear()
    for user in ("alice", "paper"):
        for path in ("/documentation/library.html", "/research-media/token", "/session/id/download/file", "/dashboard.js"):
            assert http(gate, path, cookies=cookie(config, user))[0] == 404
    assert not calls


def test_shares_are_scoped_read_only_and_never_include_unlisted_files(setup):
    gate, config, _, _, _ = setup
    auth = cookie(config, "alice")
    status, _, body = http(gate, "/shared", cookies=auth)
    assert status == 200 and b"ontology.ttl" in body and b"release.ttl" not in body and b"unlisted" not in body
    assert http(gate, "/shared/study/0", cookies=auth)[2] == b"approved research"
    assert http(gate, "/shared/release/0", cookies=auth)[0] == 404
    assert http(gate, "/shared/study/1", cookies=auth)[0] == 404
    assert http(gate, "/shared/study/0", method="POST", cookies=auth)[0] == 405


def test_rotation_and_revocation_invalidate_only_affected_credentials(setup):
    gate, config, path, _, _ = setup
    alice, team = cookie(config, "alice"), cookie(config, "team")
    config["credentials"]["alice"]["enabled"] = False
    refresh(gate, config, path)
    assert http(gate, "/shared", cookies=alice)[0] == 303
    assert http(gate, cookies=team)[0] == 200
    config["credentials"]["alice"]["enabled"] = True
    config["credentials"]["alice"]["version"] = "2"
    refresh(gate, config, path)
    assert http(gate, "/shared", cookies=alice)[0] == 303


def test_configuration_is_shared_across_instances(setup):
    gate, config, path, root, _ = setup
    other = access.AccessGate(None, access.ConfigStore(path), share_root=root, secure=False)
    auth = cookie(config, "alice")
    assert http(other, "/shared", cookies=auth)[0] == 200
    config["credentials"]["alice"]["shares"] = ["release"]
    refresh(gate, config, path)
    other.store._checked = float("-inf")
    assert http(other, "/shared", cookies=auth)[0] == 303


def test_config_failure_fails_closed(setup):
    gate, config, path, _, calls = setup
    path.write_text("invalid json")
    gate.store._checked = float("-inf")
    assert http(gate, cookies=cookie(config, "team"))[0] == 503
    assert not calls


@pytest.mark.parametrize("value", ["../escape", "/absolute", "C:/absolute", "private/file", ".env", "a/../../escape", "a\\file", "key.pem"])
def test_invalid_file_scopes_rejected(value):
    with pytest.raises(ValueError):
        access.relative(value)


def test_symlink_escape_is_not_shared(setup, tmp_path):
    gate, config, _, root, _ = setup
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    link = root / "study" / "alias.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    assert gate.files({"root": "study", "files": ["alias.txt"]}) == []


def test_whole_bucket_view_excludes_credential_files(setup):
    gate, _, _, root, _ = setup
    (root / "paper" / ".env").write_text("do not share")
    (root / "paper" / "private").mkdir()
    (root / "paper" / "private" / "data.txt").write_text("do not share")
    assert [name for name, _ in gate.files({"root": "paper", "whole_root": True})] == ["release.ttl"]


def test_html_downloads_are_attachments_and_previews_are_escaped(setup):
    gate, config, path, root, _ = setup
    (root / "paper" / "release.ttl").write_text("<script>alert('example')</script>")
    status, headers, body = http(gate, "/shared/release/0", cookies=cookie(config, "paper"))
    assert (b"content-type", b"application/octet-stream") in headers
    assert any(k == b"content-disposition" and b"attachment" in v for k, v in headers)
    _, _, body = http(gate, "/shared/release/0/preview", cookies=cookie(config, "paper"))
    assert b"<script>" not in body and b"&lt;script&gt;" in body


def test_publication_service_rejects_team_and_other_routes(setup):
    _, config, path, root, _ = setup
    gate = access.AccessGate(None, access.ConfigStore(path), mode="publication", share_root=root, secure=False)
    assert http(gate, "/shared", cookies=cookie(config, "team"))[0] == 303
    assert http(gate, "/shared", cookies=cookie(config, "alice"))[0] == 303
    assert http(gate, "/shared/release/0", cookies=cookie(config, "paper"))[0] == 200
    assert http(gate, "/documentation/library.html", cookies=cookie(config, "paper"))[0] == 404


def test_tampered_and_expired_sessions_rejected(setup):
    gate, config, _, _, _ = setup
    assert http(gate, cookies=access.COOKIE + "=" + token(config, "team") + "x")[0] == 303
    expired = access.sign({"id": "team", "revision": access.revision(config["credentials"]["team"]), "exp": 1}, config)
    assert http(gate, cookies=access.COOKIE + "=" + expired)[0] == 303


def test_logout_requires_post_and_csrf(setup):
    gate, config, _, _, _ = setup
    auth = cookie(config, "team")
    assert http(gate, "/access/logout", method="POST", cookies=auth, body=b"csrf=invalid")[0] == 400
    assert http(gate, "/access/logout", cookies=auth)[0] == 200
    status, headers, _ = http(gate, "/access/logout", method="POST", cookies=auth,
                             body=urlencode({"csrf": token(config, "team")}).encode())
    assert status == 303 and any(k == b"set-cookie" and b"Max-Age=0" in v for k, v in headers)


def test_cloud_run_cannot_bypass_or_use_insecure_cookies(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "test-service")
    monkeypatch.setenv("DPV_ACCESS_DEV_BYPASS", "1")
    with pytest.raises(ValueError, match="forbidden"):
        access.protect(object())
    monkeypatch.delenv("DPV_ACCESS_DEV_BYPASS")
    monkeypatch.delenv("DPV_ACCESS_CONFIG", raising=False)
    with pytest.raises(ValueError, match="DPV_ACCESS_CONFIG"):
        access.protect(object())
    monkeypatch.setenv("DPV_ACCESS_CONFIG", "unused")
    monkeypatch.setenv("DPV_ACCESS_INSECURE_LOCAL", "1")
    with pytest.raises(ValueError, match="secure cookies"):
        access.protect(object())


def test_revocation_closes_idle_websocket(setup):
    gate, config, path, _, calls = setup
    async def run():
        queue, accepted, closed = asyncio.Queue(), asyncio.Event(), asyncio.Event()
        events = []
        queue.put_nowait({"type": "websocket.connect"})
        gate.store.refresh = 0.02  # short test-only timer; production refresh is 30 seconds
        scope = {"type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws", "path": "/websocket/",
                 "query_string": b"", "headers": [(b"host", b"test.local"), (b"cookie", cookie(config, "team").encode())]}
        async def send(event):
            events.append(event)
            if event["type"] == "websocket.accept":
                accepted.set()
            if event["type"] == "websocket.close":
                closed.set()
        task = asyncio.create_task(gate(scope, queue.get, send))
        await asyncio.wait_for(accepted.wait(), 2)
        config["credentials"]["team"]["version"] = "revoked"
        refresh(gate, config, path)
        await asyncio.wait_for(closed.wait(), 2)
        await task
        assert events[-1] == {"type": "websocket.close", "code": 4401}
    asyncio.run(run())


@pytest.mark.parametrize("user", [None, "alice", "paper"])
def test_restricted_websockets_never_reach_shiny(setup, user):
    gate, config, _, _, calls = setup
    async def run():
        events = []
        scope = {"type": "websocket", "scheme": "ws", "path": "/websocket/", "headers":
                 [(b"cookie", (cookie(config, user) if user else "").encode())], "query_string": b""}
        async def receive():
            return {"type": "websocket.connect"}
        async def send(event):
            events.append(event)
        await gate(scope, receive, send)
        assert events == [{"type": "websocket.close", "code": 4401}]
        assert not calls
    asyncio.run(run())


def test_cross_origin_team_websocket_is_denied(setup):
    gate, config, _, _, calls = setup
    async def run():
        events = []
        scope = {"type": "websocket", "scheme": "wss", "path": "/websocket/", "headers": [
            (b"host", b"test.local"), (b"origin", b"https://untrusted.example"),
            (b"cookie", cookie(config, "team").encode())], "query_string": b""}
        async def receive():
            return {"type": "websocket.connect"}
        async def send(event):
            events.append(event)
        await gate(scope, receive, send)
        assert events == [{"type": "websocket.close", "code": 4403}]
        assert not calls
    asyncio.run(run())


def test_entrypoints_wrap_real_shiny_and_isolate_publication(setup):
    _, _, path, root, _ = setup
    env = {**os.environ, "DPV_ACCESS_CONFIG": str(path), "DPV_SHARE_ROOT": str(root),
           "DPV_ACCESS_MODE": "dashboard", "DPV_VIEWER": "1"}
    env.pop("DPV_ACCESS_DEV_BYPASS", None)
    env.pop("DPV_ACCESS_INSECURE_LOCAL", None)
    check = subprocess.run([sys.executable, "-c",
        "from dpv_dashboard.app import app; from dpv_dashboard.access import AccessGate; "
        "assert isinstance(app,AccessGate) and app.app is not None; "
        "from dpv_dashboard.publication import app as public; "
        "assert public.app is None and public.mode == 'publication'; print('entrypoints protected')"],
        env=env, capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, check.stderr
    assert "entrypoints protected" in check.stdout


def test_publication_import_does_not_load_shiny(setup):
    _, _, path, root, _ = setup
    env = {**os.environ, "DPV_ACCESS_CONFIG": str(path), "DPV_SHARE_ROOT": str(root)}
    env.pop("DPV_ACCESS_DEV_BYPASS", None)
    check = subprocess.run([sys.executable, "-c",
        "import sys; from dpv_dashboard.publication import app; "
        "assert 'shiny' not in sys.modules and 'dpv_dashboard.app' not in sys.modules; "
        "assert app.app is None"], env=env, capture_output=True, text=True, timeout=30)
    assert check.returncode == 0, check.stderr
