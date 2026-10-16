"""Shared agent mechanics: stable system prompt (prompt + schema), JSON call with one retry, ledger logging,
and answers reused per row across runs (RowCache).

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import asdict
from collections import Counter
from threading import RLock

from src import config
from src.config import CACHE, RESOURCES, REUSE_ANSWERS, TEMPERATURE, WORKFLOW_REVISION, model_for, profile_for
from src.tools import files, llm, workers
from src.tools.ledger import Ledger
from src.tools.progress import finish, log


RESPONSE_EXAMPLES = {
    "ontology_category": {"classes": [{"id": "k1", "category": "quality"}]},
    "ontology_parent": {"classes": [{"id": "k1", "parent": "U:quality"}]},
    "enrichment_definitions": {"classes": [{"id": "k1", "definition": "", "basis": "none",
                                              "category_conflict": False}]},
    "enrichment_synonyms": {"classes": [{"id": "k1", "alt_labels": []}]},
    "enrichment_restrictions": {"classes": [{"id": "k1", "restrictions": []}]},
    "enrichment_disjoint": {"classes": [{"id": "k1", "disjoint_with": []}]},
    "facets": {"tags": [{"id": "k1", "study_stage": ["Sample"], "domain": "General", "subdomain": ""}]},
    "facets_stage": {"tags": [{"id": "k1", "study_stage": ["Sample"]}]},
    "facets_domain": {"tags": [{"id": "k1", "domain": "General", "subdomain": ""}]},
}


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
    pv = config.DOMAIN == config.DEFAULT_DOMAIN
    prompt = prompt.replace("{{domain}}", config.DOMAIN)
    for ex, (pv_text, other) in config.PROMPT_EXAMPLES.items():
        prompt = prompt.replace("{{ex:" + ex + "}}", pv_text if pv else other)
    schema = RESOURCES / "schemas" / f"{name}.json"
    prompt += json.dumps(json.loads(schema.read_text(encoding="utf-8")), separators=(",", ":")) if schema.exists() else ""
    if name in RESPONSE_EXAMPLES:
        prompt += ("\n\nANSWER SHAPE EXAMPLE (replace ids and values with your answers; include EVERY input id, "
                   "including empty answers; do not return the schema):\n"
                   + json.dumps(RESPONSE_EXAMPLES[name], separators=(",", ":")))
    return prompt


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


def _hidden_rows(obj, value_key: str | None) -> list[dict]:
    """Answer rows anywhere inside a copy of the JSON schema: lists of dicts that carry an id (and value_key)."""
    found = []

    def walk(x):
        if isinstance(x, list):
            rows = [r for r in x if isinstance(r, dict) and isinstance(r.get("id"), (str, int)) and "type" not in r
                    and (not value_key or value_key in r)]
            if rows:
                found.extend(rows)
                return
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            rows = [v for v in x.values() if isinstance(v, dict) and isinstance(v.get("id"), (str, int))
                    and "type" not in v and (not value_key or value_key in v)]  # {"k1": {"id": "k1", ...}, ...}
            found.extend(rows)
            for y in x.values():
                if not any(y is r for r in rows):
                    walk(y)

    walk(obj)
    return found


def items(obj, field: str, value_key: str | None = None) -> list[dict]:
    """The dict entries of obj[field], ignoring anything malformed.
    Small models often answer in another shape; with value_key these are read too:
      {"k1": "quality", ...} or {field: {"k1": "quality"}}  -> [{"id": "k1", value_key: "quality"}]
      {"k1": {...}, ...}                                  -> [{"id": "k1", ...}]
      {"<other name>": [{...}]} (a single list under another key) -> that list"""
    if not isinstance(obj, dict):
        return []
    if "type" in obj and isinstance(obj.get("properties"), dict):  # the schema echoed back, the answer (if any) inside
        rows = _rows(obj, field, value_key)
        seen = {str(r.get("id")) for r in rows}
        return rows + [r for r in _hidden_rows(obj, value_key) if str(r.get("id")) not in seen]
    return _rows(obj, field, value_key)


def _rows(obj: dict, field: str, value_key: str | None) -> list[dict]:
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


_ID = re.compile(r"k\d+")
_ID_PREFIX = re.compile(r"^(k\d+)(?=: )")   # "k3: label" (sibling lists)
_ID_PAREN = re.compile(r"\((k\d+)\)")      # "label (k12) x3" (relation lists)
_TOKEN = re.compile("\u27e6[^\u27e7]*\u27e7")  # a concept label standing in for its id in RowCache
_TOKEN_PREFIX = re.compile("^(\u27e6[^\u27e7]*\u27e7)(?=: )")
_TOKEN_PAREN = re.compile("\\((\u27e6[^\u27e7]*\u27e7)\\)")


class RowCache:
    """Answers reused per row across runs (e.g. tea-n5 -> tea-n10). Concept ids (k1, k2, ...) are renumbered in
    every run, so rows and answers are stored with each id replaced by its concept's label; a row is reused only
    when everything the model sees for it - pass prompt, model and request settings, revision and the row itself
    (evidence, support counts, parent, siblings, candidates) - is identical. Any change gives a new key and a fresh
    answer. Rows naming a concept whose label is shared by another concept, or an id with no label, are never
    reused."""

    def __init__(self, agent: "Agent", system: str, field: str, value_key):
        tokens, seen = {}, {}
        for cid, label in agent.concept_labels.items():
            t = "\u27e6" + " ".join(str(label).lower().split()) + "\u27e7"
            seen[t] = seen.get(t, 0) + 1
            tokens[cid] = t
        self.tokens = {cid: t for cid, t in tokens.items() if seen[t] == 1}
        self.ids = {t: cid for cid, t in self.tokens.items()}
        self.identity = {"version": 1, "revision": WORKFLOW_REVISION, "agent": agent.name, "model": agent.model,
                         "provider": agent.profile["provider"], "base_url": agent.profile["base_url"],
                         "temperature": TEMPERATURE, "request": agent.profile.get("request", {}),
                         "system": system, "field": field, "value_key": value_key}
        self.run = agent.ledger.path.parent.name
        CACHE.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(CACHE / "rows.sqlite3", timeout=60)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS rows (key TEXT PRIMARY KEY, answer TEXT NOT NULL, "
                        "source_run TEXT, created REAL)")

    @staticmethod
    def _swap(obj, whole, part, table: dict):
        """obj with ids or tokens swapped through table: a string that is one (whole) or holds them in the sibling
        and relation forms (part). None when one has no entry."""
        missing = []

        def sub(m):
            if m.group(1) in table:
                return m.group(0).replace(m.group(1), table[m.group(1)])
            missing.append(m.group(1))
            return m.group(0)

        def walk(x):
            if isinstance(x, dict):
                return {k: walk(v) for k, v in x.items()}
            if isinstance(x, list):
                return [walk(v) for v in x]
            if not isinstance(x, str):
                return x
            if whole.fullmatch(x):
                if x in table:
                    return table[x]
                missing.append(x)
                return x
            for pattern in part:
                x = pattern.sub(sub, x)
            return x

        out = walk(obj)
        return None if missing else out

    def _tokens(self, obj):
        return self._swap(obj, _ID, (_ID_PREFIX, _ID_PAREN), self.tokens)

    def _ids(self, obj):
        return self._swap(obj, _TOKEN, (_TOKEN_PREFIX, _TOKEN_PAREN), self.ids)

    def key(self, row: dict) -> str | None:
        canonical = self._tokens(row)
        return None if canonical is None else hashlib.sha256(
            compact({**self.identity, "row": canonical}).encode()).hexdigest()

    def get(self, key: str | None) -> dict | None:
        if not key:
            return None
        saved = self.db.execute("SELECT answer FROM rows WHERE key=?", (key,)).fetchone()
        if not saved:
            return None
        try:
            return self._ids(json.loads(saved[0]))
        except (ValueError, TypeError):
            return None

    def put(self, key: str | None, answer: dict):
        stored = self._tokens(answer) if key else None
        if stored is not None:
            self.db.execute("INSERT OR REPLACE INTO rows VALUES (?,?,?,?)", (key, compact(stored), self.run, time.time()))
            self.db.commit()

    def close(self):
        self.db.close()


class Agent:
    name = ""

    def __init__(self, ledger: Ledger):
        self._lock = RLock()
        self.ledger = ledger
        self.profile = profile_for(self.name)
        self.model = model_for(self.name)
        self.system = load_prompt(self.name)
        self.fingerprint = hashlib.sha256((self.model + self.system).encode()).hexdigest()
        self.spent = Counter()  # running totals for this agent instance
        self.failures = Counter()  # soft calls that returned no valid JSON, by label
        self.row_stats = {}  # per pass: rows sent, answered first time, recovered by the retry, still missing
        self.doubts = []  # items only counted elsewhere, listed for review in ontology/uncertain.json
        self.concept_labels = {}  # concept id -> label for this run; set by an agent to reuse row answers (RowCache)

    def doubt(self, kind: str, **item):
        """Record one uncertain or dropped item (kind names why) for ontology/uncertain.json."""
        kept = {k: v for k, v in item.items() if v not in (None, "", [], {})}
        self.__dict__.setdefault("doubts", []).append({"kind": kind, **kept})

    def call(self, user: str, item: str, system: str | None = None, label: str | None = None,
             soft: bool = False, cache_valid=None) -> dict:
        """One JSON call with one retry. soft=True returns {} on failure (the pass is skipped, the run goes on)."""
        system = system or self.system
        # Extraction already caches complete papers. Never include credentials in a cache record.
        request = {"version": 1, "revision": WORKFLOW_REVISION, "agent": self.name, "model": self.model,
                   "provider": self.profile["provider"], "base_url": self.profile["base_url"],
                   "temperature": TEMPERATURE, "request": self.profile.get("request", {}),
                   "system": system, "user": user}
        digest = hashlib.sha256(compact(request).encode()).hexdigest()
        cache = CACHE / "calls" / f"{digest}.json" if self.name != "extraction" and REUSE_ANSWERS else None
        if cache and cache.exists():
            try:
                saved = json.loads(cache.read_text(encoding="utf-8"))
                data = parse_json(saved["output"])
                if saved["request_hash"] == digest and isinstance(data, dict) and "properties" not in data \
                        and (cache_valid is None or cache_valid(data)):
                    self.ledger.log(self.name, item, self.model, llm.Usage(), cache_hit=True)
                    with self._lock, (self.ledger.path.parent / "calls.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"agent": self.name, "item": item, "ok": True, "cache_hit": True,
                                            "cache": str(cache), "request_hash": digest,
                                            "source_usage": saved["usage"], "source_run": saved.get("source_run"),
                                            "source_item": saved.get("source_item"), "output": saved["output"][:30000]},
                                           ensure_ascii=False) + "\n")
                    log(f"  {label or item}: reusing cached response (0 tokens)")
                    return data
            except (OSError, ValueError, KeyError, TypeError):
                pass  # corrupt or obsolete cache: obtain a fresh response
        for attempt in range(2):
            log(f"  {label or item}: {self.model}{' (retry: previous reply was not JSON)' if attempt else ''} ...", end="")
            text, usage = llm.chat(system, user, self.model, profile=self.profile)
            data = parse_json(text)
            if not isinstance(data, dict):
                data = None
            finish(f"{usage.latency_s:.1f}s, {usage.input_tokens:,} in / {usage.output_tokens:,} out"
                   + ("" if data is not None else ", NO VALID JSON"))
            self.ledger.log(self.name, item, self.model, usage, ok=data is not None, attempt=attempt)
            if self.name != "extraction":  # extraction keeps its own raw_calls per paper
                with self._lock, (self.ledger.path.parent / "calls.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"agent": self.name, "item": item, "attempt": attempt, "ok": data is not None,
                                        "request_hash": digest, "output": text[:30000]}, ensure_ascii=False) + "\n")
            with self._lock:
                self.spent.update(calls=1, input_tokens=usage.input_tokens, cached_tokens=usage.cached_tokens,
                                  output_tokens=usage.output_tokens, latency_s=usage.latency_s)
            if data is not None:
                if cache and data and "properties" not in data and (cache_valid is None or cache_valid(data)):
                    files.atomic_write(cache, json.dumps({"request_hash": digest, "model": self.model,
                                                         "source_run": self.ledger.path.parent.name, "source_item": item,
                                                         "created": time.time(), "usage": asdict(usage), "output": text},
                                                        ensure_ascii=False))
                return data
        if soft:
            with self._lock:
                self.failures[(label or item).split(" ")[0]] += 1
            log(f"  {label or item}: no valid JSON after 2 attempts; skipping this pass")
            return {}
        raise ValueError(f"{self.name}: no valid JSON for {item} after 2 attempts")

    def call_rows(self, rows: list[dict], system: str, item: str, field: str, value_key: str | None = None,
                  size: int = 25, label: str | None = None, stat: str | None = None, retries: int = 1) -> list[dict]:
        """Rows in batches; rows the model left out are sent again, up to retries times, each time in batches half
        the size of the last (at least 5). Returns one answer entry per answered row id; coverage counts accumulate
        in self.row_stats[stat or item] (recovered: by any retry; recovered_retryN: by retry N >= 2; reused: answered
        from an earlier run with the identical row, see RowCache). value_key may be a tuple of fields that must all
        be present."""
        if size < 1 or retries < 0:
            raise ValueError("Row batch size must be positive and retries must be nonnegative")
        ids, answers, answered = {str(r["id"]) for r in rows}, [], set()
        if len(ids) != len(rows):
            raise ValueError("Row ids must be unique within a task")
        needed = (value_key,) if isinstance(value_key, str) else tuple(value_key or ())
        value_key = needed[0] if needed else None  # the field read from {"k1": value} replies
        contract = (f"\n\nReturn actual values under {field!r}, not a JSON schema. Include every input id exactly once. "
                    + (f"Every row must include {' and '.join(map(repr, needed))}; an explicit empty string or list is "
                       "an answer, but an id without this field is incomplete. " if needed else "")
                    + "Use the task's stated fallback when unsure; never omit a row.")
        cache = RowCache(self, system + contract, field, list(needed)) \
            if REUSE_ANSWERS and getattr(self, "concept_labels", None) else None
        by_id = {str(r["id"]): r for r in rows}
        row_keys = {k: cache.key(r) for k, r in by_id.items()} if cache else {}
        audit = (self.ledger.path.parent / "rows.jsonl") if getattr(self, "ledger", None) else None
        audit_lines = []

        def keep(k: str, a: dict, source: str):
            answered.add(k)
            answers.append(a)
            if cache and source == "model":
                cache.put(row_keys.get(k), a)
            if audit:
                audit_lines.append(json.dumps({"pass": stat or item, "id": k, "label": by_id[k].get("label"),
                                               "key": row_keys.get(k), "source": source, "answer": a},
                                              ensure_ascii=False))

        def send(todo, n, tag):
            batches = -(-len(todo) // n)
            def batch(i):
                part = todo[i:i + n]
                part_ids = {str(r["id"]) for r in part}

                def valid(a):
                    return key(a.get("id")) in part_ids and all(f in a and a[f] is not None for f in needed)

                def complete(out):
                    entries = items(out, field, value_key)
                    return len(entries) == len(part_ids) and all(valid(a) for a in entries) \
                        and {key(a.get("id")) for a in entries} == part_ids

                out = self.call(f"Return one entry for each of these {len(part)} ids.\n" + compact(part),
                                item=f"{item}{tag}_{i // n + 1}", system=system + contract,
                                label=f"{label or item}{tag} {i // n + 1}/{batches}", soft=True, cache_valid=complete)
                return [a for a in items(out, field, value_key) if valid(a)]

            for entries in workers.ordered(batch, range(0, len(todo), n)):
                for a in entries:
                    k = key(a.get("id"))
                    if k not in answered:
                        keep(k, a, "model")

        reused = 0
        for k in by_id:
            got = cache.get(row_keys[k]) if cache else None
            if got is not None and key(got.get("id")) == k:
                keep(k, got, "reused")
                reused += 1
        if reused:
            log(f"  {label or item}: {reused} of {len(rows)} rows reused from earlier runs (identical rows)")
        try:
            send([r for r in rows if str(r["id"]) not in answered], size, "")
            first, by_round = len(answered), Counter()
            for n in range(1, retries + 1):
                missing = [r for r in rows if str(r["id"]) not in answered]
                if not missing:
                    break
                before = len(answered)
                send(missing, max(5, size // 2 ** n), "_retry" if n == 1 else f"_retry{n}")
                if n > 1:
                    by_round[f"recovered_retry{n}"] = len(answered) - before
        finally:
            if cache:
                cache.close()
            if audit and audit_lines:
                with self._lock, audit.open("a", encoding="utf-8") as f:
                    f.write("\n".join(audit_lines) + "\n")
        for r in rows:
            if str(r["id"]) not in answered:
                self.doubt("unanswered_row", step=stat or item, id=str(r["id"]), label=r.get("label"))
        s = self.row_stats.setdefault(stat or item, Counter())
        s.update(rows=len(rows), answered_first=first, recovered=len(answered) - first,
                 missing=len(rows) - len(answered), reused=reused, **by_round)
        return answers
