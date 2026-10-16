"""Local credentials are saved outside source control and never returned to the browser.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from dotenv import dotenv_values
from dpv_dashboard.model import DATA

ENV = DATA / "private" / ".env"


def credentials():
    return {k: v for k, v in dotenv_values(ENV, interpolate=False).items() if v is not None} if ENV.is_file() else {}


def save_env(source: Path):
    from dpv_dashboard.model import require_editor
    require_editor()
    if source.stat().st_size > 65536:
        raise ValueError("Environment file must be smaller than 64 KB.")
    values = dotenv_values(source, interpolate=False)
    if not values or not any(values.values()):
        raise ValueError("No settings found in the environment file.")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) for k in values):
        raise ValueError("Environment setting names must be valid identifiers.")
    ENV.parent.mkdir(parents=True, exist_ok=True)
    temporary = ENV.with_suffix(".tmp")
    temporary.write_bytes(source.read_bytes())
    temporary.replace(ENV)
    os.chmod(ENV, 0o600)


def redact(text):
    for key, value in credentials().items():
        if value and re.search(r"KEY|TOKEN|PASSWORD|SECRET", key, re.I):
            text = text.replace(value, "[redacted]")
    return re.sub(r"(?i)(Bearer\s+)\S+", r"\1[redacted]", text)
