# run_test.py - quick LOCAL smoke test for the kw pipeline.
#
# Run this file in Spyder (green "Run file" arrow) or from the CLI:
#     python run_test.py

import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("[run_test] nest_asyncio not installed. If you hit "
          "'event loop is already running', run:  pip install nest_asyncio")

from kw import config, pipeline

# ----------------------------- test settings ------------------------------
# Find collection ids with:  python -m kw --list-collections
COLLECTION_ID = config.COLLECTION_ID   # default from .env / config
LIMIT         = 5                       # max papers to process for the test
EMIT_DIAGRAM  = True                    # draw.io map (adds LLM tagging calls)
DO_LORA       = False                   # Step 6 (dataset-only unless LORA_TRAIN=true)
OUTPUTS_DIR   = "outputs_test"          # keep test runs out of the real outputs/
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[run_test] collection={COLLECTION_ID}  limit={LIMIT}")
    print(f"[run_test] model={config.MODEL}  endpoint={config.LLM_BASE_URL}")

    result = pipeline.run(
        COLLECTION_ID,
        outputs_dir=OUTPUTS_DIR,
        emit_diagram=EMIT_DIAGRAM,
        do_lora=DO_LORA,
        limit=LIMIT,
    )

    print("\n[run_test] done.")
    print("  concepts  :", len(result.get("concepts") or []))
    print("  out_dir   :", result.get("out_dir"))
    print("  ontology  :", result.get("ttl"))
    print("  all.jsonld:", result.get("all_jsonld"))
    print("  validation:", result.get("validation"))
