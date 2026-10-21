"""Extraction agent: one paper -> concepts, relations, causal edges, measurements, figure links.

Per section group (adjacent short sections packed, oversized ones split at sentence ends), with only the figures it
cites and the labels already found earlier in the paper:
- frontier tier: one combined call (prompts/extraction.md);
- local tier: one narrow call per pass - concepts first, then causal, relations and measurements, each given the
  section's numbered concept list so they refer to ids instead of inventing them (EXTRACTION_PASSES in config).
Every evidence quote is checked against the paper text (word 3-gram overlap) and marked verified or not.
Rows a model returns as plain lists (Gemma does this for long tables) are read in the schema's field order.
The LLM does the semantic work; mention counts, sections, id checks and figure citations are deterministic.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
import json
import re
import unicodedata
from collections import Counter

from src.agents.base import RESOURCES, Agent, compact, items, key, load_prompt, targets
from src.config import CACHE, EXTRACTION_PASSES, TEMPERATURE, tier
from src.tools import files, concept_quality
from src.tools.llm import Usage
from src.tools.pdf_parse import MENTION
from src.tools.progress import log

CAPTION_CHARS = 400
SECTION_PACK_CHARS = 6000  # adjacent short sections share a call, retaining their headings
KNOWN_LABELS = 80          # labels from earlier sections passed forward
EARLIER_IN_LIST = 40       # earlier-section concepts added to a later pass's numbered list
PASS_PROMPT = {"combined": "extraction", "concepts": "extraction_concepts", "causal": "extraction_causal",
               "relations": "extraction_relations", "measurements": "extraction_measurements"}
PASS_REFS = {"causal": ("cause", "effect"), "relations": ("s", "o"), "measurements": ("property", "entity", "concept")}
PROPERTY_TYPES = ("property", "quantity", "parameter")
EVIDENCE_WORDS = 3         # a quote shorter than this is no evidence: re-asked once, then flagged unevidenced
EVIDENCE_BATCH = 40
CODE_VERSION = "2026-10-20-tables-basis-v2"  # part of the cache key: bump when merge/finalize logic changes
BASES = ("measured", "simulated", "cited", "target")  # where a reported value comes from
TYPES = ("material", "device", "equipment", "process", "parameter", "phenomenon", "property", "quantity", "method",
         "defect", "condition", "information")
VERIFY_SHARE = 0.8         # share of an evidence quote's word 3-grams that must appear in the paper


def row_fields(schemas) -> dict[str, list[str]]:
    """Answer field -> its item fields in schema order (measurements -> property, entity, value, ...)."""
    fields = {}
    for name in schemas:
        props = json.loads((RESOURCES / "schemas" / f"{name}.json").read_text(encoding="utf-8"))["properties"]
        for field, spec in props.items():
            if spec.get("type") == "array" and isinstance(spec.get("items", {}).get("properties"), dict):
                fields.setdefault(field, list(spec["items"]["properties"]))
    return fields


def named(out, fields: dict) -> dict:
    """Rows a model returned as lists, read in schema field order (the last, optional field may be left off)."""
    if isinstance(out, dict):
        out = dict(out)  # raw_calls keeps the answer exactly as returned
        for name, order in fields.items():
            if isinstance(out.get(name), list):
                out[name] = [dict(zip(order, r)) if isinstance(r, list) and len(order) - 1 <= len(r) <= len(order) else r
                             for r in out[name]]
    return out


def _key(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def _type(value) -> str:
    """Map a free-text type onto the schema enum: the last enum word in a short answer ("process parameter" ->
    parameter), else blank."""
    words = re.findall(r"[a-z]+", str(value or "").lower())
    hits = [w for w in words if w in TYPES]
    return hits[-1] if hits and len(words) <= 4 else ""


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).lower())


def _grams(text: str) -> set:
    words = _words(text)
    return set(zip(words, words[1:], words[2:]))


def _found(quote: str, grams: set) -> bool:
    """At least VERIFY_SHARE of the quote's word 3-grams occur in the text (quotes with omissions: per segment)."""
    tri = [t for seg in re.split(r"\.\.\.|\u2026", quote) for ev in [_words(seg)] for t in zip(ev, ev[1:], ev[2:])]
    return bool(tri) and sum(t in grams for t in tri) / len(tri) >= VERIFY_SHARE


SECTION_KINDS = (("abstract", r"abstract|front matter"), ("conclusions", r"conclu|summary|outlook|future"),
                 ("results", r"result|discussion|analys|performance|evaluat|comparison"),
                 ("methods", r"method|experiment|material|procedure|fabricat|characteri|setup|model|simulat|design"),
                 ("introduction", r"intro|background|literature|related work|motivation|theory|overview"))


def section_kind(heading: str) -> str:
    """abstract, introduction, methods, results, conclusions or other, from a section heading."""
    return next((kind for kind, pattern in SECTION_KINDS if re.search(pattern, heading or "", re.I)), "other")


VALUE_TAIL = re.compile(r"(.*?\S)\s*(?:[<>=~\u2248\u2264\u2265]|\u00b1)\s*[-+]?\d[\d.,]*\s*[%\w\u00b0/\u00b5.-]{0,8}")


def _clean_label(label: str) -> str:
    """Leaked ids and values out of a label: 'n1 (Auger recombination)', 'n1: Auger recombination' -> 'Auger
    recombination'; 'n7_round_trip_efficiency' -> 'round trip efficiency'; 'front-side efficiency > 23%' ->
    'front-side efficiency' (the value belongs in a measurement, not in the concept's name)."""
    m = re.fullmatch(r"[cnf]\d+\s*(?:\((.+)\)|[:\-\u2013]\s*(.+))\s*", label.strip(), re.I)
    rest = (m.group(1) or m.group(2)).strip() if m else ""
    label = rest if rest and not re.fullmatch(r"(?:[cnf]\d+\W*)+", rest, re.I) else label.strip()
    if m := re.fullmatch(r"[cnf]\d+_([a-z0-9_]*[a-z][a-z0-9_]*)", label, re.I):
        label = m.group(1).replace("_", " ").strip()
    if (m := VALUE_TAIL.fullmatch(label)) and len(m.group(1)) >= 3:
        label = m.group(1).strip()
    return label


class ExtractionAgent(Agent):
    name = "extraction"
    fields: dict = {}  # answer field -> item field order (set from the pass schemas in __init__)

    def __init__(self, ledger):
        super().__init__(ledger)
        self.tier = tier(self.name)
        self.passes = EXTRACTION_PASSES[self.tier]
        self.prompts = {p: load_prompt(PASS_PROMPT[p]) for p in self.passes}
        self.fields = row_fields(PASS_PROMPT[p] for p in self.passes)
        self.evidence_prompt = load_prompt("extraction_evidence")
        self.fingerprint = hashlib.sha256(compact({"model": self.model, "tier": self.tier, "version": CODE_VERSION,
            "provider": self.profile["provider"], "base_url": self.profile["base_url"], "temperature": TEMPERATURE,
            "request": self.profile.get("request", {}), "pack_chars": SECTION_PACK_CHARS,
            "evidence_prompt": self.evidence_prompt, "prompts": self.prompts}).encode()).hexdigest()
        self.new_concepts = Counter()  # concepts added by the later passes, by pass
        self.evidence = Counter()  # quotes re-asked and filled

    def run(self, paper: dict) -> dict:
        chunks = self._chunks(paper)
        digest = hashlib.sha256((self.fingerprint + "".join(chunks)).encode()).hexdigest()[:16]
        cache = CACHE / "extraction" / f"{paper['key']}-{digest}.json"
        if cache.exists():
            self.ledger.log(self.name, paper["key"], self.model, Usage(), cache_hit=True)
            log("  reusing cached extraction (same text, prompt and model): 0 tokens")
            return {**concept_quality.quarantine(json.loads(cache.read_text(encoding="utf-8"))), "cache_hit": True}
        before, failed_before, new_before = Counter(self.spent), Counter(self.failures), Counter(self.new_concepts)
        evidence_before = Counter(self.evidence)
        parts, raw_calls = [], []
        for i, chunk in enumerate(chunks, 1):
            known = self._merge(parts)["concepts"] if parts else []
            known_text = ("CONCEPTS ALREADY FOUND (reuse these exact labels): "
                          + "; ".join(c["label"] for c in known[:KNOWN_LABELS]) + "\n") if known else ""
            where = f"section {i}/{len(chunks)} ({len(chunk):,} chars)"
            if self.passes == ["combined"]:
                out = self.call(known_text + chunk, item=paper["key"], system=self.prompts["combined"],
                                label=f"extract {where}", soft=True)
                raw_calls.append({"pass": "combined", "prompt": PASS_PROMPT["combined"],
                                  "input": known_text + chunk, "output": out})
                out = named(out, self.fields)
                out = concept_quality.quarantine(out)
                labels = {key(c.get("id")): c.get("label") for c in items(out, "concepts")}
                self._fill_evidence(chunk, out, ("relations", "causal", "measurements"), labels, paper["key"], where,
                                    raw_calls)
                parts.append(out)
            else:
                parts.append(self._multi_pass(chunk, known_text, known, where, paper["key"], raw_calls))
        result = self._finalize(self._merge(parts), paper)
        spent = self.spent - before
        result["n_chunks"] = len(chunks)
        result["extraction_tier"], result["extraction_passes"] = self.tier, self.passes
        result["checks"] = {"failed_calls": dict(self.failures - failed_before),
                            "new_concepts_by_pass": dict(self.new_concepts - new_before),
                            "evidence": dict(self.evidence - evidence_before), **result.pop("checks", {})}
        result["raw_calls"] = raw_calls  # exact model input/output per section, reusable as training data
        result["compute"] = {"model": self.model, **{k: round(v, 3) for k, v in spent.items()}}
        files.atomic_write(cache, json.dumps(result))
        return result

    def _multi_pass(self, chunk: str, known_text: str, known: list[dict], where: str, item: str,
                    raw_calls: list) -> dict:
        """Local tier: concepts first, then each other pass against the numbered concept list."""
        first = self.call(known_text + chunk, item=item, system=self.prompts["concepts"], label=f"concepts {where}",
                          soft=True)
        raw_calls.append({"pass": "concepts", "prompt": PASS_PROMPT["concepts"], "input": known_text + chunk,
                          "output": first})
        first = concept_quality.quarantine(first)
        listed, remap = [], {}
        for c in items(first, "concepts"):
            if isinstance(c.get("label"), str) and c["label"].strip():
                listed.append({**c, "id": f"c{len(listed) + 1}"})
                if key(c.get("id")):
                    remap[key(c.get("id"))] = listed[-1]["id"]
        section_labels, n_section = {_key(c["label"]) for c in listed}, len(listed)
        for c in known:
            if len(listed) >= n_section + EARLIER_IN_LIST:
                break
            if _key(c["label"]) not in section_labels:
                listed.append({"id": f"c{len(listed) + 1}", "label": c["label"], "type": c.get("type", ""),
                               "synonyms": c.get("synonyms", [])})
        part = {"concepts": list(listed), "quality_review": first.get("quality_review", []),
                "figures": [{**f, "concepts": [remap[c] for c in targets(f.get("concepts")) if c in remap]}
                            for f in items(first, "figures")]}
        concept_list = "CONCEPTS:\n" + "\n".join(f"{c['id']}: {c['label']} ({c.get('type', '')})" for c in listed)
        for name in self.passes:
            if name == "concepts":
                continue
            prompt_in = f"{concept_list}\n{chunk}"
            out = self.call(prompt_in, item=item, system=self.prompts[name], label=f"{name} {where}", soft=True)
            raw_calls.append({"pass": name, "prompt": PASS_PROMPT[name], "input": prompt_in, "output": out})
            out = named(out, self.fields)
            out = concept_quality.quarantine({**out, "quality_review": part["quality_review"]})
            part["quality_review"] = out["quality_review"]
            labels = {c["id"]: c["label"] for c in listed} | {
                key(nc.get("id")): nc.get("label") for nc in items(out, "new_concepts") if key(nc.get("id"))}
            self._fill_evidence(chunk, out, (name,), labels, item, where, raw_calls)
            new_ids = {}
            for nc in items(out, "new_concepts"):  # ids are per pass; make them unique before merging
                if key(nc.get("id")) and isinstance(nc.get("label"), str):
                    new_ids[key(nc.get("id"))] = f"{name}:{key(nc.get('id'))}"
                    part["concepts"].append({**nc, "id": new_ids[key(nc.get("id"))]})
                    self.new_concepts[name] += 1
            part[name] = [{**r, **{f: new_ids.get(key(r.get(f)), r.get(f)) for f in PASS_REFS[name]}}
                          for r in items(out, name)]
        return part

    def _fill_evidence(self, chunk: str, out: dict, kinds: tuple, labels: dict, item: str, where: str,
                       raw_calls: list):
        """Items returned without a usable quote, or with one not found in the section, get one more call that asks
        only for their quotes. A new quote replaces an unfound one only when it is found."""
        rows, refs, grams = [], {}, _grams(chunk)
        for kind in kinds:
            for i, r in enumerate(items(out, kind), 1):
                quote = str(r.get("evidence") or "")
                if len(_words(quote)) >= EVIDENCE_WORDS and _found(quote, grams):
                    continue
                name = lambda f: str(labels.get(key(r.get(f))) or r.get(f) or "")
                claim = (f"{name('property') or name('concept')} = {r.get('value', '')} {r.get('unit') or ''}"
                         if kind == "measurements" else
                         f"{name('cause')} {r.get('polarity', '')} {name('effect')}" if kind == "causal" else
                         f"{name('s')} {str(r.get('p', '')).replace('_', ' ')} {name('o')}")
                rid = f"{kind[0]}{i}"
                rows.append({"id": rid, "claim": claim.strip(),
                             **({"not_found": quote[:200]} if len(_words(quote)) >= EVIDENCE_WORDS else {})})
                refs[rid] = r
        if not rows:
            return
        self.evidence["asked"] += len(rows)
        self.evidence["asked_unfound"] += sum("not_found" in r for r in rows)
        for i in range(0, len(rows), EVIDENCE_BATCH):
            user = f"SECTION\n{chunk}\n\nCLAIMS\n{compact(rows[i:i + EVIDENCE_BATCH])}"
            out2 = self.call(user, item=item, system=self.evidence_prompt, label=f"evidence {where}", soft=True)
            raw_calls.append({"pass": "evidence", "prompt": "extraction_evidence", "input": user, "output": out2})
            for a in items(out2, "quotes", "evidence"):
                r, quote = refs.get(key(a.get("id"))), str(a.get("evidence") or "").strip()
                if r is None or len(_words(quote)) < EVIDENCE_WORDS:
                    continue
                unfound = len(_words(str(r.get("evidence") or ""))) >= EVIDENCE_WORDS
                if not unfound or _found(quote, grams):
                    r["evidence"] = quote
                    self.evidence["refound" if unfound else "filled"] += 1

    def _chunks(self, paper: dict) -> list[str]:
        """Pack adjacent short sections; keep long sections separate and split them without dropping text."""
        title = f"TITLE: {paper.get('title', '')}\n"
        captions = {f["id"]: f["caption"][:CAPTION_CHARS] for f in paper["figures"]}
        # Leave space for title, captions, and the concept list added by the local passes.
        maximum = self.profile["max_input_chars"]
        limit = maximum - len(title) - len("FIGURES:\nTEXT:\n") - sum(
            len(f"{fid}: {caption}\n") for fid, caption in captions.items()) - min(4096, maximum // 4)
        if limit < 100:
            raise ValueError("Extraction input budget is too small for the title, captions, and concept list")
        pieces = []
        for s in paper["sections"]:
            heading = f"## {s['heading']}\n"
            available = limit - len(heading) - 1
            if available < 1:
                raise ValueError("Section heading exceeds the extraction input budget")
            text = s["text"]
            while len(text) > available:  # cut at a sentence end or a table row, not inside a row
                cut = max(text.rfind(". ", 0, available), text.rfind("\n", 0, available))
                cut = cut + 1 if cut > available // 2 else available
                pieces.append(heading + text[:cut].strip() + "\n")
                text = text[cut:]
            pieces.append(heading + text.strip() + "\n")
        bodies, body = [], ""
        pack = min(SECTION_PACK_CHARS, limit)
        for piece in pieces:
            if body and len(body) + len(piece) > pack:
                bodies.append(body)
                body = ""
            body += piece
        if body:
            bodies.append(body)
        chunks = []
        for body in bodies:
            cited = sorted({f"F{n}" for m in MENTION.finditer(body) for n in m.groups() if n} & set(captions),
                           key=lambda f: int(f[1:]))
            figures = "FIGURES:\n" + "\n".join(f"{f}: {captions[f]}" for f in cited) + "\n" if cited else ""
            chunks.append(f"{title}{figures}TEXT:\n{body}")
        return chunks

    @staticmethod
    def _merge(parts: list[dict]) -> dict:
        """Merge section answers into one paper graph. Relation/causal/measurement ends are resolved by concept id,
        or - since small models often write the phrase instead of the id - by label or synonym, by the longest known
        concept named inside the phrase, or (short phrases only) as a new concept taken from the text."""
        parts = [concept_quality.quarantine(part) for part in parts]
        review = [row for part in parts for row in part.get("quality_review", [])]
        concepts: dict[str, dict] = {}
        rels, causal, figs, measures = [], [], {}, []
        stats, unresolved = Counter(), []

        def add(label: str, ctype: str = "", definition: str = "", synonyms=(), figures=()) -> str:
            label = _clean_label(label)
            k = _key(label)
            if k not in concepts:
                concepts[k] = {"id": f"c{len(concepts) + 1}", "label": label, "type": "",
                               "definition": definition, "synonyms": [], "figures": []}
            m = concepts[k]
            m["type"] = m["type"] or _type(ctype)
            m["synonyms"] = sorted(set(m["synonyms"]) | {x for x in synonyms if isinstance(x, str)})
            m["figures"] = sorted(set(m["figures"]) | {x for x in figures if isinstance(x, str)})
            if len(definition) > len(m["definition"]):
                m["definition"] = definition
            return m["id"]

        def names() -> dict:
            out = {}
            for k, m in concepts.items():
                out.setdefault(k, m["id"])
                for syn in m["synonyms"]:
                    out.setdefault(_key(syn), m["id"])
            return out

        def resolve(ref, local: dict, kind: str) -> str | None:
            if key(ref) in local:
                return local[key(ref)]
            phrase = key(ref) if not isinstance(ref, str) else ref.strip()
            if not phrase:
                return None
            known = names()
            text = _key(re.sub(r"\([^)]*\)", " ", phrase))
            if _key(phrase) in known or text in known:
                stats[f"{kind}_by_label"] += 1
                return known.get(_key(phrase)) or known[text]
            inside = [n for n in known if len(n) >= 5 and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text)]
            if inside:
                stats[f"{kind}_by_contained_label"] += 1
                return known[max(inside, key=len)]
            if 1 <= len(text.split()) <= 6 and not re.fullmatch(r"(?:[cnf]\d+\W*)+", text):  # an unknown id, not a phrase
                stats[f"{kind}_new_concept"] += 1
                return add(phrase, "phenomenon" if kind == "causal" else "")
            stats[f"{kind}_unresolved"] += 1
            if phrase not in [u["ref"] for u in unresolved]:
                unresolved.append({"end_of": kind, "ref": phrase[:160]})
            return None

        for part in parts:
            local = {}
            for c in items(part, "concepts"):
                if not isinstance(c.get("label"), str) or not _key(c["label"]):
                    continue
                cid = add(c["label"], c.get("type", ""), c.get("definition", "") or "",
                          c.get("synonyms") or [], c.get("figures") or [])
                if key(c.get("id")):
                    local[key(c.get("id"))] = cid
            for r in items(part, "relations"):
                s_, o_ = resolve(r.get("s"), local, "relation"), resolve(r.get("o"), local, "relation")
                if s_ and o_ and s_ != o_:
                    rels.append({**r, "s": s_, "o": o_})
            for r in items(part, "causal") + items(part, "causal_statements") + items(part, "causal_claims"):
                s_, o_ = resolve(r.get("cause"), local, "causal"), resolve(r.get("effect"), local, "causal")
                if s_ and o_ and s_ != o_:
                    causal.append({**r, "cause": s_, "effect": o_})
            for m in items(part, "measurements"):
                if not str(m.get("value", "")).strip():
                    continue
                prop = m.get("property") if m.get("property") is not None else m.get("concept")
                pid = resolve(prop, local, "measurement") if prop else None
                eid = resolve(m.get("entity"), local, "measurement_entity") if m.get("entity") else None
                type_of = {c["id"]: c["type"] for c in concepts.values()}
                if pid and type_of.get(pid) not in PROPERTY_TYPES and not eid:
                    pid, eid = None, pid  # the value was attached to the thing measured, not to a property
                if pid or eid:
                    basis = str(m.get("basis") or "").strip().lower()
                    measures.append({"concept": pid or eid, "entity": (eid or "") if pid else "", "property_missing": not pid,
                                     **{k: str(m.get(k, "") or "").strip()
                                        for k in ("value", "unit", "condition", "evidence")},
                                     "basis": basis if basis in BASES else ""})
            for f in items(part, "figures"):
                if not key(f.get("id")):
                    continue
                entry = figs.setdefault(key(f.get("id")), {"concepts": set(), "shows": ""})
                entry["concepts"] |= {cid for c in targets(f.get("concepts")) if (cid := local.get(c))}
                entry["shows"] = entry["shows"] or f.get("shows", "")
        return {"concepts": list(concepts.values()), "relations": _dedupe(rels, ("s", "p", "o")),
                "causal": _dedupe(causal, ("cause", "effect", "polarity")),
                "measurements": _dedupe(measures, ("concept", "entity", "value", "unit", "condition")),
                "figure_links": {k: {"concepts": sorted(v["concepts"]), "shows": v["shows"]} for k, v in figs.items()},
                "resolution": dict(stats), "unresolved_ends": unresolved, "quality_review": review}

    @staticmethod
    def _finalize(x: dict, paper: dict) -> dict:
        x = concept_quality.quarantine(x)
        grams = _grams(" ".join(s["text"] for s in paper["sections"]))
        by_section = [(s["heading"], _grams(s["text"])) for s in paper["sections"]]
        verification = {}
        for kind in ("relations", "causal", "measurements"):
            for r in x[kind]:
                evidence = str(r.get("evidence", "") or "")
                r["verified"] = _found(evidence, grams)
                quote = _grams(evidence)
                if quote and by_section:  # the section that holds most of the quote
                    heading, found = max(((h, len(quote & g)) for h, g in by_section), key=lambda hg: hg[1])
                    if found:
                        r["section"], r["section_kind"] = heading, section_kind(heading)
                r["evidence_status"] = ("unevidenced" if len(_words(evidence)) < EVIDENCE_WORDS else
                                        "verified" if r["verified"] else "unverified")
            verification[kind] = {"items": len(x[kind]), "verified": sum(r["verified"] for r in x[kind]),
                                  "unevidenced": sum(r["evidence_status"] == "unevidenced" for r in x[kind])}
        types = {c["id"]: c.get("type", "") for c in x["concepts"]}
        checks = {"measurements_on_non_property": sum(
            1 for m in x["measurements"] if types.get(m["concept"]) not in PROPERTY_TYPES),
                  "measurements_property_missing": sum(1 for m in x["measurements"] if m.get("property_missing")),
                  "pairs_both_relation_and_causal": len({(r["s"], r["o"]) for r in x["relations"]}
                                                        & {(r["cause"], r["effect"]) for r in x["causal"]})}
        fig_ids = {f["id"] for f in paper["figures"]}
        for c in x["concepts"]:
            terms = {c["label"], *c["synonyms"]}
            pat = re.compile("|".join(rf"(?<!\w){re.escape(t)}s?(?!\w)" for t in terms if t), re.I)
            per_section = {s["heading"]: len(pat.findall(s["text"])) for s in paper["sections"]}
            c["mentions"] = sum(per_section.values())
            c["sections"] = [h for h, n in per_section.items() if n]
            c["figures"] = [f for f in c["figures"] if f in fig_ids]
        figures = []
        for f in paper["figures"]:
            link = x["figure_links"].get(f["id"], {})
            figures.append({**f, "concepts": link.get("concepts", []), "shows": link.get("shows", "")})
        return {"concepts": x["concepts"], "relations": x["relations"], "causal": x["causal"],
                "measurements": x["measurements"], "figures": figures, "resolution": x.get("resolution", {}),
                "unresolved_ends": x.get("unresolved_ends", []), "verification": verification, "checks": {**x.get("checks", {}), **checks}, "quality_review": x.get("quality_review", [])}


def _dedupe(rows: list[dict], keys: tuple) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = json.dumps([r.get(x) for x in keys], sort_keys=True, default=str)  # values may be dicts from the model
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
