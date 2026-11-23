"""Server-side access tiers for Shiny and explicitly shared research files.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import asyncio
import base64
from collections import OrderedDict
import hashlib
import hmac
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import re
from threading import RLock
import time
from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse, Response

IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}")
ROLES = {"team", "collaborator", "paper"}
ITERATIONS = 600_000
MAX_CONFIG = 1024 * 1024
COOKIE = "dpv_access"


def password_hash(password, salt=None):
    """Hash a user-entered password; never persist the plaintext."""
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("Use a password between 12 and 1024 characters")
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def valid_hash(encoded):
    return isinstance(encoded, str) and bool(re.fullmatch(
        rf"pbkdf2_sha256\${ITERATIONS}\$[a-f0-9]{{32}}\$[a-f0-9]{{64}}", encoded))


def verify_password(password, encoded):
    if not isinstance(password, str) or not 1 <= len(password) <= 1024 or not valid_hash(encoded):
        return False
    return hmac.compare_digest(password_hash_for_verification(password, encoded.split("$")[2]), encoded)


def password_hash_for_verification(password, salt):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("Shared paths must be relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Shared paths cannot leave their configured root")
    if any(p.startswith(".") or p.lower() == "private" for p in path.parts) or path.suffix.lower() in {".pem", ".key", ".sqlite3"}:
        raise ValueError("Credential and private files cannot be shared")
    return path


def validate(config):
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("Access configuration requires schema_version 1")
    if not isinstance(config.get("session_key"), str) or len(config["session_key"].encode()) < 32:
        raise ValueError("Configure a session signing key of at least 32 bytes")
    credentials, shares = config.get("credentials"), config.get("shares", {})
    if not isinstance(credentials, dict) or not credentials or len(credentials) > 200:
        raise ValueError("Configure between 1 and 200 named credentials")
    if not isinstance(shares, dict):
        raise ValueError("shares must be a mapping")
    for identifier, share in shares.items():
        if not IDENTIFIER.fullmatch(identifier) or not isinstance(share, dict):
            raise ValueError("Invalid share identifier")
        relative(share.get("root", "."))
        if not isinstance(share.get("title", identifier), str):
            raise ValueError("Share titles must be text")
        files = share.get("files", [])
        if not isinstance(files, list) or len(files) > 10000:
            raise ValueError("Each share needs an explicit file list of at most 10000 entries")
        for file in files:
            relative(file)
        if type(share.get("whole_root", False)) is not bool:
            raise ValueError("whole_root must be a boolean")
    for identifier, row in credentials.items():
        if not IDENTIFIER.fullmatch(identifier) or not isinstance(row, dict) or row.get("role") not in ROLES:
            raise ValueError("Invalid credential identifier or role")
        if not valid_hash(row.get("password_hash")) or type(row.get("enabled", True)) is not bool:
            raise ValueError("Every credential requires a valid password hash and boolean enabled flag")
        if not isinstance(row.get("version"), str) or not row["version"]:
            raise ValueError("Every credential requires a revocation version")
        scopes = row.get("shares", [])
        if not isinstance(scopes, list) or any(not isinstance(s, str) or s not in shares for s in scopes):
            raise ValueError("Credential references an unknown share")
        if row["role"] != "team" and not scopes:
            raise ValueError("Restricted credentials require explicit shares")
    return config


class ConfigStore:
    """Reread private runtime configuration at least every 60 seconds; fail closed on errors."""
    def __init__(self, path, refresh=30):
        self.path, self.refresh = Path(path), max(1, min(float(refresh), 55))
        self._value, self._checked, self._lock = None, float("-inf"), RLock()
        self.load()

    def load(self):
        with self._lock:
            if time.monotonic() - self._checked < self.refresh:
                if self._value is None:
                    raise ValueError("Access configuration unavailable")
                return self._value
            self._checked, self._value = time.monotonic(), None
            try:
                with self.path.open("rb") as stream:
                    payload = stream.read(MAX_CONFIG + 1)
                if len(payload) > MAX_CONFIG:
                    raise ValueError("Configuration too large")
                self._value = validate(json.loads(payload))
            except (OSError, ValueError, TypeError, KeyError):
                raise ValueError("Access configuration unavailable or invalid") from None
            return self._value


def revision(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def sign(value, config):
    payload = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(config["session_key"].encode(), payload.encode(), "sha256").hexdigest()
    return payload + "." + signature


def unsign(token, config):
    try:
        if not isinstance(token, str) or len(token) > 4096:
            return None
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(config["session_key"].encode(), payload.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        value = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(value, dict) or not isinstance(value.get("exp"), (int, float)) or value["exp"] <= time.time():
            return None
        return value
    except (ValueError, TypeError, UnicodeError):
        return None


def identity(token, config, mode):
    value = unsign(token, config)
    if not value or not isinstance(value.get("id"), str):
        return None
    row = config["credentials"].get(value["id"])
    if not row or not row.get("enabled", True) or value.get("revision") != revision(row):
        return None
    if mode == "publication" and row["role"] != "paper":
        return None
    return {**row, "id": value["id"]}


def page(title, content):
    return HTMLResponse("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        f"<title>{escape(title)}</title><style>body{{font:17px system-ui;max-width:900px;margin:5vh auto;padding:24px}}"
        "input,button{font:inherit;padding:10px;margin:8px 0;display:block}li{margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "a{color:#224d80}</style>" + content + "</html>", headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


class AccessGate:
    def __init__(self, app, store, *, mode="dashboard", share_root=None, secure=True, session_seconds=28800):
        if mode not in {"dashboard", "publication"}:
            raise ValueError("DPV_ACCESS_MODE must be dashboard or publication")
        if mode == "publication" and app is not None:
            raise ValueError("Publication mode must not load the working dashboard")
        self.app, self.store, self.mode = app, store, mode
        self.root = Path(share_root).resolve() if share_root else None
        self.secure, self.ttl = secure, max(60, min(int(session_seconds), 86400))
        self.attempts = OrderedDict()
        self.hash_slots = asyncio.Semaphore(4)

    async def config(self):
        return await asyncio.to_thread(self.store.load)

    def login_page(self, config, message="", status=200):
        csrf = sign({"exp": int(time.time()) + 900, "purpose": "login", "nonce": os.urandom(16).hex()}, config)
        response = page("Knowledge Workflow · Sign in", "<h1>Knowledge Workflow</h1><p>Enter your access ID and password.</p>"
            f"<p role=alert>{escape(message)}</p><form method=post action='/access/login'>"
            f"<input type=hidden name=csrf value='{escape(csrf)}'>"
            "<label>Access ID<input name=identifier autocomplete=username required maxlength=64></label>"
            "<label>Password<input type=password name=password autocomplete=current-password required maxlength=1024></label>"
            "<button>Sign in</button></form>")
        response.status_code = status
        response.set_cookie("dpv_login", csrf, max_age=900, httponly=True, secure=self.secure, samesite="strict", path="/")
        return response

    async def form(self, request):
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise ValueError("Unsupported form")
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            raise ValueError("Invalid origin")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                raise ValueError("Form too large")
        values = parse_qs(body.decode("utf-8"), max_num_fields=5)
        if any(len(v) != 1 for v in values.values()):
            raise ValueError("Duplicate form fields")
        return {k: v[0] for k, v in values.items()}

    async def login(self, request, config):
        try:
            form = await self.form(request)
            csrf = form.get("csrf", "")
            challenge = unsign(csrf, config)
            if not challenge or challenge.get("purpose") != "login" or not hmac.compare_digest(csrf, request.cookies.get("dpv_login", "")):
                raise ValueError("Invalid login form")
        except (ValueError, UnicodeError):
            return self.login_page(config, "Please reload the login page and try again.", 400)
        identifier = form.get("identifier", "")
        if not IDENTIFIER.fullmatch(identifier):
            return self.login_page(config, "Access ID or password is incorrect.", 401)
        now = time.monotonic()
        start, count = self.attempts.get(identifier, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        self.attempts[identifier] = (start, count + 1)
        self.attempts.move_to_end(identifier)
        while len(self.attempts) > 4096:
            self.attempts.popitem(last=False)
        if count >= 10:
            return self.login_page(config, "Too many attempts. Try again in a minute.", 429)
        row = config["credentials"].get(identifier)
        # Unknown IDs get the same password-hash workload and generic response.
        encoded = row["password_hash"] if row else next(iter(config["credentials"].values()))["password_hash"]
        async with self.hash_slots:
            valid = await asyncio.to_thread(verify_password, form.get("password", ""), encoded)
        if not valid or not row or not row.get("enabled", True) or (self.mode == "publication" and row["role"] != "paper"):
            return self.login_page(config, "Access ID or password is incorrect.", 401)
        # Configuration may rotate during a password-hash calculation.
        current = await self.config()
        if current["credentials"].get(identifier) != row or current["session_key"] != config["session_key"]:
            return self.login_page(current, "Access settings changed. Please sign in again.", 401)
        token = sign({"id": identifier, "revision": revision(row), "exp": int(time.time()) + self.ttl}, current)
        response = RedirectResponse("/" if row["role"] == "team" else "/shared", status_code=303)
        response.set_cookie(COOKIE, token, max_age=self.ttl, httponly=True, secure=self.secure, samesite="strict", path="/")
        response.delete_cookie("dpv_login", path="/", secure=self.secure, httponly=True, samesite="strict")
        return response

    def files(self, share):
        if self.root is None:
            return []
        root = self.root.joinpath(*relative(share.get("root", ".")).parts).resolve()
        if not root.is_relative_to(self.root) or not root.is_dir():
            return []
        relative(root.relative_to(self.root).as_posix())
        names = share.get("files", [])
        if share.get("whole_root", False):
            names = []
            for path in root.rglob("*"):
                if path.is_file():
                    try:
                        relative(path.relative_to(root).as_posix())
                    except ValueError:
                        continue
                    names.append(path.relative_to(root).as_posix())
                    if len(names) > 10000:
                        raise ValueError("Publication root contains more than 10000 files; use an explicit file list")
        found = []
        for name in sorted(set(names)):
            path = root.joinpath(*relative(name).parts).resolve()
            if path.is_relative_to(root) and path.is_file():
                try:
                    relative(path.relative_to(root).as_posix())
                except ValueError:
                    continue
                found.append((name, path))
        return found

    async def shared(self, request, user, config):
        if request.method not in {"GET", "HEAD"}:
            return Response("Read-only access", status_code=405)
        if request.url.path == "/shared":
            content = f"<h1>Shared research files</h1><p>Access: {escape(user['id'])} · {escape(user['role'])}</p>"
            content += "<p><a href='/access/logout'>Sign out</a></p>"
            for identifier in user.get("shares", []):
                share = config["shares"][identifier]
                files = await asyncio.to_thread(self.files, share)
                content += f"<h2>{escape(share.get('title', identifier))}</h2><ul>"
                for index, (name, _) in enumerate(files):
                    content += f"<li>{escape(name)} · <a href='/shared/{identifier}/{index}'>Download</a> · <a href='/shared/{identifier}/{index}/preview'>View text</a></li>"
                content += "</ul>"
            return page("Shared research files", content)
        parts = request.url.path.strip("/").split("/")
        if len(parts) not in (3, 4) or parts[0] != "shared" or parts[1] not in user.get("shares", []):
            return Response("Not found", status_code=404)
        files = await asyncio.to_thread(self.files, config["shares"][parts[1]])
        if not parts[2].isdigit() or int(parts[2]) >= len(files):
            return Response("Not found", status_code=404)
        name, path = files[int(parts[2])]
        if len(parts) == 4:
            if parts[3] != "preview":
                return Response("Not found", status_code=404)
            with path.open("rb") as stream:
                text = stream.read(256 * 1024).decode("utf-8", errors="replace")
            return page(name, f"<h1>{escape(name)}</h1><p><a href='/shared'>Back</a> · Text preview, first 256 KB</p><pre>{escape(text)}</pre>")
        return FileResponse(path, filename=Path(name).name, media_type="application/octet-stream",
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

    async def websocket(self, scope, receive, send, token):
        """Check active Shiny sockets on traffic and on a timer, even when idle."""
        async def allowed():
            try:
                config = await self.config()
                user = identity(token, config, self.mode)
                return user is not None and user["role"] == "team"
            except ValueError:
                return False

        async def guarded_receive():
            event = await receive()
            if not await allowed():
                return {"type": "websocket.disconnect", "code": 4401}
            return event

        async def guarded_send(message):
            if message["type"] in {"websocket.send", "websocket.accept"} and not await allowed():
                raise PermissionError("Access expired")
            await send(message)

        async def expiry():
            while await allowed():
                await asyncio.sleep(min(self.store.refresh, 5))

        work = asyncio.create_task(self.app(scope, guarded_receive, guarded_send))
        timer = asyncio.create_task(expiry())
        try:
            done, _ = await asyncio.wait({work, timer}, return_when=asyncio.FIRST_COMPLETED)
            if timer in done or (work in done and isinstance(work.exception(), PermissionError)):
                await send({"type": "websocket.close", "code": 4401})
            elif work in done:
                await work
        finally:
            for task in (work, timer):
                if not task.done():
                    task.cancel()
            await asyncio.gather(work, timer, return_exceptions=True)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            if self.app:
                return await self.app(scope, receive, send)
            while True:
                event = await receive()
                await send({"type": event["type"] + ".complete"})
                if event["type"] == "lifespan.shutdown":
                    return
        if scope["type"] not in {"http", "websocket"}:
            return
        try:
            config = await self.config()
        except ValueError:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 4401})
            return await Response("Access configuration unavailable", status_code=503)(scope, receive, send)
        request = Request({**scope, "type": "http"}, receive)
        token = request.cookies.get(COOKIE)
        user = identity(token, config, self.mode)
        path = scope["path"]
        if scope["type"] == "websocket":
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return await send({"type": "websocket.close", "code": 4403})
            if not user or user["role"] != "team" or self.app is None:
                return await send({"type": "websocket.close", "code": 4401})
            return await self.websocket(scope, receive, send, token)
        if path == "/access/login":
            if request.method == "GET":
                response = self.login_page(config)
            elif request.method == "POST":
                try:
                    response = await self.login(request, config)
                except ValueError:
                    response = Response("Access configuration unavailable", status_code=503)
            else:
                response = Response("Method not allowed", status_code=405)
        elif not user:
            response = RedirectResponse("/access/login", status_code=303)
        elif path == "/access/logout":
            if request.method == "POST":
                try:
                    form = await self.form(request)
                    if not hmac.compare_digest(form.get("csrf", ""), token or ""):
                        raise ValueError("Invalid logout")
                    response = RedirectResponse("/access/login", status_code=303)
                    response.delete_cookie(COOKIE, path="/", secure=self.secure, httponly=True, samesite="strict")
                except ValueError:
                    response = Response("Invalid logout form", status_code=400)
            elif request.method == "GET":
                response = page("Sign out", "<h1>Sign out</h1><form method=post action='/access/logout'>"
                                f"<input type=hidden name=csrf value='{escape(token)}'><button>Sign out</button></form>")
            else:
                response = Response("Method not allowed", status_code=405)
        elif path.startswith("/shared") or user["role"] != "team":
            if path == "/":
                response = RedirectResponse("/shared", status_code=303)
            else:
                try:
                    response = await self.shared(request, user, config)
                except (OSError, ValueError):
                    response = Response("Shared files unavailable", status_code=503)
        elif self.app:
            scope["dpv_identity"] = {"id": user["id"], "role": user["role"]}
            async def private_send(message):
                if message["type"] == "http.response.start":
                    headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                    message = {**message, "headers": headers + [(b"cache-control", b"private, no-store")]}
                await send(message)
            return await self.app(scope, receive, private_send)
        else:
            response = Response("Not found", status_code=404)
        response.headers["Cache-Control"] = "private, no-store"
        await response(scope, receive, send)


def protect(app=None):
    """Cloud Run always requires access configuration; bypass is explicit and local only."""
    if os.environ.get("DPV_ACCESS_DEV_BYPASS") == "1":
        if os.environ.get("K_SERVICE") or app is None:
            raise ValueError("Development bypass is forbidden on Cloud Run and publication services")
        return app
    path = os.environ.get("DPV_ACCESS_CONFIG")
    if not path:
        raise ValueError("Set DPV_ACCESS_CONFIG to the private access configuration JSON")
    secure = os.environ.get("DPV_ACCESS_INSECURE_LOCAL") != "1"
    if not secure and os.environ.get("K_SERVICE"):
        raise ValueError("Cloud Run requires secure cookies")
    return AccessGate(app, ConfigStore(path), mode=os.environ.get("DPV_ACCESS_MODE", "dashboard"),
                      share_root=os.environ.get("DPV_SHARE_ROOT"), secure=secure,
                      session_seconds=os.environ.get("DPV_ACCESS_SESSION_SECONDS", "28800"))
