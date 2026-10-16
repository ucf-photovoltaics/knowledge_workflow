"""Read existing model profiles without importing or changing pipeline configuration.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import ast
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dpv_dashboard import catalog, model

PROVIDERS = {"ollama": "Local Ollama", "ollama-lora": "Local Ollama", "vllm": "vLLM", "gemini": "Google Gemini",
             "gemini-lite": "Google Gemini", "deepseek": "DeepSeek", "groq": "Groq", "anthropic": "Anthropic"}


def profiles(settings):
    values = {}
    def resolve(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    result.update(resolve(value))
                else:
                    result[resolve(key)] = resolve(value)
            return result
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "PROFILES":
            return values.get(resolve(node.slice), {})
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "getenv":
            key = resolve(node.args[0])
            return settings.get(key) or os.environ.get(key) or (resolve(node.args[1]) if len(node.args) > 1 else None)
        raise ValueError("Unsupported profile setting")
    try:
        tree = ast.parse((model.ROOT / "src/config.py").read_text(encoding="utf-8"))
        for statement in tree.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id == "PROFILES":
                values.update(resolve(statement.value))
            elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "PROFILES":
                values[resolve(target.slice)] = resolve(statement.value)
    except (OSError, SyntaxError, ValueError, TypeError):
        return values
    return values


_PROBES = {}
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def reachable(base_url):
    """Whether a model server answers; cached for 30 s so page renders stay fast."""
    now = time.monotonic()
    if base_url in _PROBES and now - _PROBES[base_url][1] < 30:
        return _PROBES[base_url][0]
    try:
        _NO_PROXY.open(base_url.rstrip("/") + "/models", timeout=1.5).close()
        ok = True
    except urllib.error.HTTPError:
        ok = True  # the server answered, if only with an error
    except Exception:
        ok = False
    _PROBES[base_url] = (ok, now)
    return ok


def offline(option):
    """A local model server (e.g. Ollama) that is not running."""
    host = urllib.parse.urlparse((option or {}).get("base_url") or "").hostname or ""
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal") and not reachable(option["base_url"])


def model_label(name):
    if name == "kw-qwen3.5-9b-32k":
        return "Qwen 3.5 · 9B"
    if name == "kw-qwen3.5-9b-lora-32k":
        return "Qwen 3.5 · 9B fine-tuned"
    words = name.rsplit("/", 1)[-1].replace("-", " ").split()
    brands = {"gemini": "Gemini", "deepseek": "DeepSeek", "llama": "Llama", "mistral": "Mistral", "qwen": "Qwen", "gpt": "GPT"}
    return " ".join(brands.get(w.lower(), w) for w in words)


def choices(root, project, settings):
    known = profiles(settings)
    manifest = catalog.load(root / "integration.json", {}) or catalog.load(root / "run.json", {}) if root else {}
    config = manifest.get("config", {})
    routes = config.get("agent_profiles", {})
    route = routes.get("integration") or routes.get("interoperability") or {}
    selected = route.get("profile") or config.get("llm_profile") or (project or {}).get("profile", "ollama")
    def option(profile, name=None, base=None, provider=None):
        saved = known.get(profile, {})
        return {"model": name or saved.get("model", ""), "base_url": base or saved.get("base_url"),
                "provider": provider or saved.get("provider", "openai"), "key_name": saved.get("api_key_env"),
                "profile": profile, "request": saved.get("request", {})}
    workflow = option(selected, config.get("model_integration") or config.get("model_interoperability") or config.get("model"),
                      route.get("base_url") or config.get("llm_base_url"), route.get("provider") or config.get("llm_provider"))
    result = {}
    if workflow["model"]:
        result["workflow"] = {**workflow, "label": "Same as workflow · " + model_label(workflow["model"])}
    seen = {(workflow["provider"], workflow["base_url"], workflow["model"])}
    for stage, value in config.items():
        if not stage.startswith("model_") or not isinstance(value, str) or not value:
            continue
        stage_name = stage.removeprefix("model_")
        routed = routes.get(stage_name, {})
        profile = routed.get("profile") or config.get("llm_profile") or selected
        known.setdefault(profile, {})
        candidate = option(profile, value, routed.get("base_url"), routed.get("provider"))
        identity = (candidate["provider"], candidate["base_url"], candidate["model"])
        if identity not in seen and (not candidate["key_name"] or settings.get(candidate["key_name"])):
            result[stage] = {**candidate, "label": model_label(value) + " · " + PROVIDERS.get(profile, profile.title())}
            seen.add(identity)
    for name, value in known.items():
        identity = (value.get("provider"), value.get("base_url"), value.get("model"))
        if not value.get("model") or identity in seen or value.get("api_key_env") and not settings.get(value["api_key_env"]):
            continue
        result[name] = {**option(name), "label": model_label(value["model"]) + " · " + PROVIDERS.get(name, name.title())}
        seen.add(identity)
    custom_model = settings.get("DPV_CHAT_MODEL") or settings.get("LLM_MODEL") or settings.get("OPENAI_MODEL")
    custom_base = settings.get("DPV_CHAT_BASE_URL") or settings.get("LLM_BASE_URL") or settings.get("OPENAI_BASE_URL")
    if custom_model and custom_base:
        result["saved_chat"] = {"model": custom_model, "base_url": custom_base, "provider": "openai", "profile": "custom",
            "key_name": next((k for k in ("DPV_CHAT_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY") if settings.get(k)), None),
            "request": {}, "label": model_label(custom_model) + " · Saved connection"}
    for value in result.values():
        if offline(value):
            value["offline"] = True
            value["label"] += " · not running"
    return result


def connection(option, settings):
    if not option:
        raise ValueError("Choose a chat model. Connect a model provider on Home, or enter a Gemini API key for this session.")
    if offline(option):
        raise ValueError("This local model server is not running. Start Ollama, or choose another model "
                         "(for example Gemini, after entering an API key for this session).")
    key = option.get("key_name")
    if key and not settings.get(key):
        raise ValueError("This model needs a saved provider sign-in. Update your connection on Home, then try again.")
    endpoint = option.get("base_url")
    if not endpoint and option.get("provider") == "anthropic":
        endpoint = "https://api.anthropic.com/v1"
    if not endpoint:
        raise ValueError("The workflow's model connection is incomplete. Choose another model or update your connection on Home.")
    values = {"DPV_CHAT_BASE_URL": endpoint, "DPV_CHAT_PROVIDER": option.get("provider", "openai"),
              "DPV_CHAT_REQUEST": option.get("request", {})}
    if key:
        values["DPV_CHAT_API_KEY"] = settings[key]
    return values, option["model"]
