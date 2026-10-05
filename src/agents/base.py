"""Shared agent mechanics: stable system prompt (prompt + schema), JSON call with one retry, ledger logging."""
import hashlib
import json
import re
from collections import Counter

from src.config import RESOURCES, model_for, profile_for
from src.tools import llm
from src.tools.ledger import Ledger
from src.tools.progress import finish, log


def parse_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # local reasoning models
    text = re.sub(r"\\ud[89a-f][0-9a-f]{2}", "", text, flags=re.I)  # escaped lone surrogates -> not valid UTF-8
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def load_prompt(name: str) -> str:
    """Prompt text plus its compact JSON schema (if any): the stable, cacheable system prefix."""
    prompt = (RESOURCES / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    schema = RESOURCES / "schemas" / f"{name}.json"
    return prompt + (json.dumps(json.loads(schema.read_text(encoding="utf-8")), separators=(",", ":")) if schema.exists() else "")


def key(value) -> str | None:
    """A model-supplied id as a plain string. Models sometimes return ["k3"] or 3 instead of "k3"."""
    if isinstance(value, list):
        value = value[0] if len(value) == 1 else None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    return value.strip() if isinstance(value, str) else None


def targets(value) -> list[str]:
    """One or many model-supplied ids as a list of strings."""
    return [k for k in (key(v) for v in (value if isinstance(value, list) else [value])) if k]


def items(obj, field: str, value_key: str | None = None) -> list[dict]:
    """The dict entries of obj[field], ignoring anything malformed.
    Small models often answer in another shape; with value_key these are read too:
      {"k1": "quality", ...} or {field: {"k1": "quality"}}  -> [{"id": "k1", value_key: "quality"}]
      {"k1": {...}, ...}                                  -> [{"id": "k1", ...}]
      {"<other name>": [{...}]} (a single list under another key) -> that list"""
    if not isinstance(obj, dict):
        return []
    if field not in obj and value_key and "id" in obj and value_key in obj:  # one row answered as a bare object
        return [obj]
    if field not in obj and isinstance(obj.get("properties"), dict):  # small models echo the JSON schema around the answer
        obj = obj["properties"]
    value = obj.get(field)
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        value = value["items"]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if not value_key:
        return []
    if value is None and len(obj) == 1 and isinstance(next(iter(obj.values())), list):
        return [x for x in next(iter(obj.values())) if isinstance(x, dict)]
    mapping = value if isinstance(value, dict) else obj if value is None else {}
    return [{"id": str(k), **v} if isinstance(v, dict) else {"id": str(k), value_key: v} for k, v in mapping.items()]


def compact(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


class Agent:
    name = ""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        self.profile = profile_for(self.name)
        self.model = model_for(self.name)
        self.system = load_prompt(self.name)
        self.fingerprint = hashlib.sha256((self.model + self.system).encode()).hexdigest()
        self.spent = Counter()  # running totals for this agent instance
        self.failures = Counter()  # soft calls that returned no valid JSON, by label
        self.row_stats = {}  # per pass: rows sent, answered first time, recovered by the retry, still missing
        self.doubts = []  # items only counted elsewhere, listed for review in ontology/uncertain.json

    def doubt(self, kind: str, **item):
        """Record one uncertain or dropped item (kind names why) for ontology/uncertain.json."""
        kept = {k: v for k, v in item.items() if v not in (None, "", [], {})}
        self.__dict__.setdefault("doubts", []).append({"kind": kind, **kept})

    def call(self, user: str, item: str, system: str | None = None, label: str | None = None,
             soft: bool = False) -> dict:
        """One JSON call with one retry. soft=True returns {} on failure (the pass is skipped, the run goes on)."""
        for attempt in range(2):
            log(f"  {label or item}: {self.model}{' (retry: previous reply was not JSON)' if attempt else ''} ...", end="")
            text, usage = llm.chat(system or self.system, user, self.model, profile=self.profile)
            data = parse_json(text)
            finish(f"{usage.latency_s:.1f}s, {usage.input_tokens:,} in / {usage.output_tokens:,} out"
                   + ("" if data is not None else ", NO VALID JSON"))
            self.ledger.log(self.name, item, self.model, usage, ok=data is not None, attempt=attempt)
            if self.name != "extraction":  # extraction keeps its own raw_calls per paper
                with (self.ledger.path.parent / "calls.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"agent": self.name, "item": item, "attempt": attempt, "ok": data is not None,
                                        "output": text[:30000]}, ensure_ascii=False) + "\n")
            self.spent.update(calls=1, input_tokens=usage.input_tokens, cached_tokens=usage.cached_tokens,
                              output_tokens=usage.output_tokens, latency_s=usage.latency_s)
            if data is not None:
                return data
        if soft:
            self.failures[(label or item).split(" ")[0]] += 1
            log(f"  {label or item}: no valid JSON after 2 attempts; skipping this pass")
            return {}
        raise ValueError(f"{self.name}: no valid JSON for {item} after 2 attempts")

    def call_rows(self, rows: list[dict], system: str, item: str, field: str, value_key: str | None = None,
                  size: int = 25, label: str | None = None, stat: str | None = None) -> list[dict]:
        """Rows in batches; rows the model left out are sent once more in half-size batches. Returns one answer
        entry per answered row id; coverage counts accumulate in self.row_stats[stat or item]."""
        ids, answers, answered = {str(r["id"]) for r in rows}, [], set()

        def send(todo, n, tag):
            batches = -(-len(todo) // n)
            for i in range(0, len(todo), n):
                part = todo[i:i + n]
                out = self.call(f"Return one entry for each of these {len(part)} ids.\n" + compact(part),
                                item=f"{item}{tag}_{i // n + 1}", system=system,
                                label=f"{label or item}{tag} {i // n + 1}/{batches}", soft=True)
                for a in items(out, field, value_key):
                    k = key(a.get("id"))
                    if k in ids and k not in answered:
                        answered.add(k)
                        answers.append(a)

        send(rows, size, "")
        first = len(answered)
        missing = [r for r in rows if str(r["id"]) not in answered]
        if missing:
            send(missing, max(5, size // 2), "_retry")
        for r in rows:
            if str(r["id"]) not in answered:
                self.doubt("unanswered_row", step=stat or item, id=str(r["id"]), label=r.get("label"))
        s = self.row_stats.setdefault(stat or item, Counter())
        s.update(rows=len(rows), answered_first=first, recovered=len(answered) - first,
                 missing=len(rows) - len(answered))
        return answers
