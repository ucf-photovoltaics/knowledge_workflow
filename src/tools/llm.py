"""Provider-agnostic chat call returning (text, usage), with usage normalized across providers."""
import time
from dataclasses import dataclass

from src.config import CACHE, EMBED, GEMINI_LIMITS, LLM, MAX_OUTPUT_TOKENS, MAX_RETRIES, TEMPERATURE, secret
from src.tools import gemini_quota


@dataclass
class Usage:
    input_tokens: int = 0   # all prompt tokens, cached included
    cached_tokens: int = 0  # prompt tokens served from the provider cache
    output_tokens: int = 0
    latency_s: float = 0.0


_clients = {}
_quota = None


def _get_client(profile=None):
    profile = LLM if profile is None else profile
    identity = (profile["provider"], profile["base_url"], profile["api_key_env"])
    if identity not in _clients:
        key = secret(profile["api_key_env"])
        if profile["provider"] == "anthropic":
            import anthropic
            _clients[identity] = anthropic.Anthropic(api_key=key, base_url=profile["base_url"], max_retries=MAX_RETRIES)
        else:
            import openai
            gemini = profile.get("api_key_env") == "GEMINI_API_KEY"
            _clients[identity] = openai.OpenAI(api_key=key or "none", base_url=profile["base_url"],
                                              max_retries=0 if gemini else MAX_RETRIES)
    return _clients[identity]


def chat(system: str, user: str, model: str, max_tokens: int = MAX_OUTPUT_TOKENS,
         profile: dict | None = None) -> tuple[str, Usage]:
    """One JSON-returning call. The system prompt is the stable, cacheable prefix."""
    profile = LLM if profile is None else profile
    client = _get_client(profile)
    gemini = profile.get("api_key_env") == "GEMINI_API_KEY"
    kw = {"temperature": TEMPERATURE} if TEMPERATURE is not None else {}
    t0 = time.perf_counter()
    if profile["provider"] == "anthropic":
        r = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}], **kw)
        text = "".join(b.text for b in r.content if b.type == "text")
        u = r.usage
        cached = u.cache_read_input_tokens or 0
        usage = Usage(u.input_tokens + cached + (u.cache_creation_input_tokens or 0), cached, u.output_tokens)
    else:
        if gemini:
            global _quota
            if _quota is None:
                _quota = gemini_quota.GeminiQuota(CACHE / "gemini_quota.sqlite3", GEMINI_LIMITS)
            r = gemini_quota.call(client, model, system, user,
                                  {**kw, **profile.get("request", {}), "max_tokens": max_tokens}, _quota, MAX_RETRIES)
        else:
            r = client.chat.completions.create(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                **kw, **profile.get("request", {}))
        text = r.choices[0].message.content or ""
        u = r.usage
        details = getattr(u, "prompt_tokens_details", None)
        usage = Usage(u.prompt_tokens, getattr(details, "cached_tokens", 0) or 0, u.completion_tokens)
    usage.latency_s = round(time.perf_counter() - t0, 3)
    return text, usage


def embed(texts: list[str], batch: int = 100) -> tuple[list[list[float]], Usage]:
    """Embeddings from an OpenAI-compatible /embeddings endpoint (OpenAI, Ollama, vLLM, Gemini).
    Paced to EMBED['inputs_per_minute']; on a quota error it waits the delay the provider asks for."""
    import re
    import openai
    from src.tools.progress import log
    client = openai.OpenAI(api_key=secret(EMBED["api_key_env"]) or "none", base_url=EMBED["base_url"],
                           max_retries=MAX_RETRIES, timeout=120)
    per_minute = EMBED.get("inputs_per_minute")
    batch = min(batch, per_minute) if per_minute else batch
    t0, vectors, tokens = time.perf_counter(), [], 0
    for i in range(0, len(texts), batch):
        if per_minute and i:
            log(f"  embedding quota: pausing 60s before labels {i + 1}-{min(i + batch, len(texts))} of {len(texts)}")
            time.sleep(60)
        for attempt in range(5):
            try:
                r = client.embeddings.create(model=EMBED["model"], input=texts[i:i + batch])
                break
            except openai.RateLimitError as e:
                wait = float(m.group(1)) + 2 if (m := re.search(r"retry in ([\d.]+)s", str(e))) else 30 * (attempt + 1)
                if attempt == 4:
                    raise
                log(f"  embedding quota hit; waiting {wait:.0f}s")
                time.sleep(wait)
        vectors += [d.embedding for d in r.data]
        tokens += getattr(r.usage, "prompt_tokens", 0) or 0
    return vectors, Usage(tokens, 0, 0, round(time.perf_counter() - t0, 3))
