"""Create a password hash interactively; plaintext never enters command arguments.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dpv_dashboard.access import password_hash, valid_hash, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--setup", action="store_true", help="privately fill missing signing key and password hashes")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/dashboard/private/access.json")
    args = parser.parse_args()
    if not args.setup:
        password = getpass("New access password (at least 12 characters): ")
        if password != getpass("Repeat password: "):
            raise SystemExit("Passwords did not match; nothing saved")
        print(password_hash(password))
        return

    target = args.output.resolve()
    if target.exists() and target.stat().st_size > 1024 * 1024:
        raise SystemExit("Access configuration is too large; nothing saved")
    original = target.read_bytes() if target.exists() else None
    template = Path(__file__).resolve().parents[1] / "dpv_dashboard/access.example.json"
    try:
        config = json.loads(original if original is not None else template.read_bytes())
    except (ValueError, UnicodeError):
        raise SystemExit("Access configuration is not readable JSON; nothing saved") from None
    if not isinstance(config, dict) or not isinstance(config.get("credentials"), dict) or not config["credentials"]:
        raise SystemExit("Access configuration must contain named credentials; nothing saved")
    if config == json.loads(template.read_bytes()):
        # The example's sample filenames are not a publication approval.
        for share in config.get("shares", {}).values():
            share["files"] = []
    if config.get("session_key") and (not isinstance(config["session_key"], str) or len(config["session_key"].encode()) < 32):
        raise SystemExit("Existing session_key is invalid; correct it explicitly before setup")
    for identifier, row in config["credentials"].items():
        if not isinstance(row, dict) or row.get("password_hash") and not valid_hash(row["password_hash"]):
            raise SystemExit(f"Credential {identifier!r} is invalid; nothing saved")

    changed = False
    print("Passwords stay in this local process. No password or signing key will be printed.")
    print("Existing credentials and custom grants are preserved; example file grants stay empty. Ctrl+C cancels.")
    for identifier, row in config["credentials"].items():
        if valid_hash(row.get("password_hash")):
            continue
        print(f"Set password for {identifier} ({row.get('role', 'unknown role')}).")
        password = getpass("Password (12–1024 characters): ")
        if password != getpass("Repeat password: "):
            raise SystemExit("Passwords did not match; nothing saved")
        try:
            row["password_hash"] = password_hash(password)
        except ValueError as exc:
            raise SystemExit(f"{exc}; nothing saved") from None
        password = None
        changed = True
    if not config.get("session_key"):
        config["session_key"] = secrets.token_hex(32)
        changed = True
    try:
        validate(config)
    except ValueError as exc:
        raise SystemExit(f"{exc}; nothing saved") from None
    if not changed:
        print("Credentials already configured; nothing changed.")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(config, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if (target.read_bytes() if target.exists() else None) != original:
            raise SystemExit("Configuration changed during setup; nothing overwritten. Run setup again.")
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(f"Private access configuration saved: {target}")
    print("Credentials validated. Review file grants after the bucket layout is finalized; nothing uploaded.")


if __name__ == "__main__":
    main()
