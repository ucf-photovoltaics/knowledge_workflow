"""Append-only compute ledger: one JSONL row per LLM call (or cache hit), summarized per item or agent."""
import json
import time
from dataclasses import asdict
from pathlib import Path

from src.config import PRICES
from src.tools.llm import Usage

SUMS = ("calls", "input_tokens", "cached_tokens", "output_tokens", "latency_s", "cost_usd")


def cost(u: Usage):
    p_in, p_out = PRICES["input"], PRICES["output"]
    if p_in is None or p_out is None:
        return None
    p_cached = PRICES["cached_input"] if PRICES["cached_input"] is not None else p_in
    fresh = u.input_tokens - u.cached_tokens
    return round((fresh * p_in + u.cached_tokens * p_cached + u.output_tokens * p_out) / 1e6, 6)


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, agent: str, item: str, model: str, usage: Usage, ok=True, attempt=0, cache_hit=False):
        row = {"ts": time.time(), "agent": agent, "item": item, "model": model, **asdict(usage),
               "cost_usd": cost(usage), "ok": ok, "attempt": attempt, "cache_hit": cache_hit}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def summary(self, by: str = "item") -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in self.rows():
            s = out.setdefault(r[by], {k: 0 for k in SUMS} | {"cache_hits": 0})
            s["cache_hits"] += r["cache_hit"]
            if r["cache_hit"]:
                continue
            s["calls"] += 1
            for k in SUMS[1:]:
                s[k] += r[k] or 0
        for s in out.values():
            s["latency_s"] = round(s["latency_s"], 3)
            s["cost_usd"] = round(s["cost_usd"], 6)
        return out
