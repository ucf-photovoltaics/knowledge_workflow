# run_test.py — quick LOCAL smoke test for the kw pipeline (one paper).
#
# Run in Spyder (green "Run file" arrow) or from a shell:
#     uv run python run_test.py
#
# It:
#   * works from the project root (so .env, data/ palettes, and outputs/ resolve),
#   * applies nest_asyncio (Spyder's IPython kernel already runs an event loop,
#     which otherwise breaks pydantic-ai's run_sync),
#   * runs the pipeline on a SMALL number of papers with the heavy steps off,
#   * prints the validation-gate verdict + where the report landed.
#
# Edit the dials below as needed.

import os

# 1) Work from the project root (this file's folder) BEFORE importing kw, so that
#    .env, data/mds_onto.json, data/cemento-templates.xml, and outputs/ all resolve.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 2) Spyder/IPython already run an event loop; nest_asyncio lets pydantic-ai's
#    run_sync work inside it. Harmless on a plain CLI run.
try:
    import nest_asyncio
    nest_asyncio.apply()
except Exception:
    pass

from kw import config, pipeline

# --- dials -----------------------------------------------------------------
COLLECTION_ID = config.COLLECTION_ID   # or hardcode e.g. "5NLP8DAI"
LIMIT         = 1                      # number of papers to process
DO_REBEL      = False                  # REBEL triples (needs transformers+torch)
DO_LORA       = False                  # LoRA fine-tune
EMIT_DIAGRAM  = False                  # cemento draw.io diagram
EMIT_VISUAL   = False                  # Step 7 interactive graph
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[run_test] collection={COLLECTION_ID} limit={LIMIT} model={config.MODEL}")
    r = pipeline.run(
        COLLECTION_ID,
        limit=LIMIT,
        do_rebel=DO_REBEL,
        do_lora=DO_LORA,
        emit_diagram=EMIT_DIAGRAM,
        emit_visual=EMIT_VISUAL,
    )

    print("\n=== run_test summary ===")
    print(f"  out_dir : {r.get('out_dir')}")
    print(f"  ttl     : {r.get('ttl')}")

    rep = r.get("validation") or {}
    if rep:
        verdict = "PASS" if rep.get("gate_passed") else "FAIL"
        print(f"  gate    : {verdict}  (required: {', '.join(rep.get('required_checks', [])) or 'none'})")
        if rep.get("required_failed"):
            print(f"  failing : {', '.join(rep['required_failed'])}")
        print(f"  report  : {rep.get('report_md')}")
        for c in rep.get("checks", []):
            print(f"    - {c['name']:<10} {c['severity']:<8} {c['status']:<5} {c['summary']}")
    else:
        print("  (no validation report — was a TTL produced?)")
