# Cleanup & Structural Review — 2026-06-24

A cleanup, structural review, and documentation refresh of the `knowledge_workflow`
repository (branch `visuals`). This records what was changed, what was found, and the
decisions left to you.

## 1. Summary

The codebase is in good shape: it's a single, coherent `kw/` package with one ordered
pipeline, clear per-module responsibilities, env-driven config, and graceful degradation
for optional stages. The main problems were **documentation drift** (docs described an
older versioned-script design that no longer exists) and **accumulated cruft** at the
repo root. Both are addressed below. No pipeline logic was changed.

## 2. Changes made

### Git
- Removed the stale `.git/index.lock` left by an interrupted git process — `git` works
  again. (No repo content touched.)

### Files deleted (cruft / exact duplicates)
| Path | Why |
|------|-----|
| `__main__.py` (repo root) | Byte-for-byte duplicate of `kw/__main__.py`; the package is run via `python -m kw`. |
| `shiny/_explorer_test.py` | Byte-for-byte duplicate of `shiny/explorer.py`. |
| `auto_ps.txt` | Scratch Windows batch one-liner with collection keys. |
| `run_test.py`, `mdsonto_test.py`, `rebel_test.py` | Root-level smoke scripts (removed at your request). _Note: `run_test.py` was later restored as a one-paper smoke test._ |
| all `__pycache__/` (outside `.venv`/`.git`) | Regenerated build artifacts. |

### Code tidying (no behavior change)
Removed 6 unused imports flagged by `ruff` (F401), verified by recompiling each file:
- `kw/drawio.py` — `STUDY_STAGES`, `SUPPLY_CHAIN_LEVELS`
- `kw/graphview.py` — `normalize_stage`
- `kw/merge.py` — `MERGE_SIM_THRESHOLD`
- `kw/visualize.py` — `glob`
- `scripts/publish.py` — `pathlib.Path`

`ruff` found **no undefined names (F821)**, no redefinitions, and no unused-variable
issues — i.e. no obvious latent bugs surfaced by static analysis.

### Documentation
- **`docs/ARCHITECTURE.md` — rewritten.** It described a defunct V1–V4 script world,
  referenced nonexistent `V3_GUIDE.md`/`V4_GUIDE.md`, and **contained a hardcoded
  Zotero API key in plaintext** (see §4). It now documents the current `kw` package:
  corpus contract, full module map, the ordered pipeline (incl. Step 7), namespace
  registry, config model, and output layout.
- **`docs/PROCESS.md`** — added Step 7 (visual + benchmark), fleshed out Step 3
  (relation normalization, entity resolution, MDS-Onto grounding), updated the
  deliverables table.
- **`docs/USAGE_GUIDE.md`** — corrected stale env defaults (`COLLECTION_ID`,
  `TOP_N_PER_PAPER`, `RATE_LIMIT_DELAY`), expanded the variable reference to cover the
  current `config.py` (chunking, mining workers, validation toggles, OntoPortal
  submission, etc.), added `--no-visual`, and fixed the "LoRA is a stub" line (LoRA is
  implemented; it's dataset-only without a GPU).
- **`kw/README.md`** — module table now lists all modules (`llm`, `relations`, `merge`,
  `mdsonto`, `visualize`, `graphview`, `batch`, `sources/`, `gephi`) and the flow line
  includes the visual step.
- **`docs/PROJECT_BRIEF.md` / `docs/PROJECT_INSTRUCTIONS.md`** — kept as historical
  scoping docs but added a status banner and corrected `src/agents` → `kw/` references.
- **`README.md` (new, repo root)** — there was none; added overview, install, configure,
  run, outputs, repo layout, and doc links.

## 3. Structural review findings

**Architecture is sound.** `kw/pipeline.py` is the single source of truth for ordering
and enforces the documented invariants (JSON-LD / diagram / LoRA / visual only after the
ontology; REBEL alongside the LLM). Config is fully centralized in `kw/config.py` with a
clean env > `.env` > default precedence and one canonical namespace registry. The corpus
contract (`kw/zotero.py`) cleanly decouples the data source from everything downstream.

**Orphaned / standalone modules** (not wired into `pipeline.py`, used manually or not at
all — kept, not deleted):
- `kw/gephi.py` — standalone Gephi/GEXF exporter; nothing imports it. Decide whether to
  wire it into Step 7 or move it to `scripts/`.
- `kw/batch.py` — intended manual entry point (`python -m kw.batch`); fine as-is.
- `kw/sources/patents.py` — alternate corpus source, not yet referenced by the pipeline.
- `eval/` (`run_all.py`, `spot_check.py`, `ablation_rebel.py`) and `shiny/explorer.py` —
  legitimate auxiliary tooling, run on their own.

**Minor doc/code mismatch to note:** in `kw/config.py`, `CHUNK_FULL_TEXT` has the code
default `'true'` (chunking ON) but its inline comment says "Off by default = legacy
truncation." The comment is stale relative to the value. Pick one and make them agree.

## 4. Security note — please rotate this key

`docs/ARCHITECTURE.md` (old version) contained a **plaintext Zotero API key**
(`W3COg3WIiWEvORVM3CiTLwc2`) in several code snippets. The rewrite removes it, but the
key is still in **git history**. Recommended:
1. Rotate/revoke that Zotero key in your Zotero account settings.
2. The current code already reads it from the environment only, so no further code change
   is needed.

(The key is read-only to a group library, so exposure is low-risk, but rotating is the
safe move.)

## 5. Decisions left to you (git index — you said you'd commit)

These are staging decisions, so they're untouched:

- **Untracked source modules** that should likely be committed: `kw/batch.py`,
  `kw/gephi.py`, `kw/graphview.py`, `kw/mdsonto.py`, `kw/visualize.py`,
  `outputs_test/visualize_kg.py`, plus `queries/` and `shiny/`.
- **`outputs_test/`** is partially tracked (29 files) but now holds dozens of untracked
  generated artifacts (`graph.html`, `graph_report.md`, per-collection `*.jsonld`,
  `kg_*.html`). Decide whether `outputs_test/` is a curated demo set (commit a clean
  subset) or generated data (ignore it like `outputs/`). I left `.gitignore` as you had
  it; my earlier addition of runtime-cache ignores (`.mdsonto_cache.json`, generated
  `graph.html`/`graph_report.md`/`kg_*`) was reverted — re-apply if you want them ignored.
- **`uv.lock` is gitignored.** Lockfiles are normally committed for reproducible installs;
  consider un-ignoring it.
- The branch `visuals` has many staged modifications (incl. a staged delete of
  `kw/shapes/mds_shapes.ttl`, still referenced by `config.SHACL_SHAPES`). Confirm that
  deletion is intended before committing, or the SHACL path will be dead.

## 6. Verification performed

- `ruff` static check (F401/F811/F821/F841) — clean after fixes.
- `python -m py_compile` on every edited module — all compile.
- Manual cross-check of every documented step / env var / CLI flag against
  `kw/pipeline.py`, `kw/config.py`, `kw/__main__.py`, and `kw/batch.py`.
