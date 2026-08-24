# Kweave

Kweave turns a Zotero collection into normalized, provenance-ready graph data through three agents:

1. **Triage agent** classifies Zotero papers and local artifacts and chooses an extraction route.
2. **Extract agent** runs every configured entity/relation tool. Optional tool failures are recorded per paper without aborting the collection.
3. **Normalization agent** deduplicates entities and relations, applies optional ontology grounding/validation hooks, and emits one serializable graph.

## Configure Zotero

Copy `.env.example` values into your shell environment. Never commit the API key.

- `ZOTERO_LIBRARY_ID`: user or group library ID.
- `ZOTERO_LIBRARY_TYPE`: `users` or `groups`.
- `ZOTERO_API_KEY`: a Zotero Web API key with read access.

The client can list accessible libraries, map nested collections, page through results, and retrieve Zotero-indexed PDF text. Collection results are keyed by Zotero item key so duplicate titles are safe.

## Run a collection

```powershell
uv run kweave J73JQMCQ --limit 10 --output data/results/normalized.json
```

The dependency-free baseline extractors always run. Install `.[scispacy]` plus a matching scispaCy model to enable biomedical concept linking; otherwise the missing optional tool is reported in each paper's extraction errors while the rest of the pipeline continues.

The pinned scispaCy 0.5.4 model stack requires Python 3.11; use `uv sync --python 3.11 --extra scispacy` for that optional environment.

## Test

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
