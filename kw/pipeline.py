# -*- coding: utf-8 -*-
"""
The pipeline - the single ordered runner. Implements the spec exactly:

    INPUT(mode) -> CONCEPTS -> MINE(LLM + REBEL) -> CONSOLIDATE
                -> ONTOLOGY -> JSON-LD -> DIAGRAM -> LoRA

Ordering invariants enforced here: JSON-LD, diagram, and LoRA run only AFTER the
ontology is built. REBEL runs together with the LLM during mining.
"""
from __future__ import annotations

import os
import re
import sys
import glob
import time
import logging
import pandas as pd

from kw import config, zotero, extract, rebel, store, tagger      # preprocessing
from kw import drawio, ontology, lora, relations, merge, mdsonto  # ontology engineering
from kw import validate  # package-qualified (avoids the PyPI 'validate' name collision)

# Basic logging: configure the root logger once (safe no-op if the host app
# already configured it, e.g. Spyder). Timestamps make the per-step timing readable.
log = logging.getLogger("kw.pipeline")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

# Quiet noisy third-party loggers (httpx request lines, HuggingFace Hub chatter,
# model-loader info) so the pipeline's own output + step timing stay readable.
# 'openai'/'openai._base_client' emit "Retrying request to /chat/completions in
# N seconds" at INFO on every transient retry — bumped to WARNING so they don't
# bloat the per-run log (kw.llm already prints a concise [retry x/y] line).
for _noisy in ("httpx", "httpcore", "urllib3", "huggingface_hub", "filelock",
               "sentence_transformers", "transformers", "datasets",
               "openai", "openai._base_client"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# Write a per-collection log file (capturing stdout prints + log records). Off => console only.
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() != 'false'


def _safe_portal_name(text: str, maxlen: int = 100) -> str:
    """OntoPortal-safe ontology name from the inferred domain: drop the
    '(key categories ...)' tail and any disallowed punctuation / control chars,
    collapse whitespace, and cap length. Used so the portal 'name' validates."""
    s = str(text or "").split("(key categories")[0]
    s = re.sub(r"[<>\r\n\t]", " ", s)
    s = re.sub(r"[^A-Za-z0-9 ,.\-/&]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen].strip() or "MDS Ontology"


# Words that carry no meaning in an acronym.
_ACRONYM_STOPWORDS = {
    "and", "or", "of", "the", "in", "a", "an", "for", "to", "with", "on",
    "by", "at", "from", "into", "review", "study", "studies",
}


def _portal_acronym(raw: str, max_len: int = 15) -> str:
    """Derive an OntoPortal-safe acronym from a collection slug/name.

    The portal rejects long, truncated acronyms (e.g. 'CHARACTERIZA'). We want one
    of two valid forms:
      * a clean token shorter than 16 characters (used as-is), or
      * an initialism of the significant words, suffixed with '_onto'
        (e.g. 'photovoltaics' -> 'pv_onto').

    Always returns lowercase [a-z0-9_], starts with a letter, <= max_len chars.
    """
    # Normalise to space-separated alphanumeric words.
    words = [w for w in re.split(r"[^A-Za-z0-9]+", str(raw or "")) if w]
    compact = "_".join(words).lower()

    # Short enough already: use the cleaned slug verbatim.
    if compact and len(compact) < 16:
        acr = compact
    else:
        meaningful = [w for w in words if w.lower() not in _ACRONYM_STOPWORDS] or words
        initials = "".join(w[0] for w in meaningful).lower()[: max_len - len("_onto")]
        acr = f"{initials}_onto" if initials else "mds_onto"

    # OntoPortal acronyms must start with a letter.
    if acr and acr[0].isdigit():
        acr = f"o{acr}"
    return acr[:max_len] or "mds_onto"


class _StepTimer:
    """Minimal per-step timer (stdlib only): logs seconds elapsed since the last
    mark, and a TOTAL at the end."""
    def __init__(self):
        self._start = self._last = time.perf_counter()

    def mark(self, label: str) -> None:
        now = time.perf_counter()
        log.info("step %-10s %7.1fs", label, now - self._last)
        self._last = now

    def total(self) -> None:
        log.info("step %-10s %7.1fs", "TOTAL", time.perf_counter() - self._start)


class _Tee:
    """Write to several streams at once (e.g. the real console + a log file)."""
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


def _open_run_log(out_dir: str, slug: str) -> dict:
    """Tee stdout to outputs/<slug>/<slug>.log AND attach a logging handler to the
    same file, so BOTH print() output and log records are captured. Windows-safe name."""
    path = os.path.join(out_dir, f'{store.safe_filename(slug)}.log')
    fh = open(path, 'a', encoding='utf-8')
    old_stdout = sys.stdout
    sys.stdout = _Tee(old_stdout, fh)                 # prints -> console + file
    handler = logging.StreamHandler(fh)               # log records -> same file
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    print(f'[log] run log -> {path}')
    return {'path': path, 'file': fh, 'stdout': old_stdout, 'handler': handler}


def _close_run_log(state: dict | None) -> None:
    if not state:
        return
    logging.getLogger().removeHandler(state['handler'])
    try:
        state['handler'].close()
    except Exception:
        pass
    sys.stdout = state['stdout']                       # restore (important for batch runs)
    try:
        state['file'].close()
    except Exception:
        pass


def run(collection_id: str,
        concepts_csv: str | None = None,
        outputs_dir: str | None = None,
        emit_diagram: bool = True,
        do_lora: bool = True,
        limit: int | None = None,
        do_rebel: bool = True,
        emit_visual: bool = True,
        top_n: int | None = None,
        min_relevance: float | None = None,
        max_concepts: int | None = None) -> dict:
    outputs_dir   = outputs_dir or config.OUTPUTS_DIR
    # Dials: fall back to config defaults when not overridden by the caller/CLI.
    top_n         = config.TOP_N_PER_PAPER if top_n is None else top_n
    min_relevance = config.MIN_RELEVANCE   if min_relevance is None else min_relevance
    max_concepts  = config.MAX_CONCEPTS    if max_concepts is None else max_concepts
    timer = _StepTimer()

    # --- Step 0: resolve names + output dir (needed before the log opens) ---
    coll_map        = zotero.get_collection_map()
    id_to_name      = {v: k for k, v in coll_map.items()}
    collection_name = id_to_name.get(collection_id, collection_id)
    domain          = collection_name.lower().replace(' ', '_')
    slug            = store.collection_slug(collection_name)
    mode            = 'supervised' if concepts_csv else 'unsupervised'
    out_dir  = os.path.join(outputs_dir, slug)
    os.makedirs(out_dir, exist_ok=True)
    prefix   = store.make_filename(collection_name)
    ckpt_dir = os.path.join(out_dir, '.checkpoints') if config.USE_CHECKPOINT else None

    _logstate = _open_run_log(out_dir, slug) if LOG_TO_FILE else None
    try:
        log.info("run start: collection %r (%s) | model %s", collection_name, collection_id, config.MODEL)
        print(f'\n[{mode}] collection "{collection_name}" ({collection_id}) | model {config.MODEL}')
        print(f'[dials] top_n={top_n} min_relevance={min_relevance} '
              f'max_concepts={max_concepts or "uncapped"} limit={limit or "all"}')
        print(rebel.gpu_banner())

        papers = zotero.get_collection_with_text(collection_id, limit=limit)
        print(f'Loaded {len(papers)} papers.' + (f' (limited to {limit})' if limit else ''))
        no_text = [p['title'] for p in papers.values() if not p.get('full_text')]
        if no_text:
            print(f'[input] {len(no_text)} paper(s) had no extractable PDF text (abstract only).')
        if config.LORA_ADAPTER_PATH:
            print(f'[lora] extraction adapter configured: {config.LORA_ADAPTER_PATH}')
        timer.mark('input')

        # --- Step 1: concepts --------------------------------------------------
        domain_hint = ''
        if concepts_csv:                                   # supervised - skip extraction
            concept_list  = store.load_concept_list(concepts_csv)
            concept_table = None
            print(f'[concepts] supervised: {len(concept_list)} from {concepts_csv}')
        else:                                              # unsupervised - from abstracts
            print('[concepts] Step 1: extracting from abstracts...')
            domain_hint = extract.infer_domain_context(papers)   # unsupervised corpus framing
            concept_table = extract.build_concept_table(papers, top_n=top_n,
                                                        min_relevance=min_relevance,
                                                        domain_hint=domain_hint)
            concept_list  = extract.normalize_concept_list(concept_table.all_canonicals,
                                                           max_concepts=max_concepts,
                                                           domain_hint=domain_hint)
            print(f'[concepts] normalized to {len(concept_list)}')
        timer.mark('concepts')

        # --- Step 2: mine (LLM + REBEL together) -------------------------------
        print('[mine] Step 2: full-text mining (LLM) + REBEL triples...')
        schema_rows = extract.build_schema_rows(papers, concept_list, domain,
                                                checkpoint_dir=ckpt_dir)
        timer.mark('mine.llm')
        triples     = rebel.extract_corpus(papers) if do_rebel else []   # safe no-op if absent
        timer.mark('mine.rebel')

        # --- Step 3: consolidate - normalize predicates + resolve entities -----
        merge_stats = None
        rel_cov     = None
        if triples:
            relations.normalize_triples(triples)           # T3.2 predicate -> mds vocab
            rel_cov = relations.coverage(triples)
            if config.MERGE_REBEL:
                merge.resolve(triples, concept_list)        # T3.1 entity resolution
                merge_stats = merge.stats(triples)
        extra = ''
        if triples and merge_stats:
            extra = f' (rel-vocab {rel_cov}, resolved {merge_stats["resolution_rate"]})'
        print(f'[mine] {len(schema_rows)} schema rows, {len(triples)} REBEL triples{extra}')
        timer.mark('mine.consolidate')

        # --- persist mined data (the CSV handoff the emitter consumes) ---------
        if concept_table and concept_table.rows:
            store.save_concepts_csv(concept_table, os.path.join(out_dir, f'concepts_{prefix}'))
        schema_path = os.path.join(out_dir, f'schema_{prefix}')
        store.save_schema_csv(schema_rows, concept_list, schema_path)

        # REBEL triples become part of the GraphDB repo (relations as stated in the text)
        triples_files = None
        if triples:
            triples_files = rebel.save_triples(triples, out_dir, prefix, ns=config.MDS_NS)
            print(f'[mine] REBEL triples -> {triples_files["jsonld"]}')

        timer.mark('mine.persist')

        # --- MDS-Onto grounding: resolve concepts to real terms (no-op unless GROUND_MDSONTO) ---
        mds_matches = mdsonto.resolve_concepts(concept_list)
        if mds_matches:
            mdsonto.write_csv(mds_matches, os.path.join(out_dir, f'mdsonto_{prefix}'))
            print(f'[ground] MDS-Onto: matched {len(mds_matches)}/{len(concept_list)} concepts')
        timer.mark('mine.ground')

        # --- Step 4 -> 5: ONTOLOGY then JSON-LD (ordered) ----------------------
        print('[ontology] Step 4: OWL 2 TTL, then Step 5: JSON-LD (GraphDB repo)...')
        ontology.process_schema_file(schema_path=schema_path, outdir=outputs_dir, ttl_map={})
        ttls = sorted(glob.glob(os.path.join(out_dir, '*_onto.ttl')), key=os.path.getmtime)
        ttl_path = ttls[-1] if ttls else None
        timer.mark('ontology')

        # --- validation gate ---------------------------------------------------
        # Runs every check (required + advisory), writes a detailed per-run
        # report, and decides whether the MDS-Onto upload is allowed. The run
        # always continues to produce local artifacts; only the upload is gated.
        report = None
        if ttl_path:
            report = validate.evaluate(ttl_path)
            validate.write_report(report, out_dir, collection=collection_name)
            verdict = 'PASS' if report['gate_passed'] else 'FAIL'
            for c in report['checks']:
                print(f'  [validate] {c["name"]:<10} {c["severity"]:<8} '
                      f'{c["status"]:<5} {c["summary"]}')
            print(f'[validate] gate {verdict} '
                  f'(required: {", ".join(report["required_checks"]) or "none"}) '
                  f'-> report {report.get("report_md")}')
            if report['required_failed']:
                print(f'[validate] required checks failing: '
                      f'{", ".join(report["required_failed"])}')

        # --- OntoPortal submission (runs ONLY after the gate passes) -----------
        if ttl_path and report and config.SUBMIT_TO_PORTAL:
            if not report['gate_passed']:
                print('[portal] upload BLOCKED — validation gate failed '
                      f'({", ".join(report["required_failed"])}). '
                      'See validation_report.md; fix and re-run.')
            else:
                acronym = config.PORTAL_ONTOLOGY_ACRONYM or _portal_acronym(slug)
                # Succinct, portal-safe name from the inferred domain (falls back to collection).
                name = config.PORTAL_ONTOLOGY_NAME or _safe_portal_name(domain_hint or collection_name)
                try:
                    sub = mdsonto.submit_to_portal(
                        ttl_path, acronym, name,
                        contact_name=config.PORTAL_CONTACT_NAME,
                        contact_email=config.PORTAL_CONTACT_EMAIL,
                    )
                    print(f'[portal] submitted -> {sub.get("submission_url")}')
                except Exception as exc:
                    print(f'[portal] submission failed (non-fatal): {exc}')
        timer.mark('validate')

        # --- Step 5b: DIAGRAM (cemento draw.io) --------------------------------
        diagram_path = enriched_path = None
        if emit_diagram:
            print('[diagram] tagging concepts + building cemento draw.io...')
            cdf = pd.DataFrame({'concept': concept_list})
            cdf = tagger.tag_concepts(cdf)
            enriched_path = os.path.join(out_dir, f'enriched_{prefix}')
            cdf.to_csv(enriched_path, index=False)
            mx = drawio.build_drawio_xml(cdf, page_title=collection_name)
            drawio.add_template_pages(mx)                  # embed MDS-Onto + Cemento palettes
            diagram_path = os.path.join(out_dir, 'diagram_' + prefix.replace('.csv', '.drawio'))
            with open(diagram_path, 'w', encoding='utf-8') as fh:
                fh.write(drawio.serialize_drawio(mx))
            print(f'[diagram] {diagram_path}')
        timer.mark('diagram')

        # --- Step 6: LoRA (only after the ontology) ----------------------------
        lora_result = None
        if do_lora and ttl_path:
            print('[lora] Step 6: fine-tune on final ontology terms...')
            lora_result = lora.finetune(concept_list, ttl_path,
                                        schema_path=schema_path, papers=papers)
        timer.mark('lora')

        # --- Step 7: VISUAL + BENCHMARK (last; never allowed to break the run) --
        visual = None
        all_jsonld = os.path.join(out_dir, 'all.jsonld')
        if emit_visual and config.EMIT_VISUAL:
            try:
                from kw import visualize           # lazy: keeps networkx/pyvis optional
                print('[visual] Step 7: interactive graph + benchmark...')
                visual = visualize.run_for_pipeline(
                    all_jsonld, out_dir, collection=collection_name,
                    with_values=config.VISUAL_WITH_VALUES,
                    benchmark_csv=config.BENCHMARK_CSV,
                    inferred_domain=domain_hint)
            except Exception as exc:                # noqa: BLE001
                print(f'[visual] skipped (non-fatal): {exc}')
        timer.mark('visual')
        timer.total()

        print(f'\nDone - GraphDB repo + diagram in {out_dir}')
        return {
            'collection': collection_name, 'mode': mode, 'out_dir': out_dir,
            'concepts': concept_list, 'schema_path': schema_path,
            'n_triples': len(triples), 'rebel_triples': triples_files,
            'ttl': ttl_path, 'all_jsonld': all_jsonld,
            'enriched': enriched_path, 'diagram': diagram_path,
            'validation': report, 'lora': lora_result,
            'relation_coverage': rel_cov, 'merge_stats': merge_stats,
            'lora_adapter': config.LORA_ADAPTER_PATH or None,
            'visual': visual,
            'log': _logstate['path'] if _logstate else None,
            'dials': {'top_n': top_n, 'min_relevance': min_relevance,
                      'max_concepts': max_concepts, 'limit': limit},
        }
    finally:
        _close_run_log(_logstate)
