# 05 — Lessons Learned (the case for the refactor)

Ordered by how much pain they cause the rebuild.

## 1. Capability fragmentation — three entry points, no shared contract
Extraction lives in `src/`, OWL/JSON-LD in `graphdb_connector.py`, draw.io in
`cemento_connect.py`. None of the connectors import `src/`. The pipeline is stitched
together by **CSV files on disk**, not typed objects. Result: the project's headline
deliverable (committee-ready ontology) technically exists but can't be run as one flow.
→ *Rebuild around one in-memory data contract that every stage consumes and produces.*

## 2. Version sprawl & duplication
V1–V6 monoliths (`knowledge_worklow_v5.py`, `..._v5_codebase.py`) **plus** three git
worktrees under `.claude/worktrees/`, each carrying its own V6 (one is 1048 lines),
README, ARCHITECTURE, and outputs. `tag_concepts` and `build_drawio_xml` exist in **both**
`cemento_connect.py` and `src/`. Bug fixes must be made in N places.
→ *Pick one of everything; delete the rest; enforce "one implementation per capability."*

## 3. Implicit, brittle data contracts
- Cells packed as `"value | quote"` strings → every consumer re-parses on `|`.
- Wide-format schema explodes to 60–80 columns.
- No model for Paper / Triple / OntologyClass / Provenance — they're dicts and strings.
→ *Promote everything to Pydantic models in `core/`; serialize at the edges only.*

## 4. No validation gate
Ontologies are emitted unvalidated — no reasoner (consistency), no OOPS! (pitfalls),
no SHACL (shape). For a journal claim of "committee-ready," this is the missing spine.
→ *Make `validate/` a required stage; fail the run if it doesn't pass (see `eval/structural_metrics.py`).*

## 5. No provenance or confidence as data
Provenance today = a quote string inside a cell. No per-assertion source/confidence
object, no routing/decision log. Undercuts the "explainable & reproducible" goal.
→ *Attach a Provenance record (source paper, span, tool, model+version, seed, confidence) to every triple.*

## 6. Namespace / standards inconsistency
`mds#` vs `mds/`; MDS-only grounding in the generator vs BFO/PMD/QUDT in the gaas
reference. No CCO anywhere despite the stated interoperability requirement.
→ *Central namespace registry; one canonical MDS IRI; add BFO/CCO alignment in `ground/`.*

## 7. Robustness gaps
Serial processing (~7–13 min / 50 papers in Phase 2), no checkpointing, no retries —
an API error crashes the whole run and reprocesses from scratch. No tests.
→ *Async + checkpointing per paper; retry/backoff; a small unit/integration test suite.*

## 8. Repo hygiene
Generated `outputs/` and `schemas/` are committed (and duplicated across worktrees),
bloating the repo. API keys were historically hardcoded (now mostly in `.env`/config).
→ *Gitignore generated data; keep secrets in `.env`; remove worktrees from VCS.*

## 9. "Agents" that aren't agents
The `src/agents/` modules are LLM-calling functions, not an agent loop. The multi-agent
orchestration, REBEL parallel extraction, and LoRA routing from the brief are still stubs.
→ *Either rename to `stages/` for honesty, or build the real orchestrator — but don't
conflate the two in docs.*

## What's genuinely good (keep)
- `src/config.py` provider-agnostic design (`OpenAIModel` + base_url).
- PydanticAI `result_type` structured output (kills hand-written tool JSON).
- Two-stage discovery→full-text mining with source quotes (V4/V5 core idea).
- `graphdb_connector.py`'s OWL+JSON-LD emit logic (harvest, don't rewrite).
- The Zotero abstraction (`get_collection_with_text` returns a clean uniform dict).
- `docs/ARCHITECTURE.md` (in the worktree) — excellent existing documentation.
