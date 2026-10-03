"""Persistent Gemini chat quotas; reservations include every retry attempt."""
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from src.tools.progress import log


class GeminiRequestStopped(RuntimeError):
    """Stop without treating unavailable Gemini service as a failed paper."""


class QuotaExhausted(GeminiRequestStopped):
    """Daily quota reached: stop the run rather than skip papers."""


class GeminiQuota:
    def __init__(self, path, limits):
        self.path, self.limits = path, limits
        self.pacific = ZoneInfo("America/Los_Angeles")

    def day(self, now):
        return datetime.fromtimestamp(now, self.pacific).date().isoformat()

    def reserve(self, model, tokens):
        limits = self.limits.get(model)
        if not limits:
            raise ValueError(f"Configure GEMINI_LIMITS for model {model!r} before calling Gemini")
        rpm, tpm, rpd = (limits[k] for k in ("rpm", "tpm", "rpd"))
        if rpm <= 0 or rpd <= 0 or (tpm is not None and tpm <= 0):
            raise ValueError("Gemini rpm/rpd/tpm limits must be positive (tpm may be None)")
        if tpm is not None and tokens > tpm:
            raise ValueError("Gemini input exceeds the configured TPM budget; reduce the batch/input size")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            now = time.time()
            with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS requests (model TEXT, ts REAL, day TEXT, tokens INTEGER)")
                db.execute("CREATE TABLE IF NOT EXISTS blocked (model TEXT, day TEXT, PRIMARY KEY(model, day))")
                db.commit()
                db.execute("BEGIN IMMEDIATE")
                day = self.day(now)
                daily = db.execute("SELECT COUNT(*) FROM requests WHERE model=? AND day=?", (model, day)).fetchone()[0]
                blocked = db.execute("SELECT 1 FROM blocked WHERE model=? AND day=?", (model, day)).fetchone()
                if blocked or daily >= rpd:
                    raise QuotaExhausted(f"Gemini daily quota reached for {model}; resume after midnight Pacific")
                recent = db.execute("SELECT ts,tokens FROM requests WHERE model=? AND ts>? ORDER BY ts",
                                    (model, now - 60)).fetchall()
                # Even pacing avoids bursts; the rolling window also survives restarts.
                wait = max(0, recent[-1][0] + 60 / rpm + 0.1 - now) if recent else 0
                if len(recent) >= rpm:
                    wait = max(wait, recent[-rpm][0] + 60.1 - now)
                if tpm is not None:
                    total = sum(t for _, t in recent) + tokens
                    for ts, count in recent:
                        if total <= tpm:
                            break
                        total -= count
                        wait = max(wait, ts + 60.1 - now)
                if wait <= 0:
                    db.execute("INSERT INTO requests VALUES (?,?,?,?)", (model, now, day, tokens))
                    return
            log(f"  Gemini quota: waiting {min(wait, 60):.1f}s")
            time.sleep(min(wait, 60))

    def block_day(self, model):
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute("INSERT OR IGNORE INTO blocked VALUES (?,?)", (model, self.day(time.time())))


def daily_error(error):
    # Google quota IDs/metrics, plus readable proxy errors. Never print the error body.
    text = str(getattr(error, "body", "") or error).lower()
    return bool(re.search(r"perday|per_day|requests? per day|daily quota|\brpd\b", text))


def retry_delay(error, attempt):
    headers = getattr(getattr(error, "response", None), "headers", {})
    value = headers.get("retry-after")
    if value:
        try:
            return max(0, float(value)) + 1
        except ValueError:
            try:
                return max(0, parsedate_to_datetime(value).timestamp() - time.time()) + 1
            except (TypeError, ValueError, OverflowError):
                pass
    text = str(getattr(error, "body", "") or error)
    match = re.search(r"(?:retry in|retryDelay[\"']?\s*[:=])\s*[\"']?([\d.]+)s", text, re.I)
    return float(match.group(1)) + 1 if match else min(60, 2 ** attempt)


def call(client, model, system, user, options, quota, retries):
    import openai
    # UTF-8 bytes are deliberately conservative for text tokenization; 256 covers framing.
    tokens = len(system.encode("utf-8")) + len(user.encode("utf-8")) + 256
    for attempt in range(retries + 1):
        quota.reserve(model, tokens)
        try:
            return client.chat.completions.create(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **options)
        except (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError) as error:
            if isinstance(error, openai.RateLimitError) and daily_error(error):
                quota.block_day(model)
                raise QuotaExhausted(f"Gemini reported daily quota exhaustion for {model}; resume after midnight Pacific") from None
            if attempt == retries:
                raise GeminiRequestStopped(f"Gemini request failed after {retries + 1} attempts ({type(error).__name__}); resume the run later") from None
            wait = retry_delay(error, attempt)
            log(f"  Gemini {type(error).__name__}: retry {attempt + 1}/{retries} after {wait:.1f}s")
            while wait > 0:
                pause = min(wait, 60)
                time.sleep(pause)
                wait -= pause
