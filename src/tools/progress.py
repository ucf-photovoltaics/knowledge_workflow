"""Console progress: every line is 'HH:MM:SS [stage] message'.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import time
import json
import logging
import os
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import quote, quote_plus

_stage = ["setup"]
_folder = None
_run_id = None
_lock = RLock()


class _DiagnosticHandler(logging.Handler):
    def emit(self, record):
        log(f'{record.levelname}: {record.name}: {self.format(record)}')


_handler = _DiagnosticHandler(logging.WARNING)


def redact(message: str) -> str:
    for name, value in os.environ.items():
        if value and re.search(r'KEY|TOKEN|PASSWORD|SECRET', name, re.I):
            for encoded in (value, quote(value, safe=''), quote_plus(value)):
                message = message.replace(encoded, '***')
    message = re.sub(r'(?i)((?:apikey|api_key|access_token|password|secret)\s*[=:]\s*)[^&\s,;]+', r'\1***', message)
    return re.sub(r'(?i)(Bearer\s+)[^\s]+', r'\1***', message)


def configure_logging(folder: Path, run_id: str):
    """Append console messages and diagnostics independently of the sweep shell."""
    global _folder, _run_id
    _folder, _run_id = Path(folder), run_id
    _folder.mkdir(parents=True, exist_ok=True)
    warnings.showwarning = _warning
    warnings.simplefilter('always')
    root_logger = logging.getLogger()
    if _handler not in root_logger.handlers:
        root_logger.addHandler(_handler)


def _warning(message, category, filename, lineno, file=None, line=None):
    log(f'warning: {category.__name__}: {message} ({filename}:{lineno})')


def _record(message: str, end: str):
    if _folder is None:
        return
    with _lock:
        with (_folder / 'run.log').open('a', encoding='utf-8') as stream:
            stream.write(f"{time.strftime('%H:%M:%S')} [{_stage[0]}] {message}{end}")
        if re.search(r'warning|failed|error|ignored|unavailable|overload|retry|not written|not updated|dropped|invalid|NO VALID JSON|fallback|quota|skipped|refused', message, re.I):
            event = {'time': datetime.now(timezone.utc).isoformat(), 'run_id': _run_id,
                     'stage': _stage[0], 'level': 'ERROR' if re.search(r'failed|error', message, re.I) else 'WARNING',
                     'message': message}
            with (_folder / 'warnings_errors.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')


def set_stage(name: str):
    _stage[0] = name


def log(message: str, end: str = "\n"):
    message = redact(message)
    _record(message, end)
    print(f"{time.strftime('%H:%M:%S')} [{_stage[0]}] {message}", end=end, flush=True)


def finish(message: str):
    """Complete a line started with log(..., end='')."""
    message = redact(message)
    _record(message, '\n')
    print(f" {message}", flush=True)
