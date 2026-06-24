# rebel_test.py — run ONLY the REBEL relation-extraction stage and show the triples.
#
# REBEL needs transformers + torch:   pip install transformers torch
# (CPU is fine; REBEL_DEVICE defaults to cpu, so Blackwell/sm_120 is a non-issue.)
# First run downloads the model (~1.6 GB).

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from kw import config, zotero, rebel

LIMIT = 5  # same small slice as run_test.py

print(f"[rebel_test] fetching up to {LIMIT} papers from collection {config.COLLECTION_ID} ...")
papers = zotero.get_collection_with_text(config.COLLECTION_ID, limit=LIMIT)
print(f"[rebel_test] {len(papers)} papers loaded. Running REBEL "
      f"(device={rebel.REBEL_DEVICE}; first run downloads the model)...\n")

triples = rebel.extract_corpus(papers)
print(f"\n[rebel_test] {len(triples)} triples extracted\n")

for t in triples:
    src = (t.provenance.source_paper or "")[:45]
    print(f"  {t.subject}  --[{t.predicate}]-->  {t.object}    ({src})")

if triples:
    os.makedirs("outputs_test/rebel", exist_ok=True)
    files = rebel.save_triples(triples, "outputs_test/rebel", "rebel_test.csv", ns=config.MDS_NS)
    print(f"\n[rebel_test] saved:\n  {files['csv']}\n  {files['jsonld']}")
else:
    print("\n[rebel_test] No triples returned. If you saw '[rebel] unavailable' above, "
          "install the deps:  pip install transformers torch")
