"""Pipeline settings. API keys live in .env; everything else is set here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RESOURCES = ROOT / "src" / "resources"
OUTPUTS = ROOT / "outputs"
CACHE = OUTPUTS / "cache"

# ---- LLM ----
# provider "openai" = any OpenAI-compatible endpoint (Ollama, DeepSeek, Groq, OpenAI, vLLM);
# provider "anthropic" = Anthropic Messages API (system prompt is prompt-cached).
# api_key_env = name of the .env variable holding the key (None = no key needed).
# max_input_chars = paper text per extraction call; longer papers are split by section.
# request = extra fields sent with every chat call (OpenAI-compatible providers only).
# tier = "local" or "frontier": local models get each stage split into narrow single-task calls; frontier models
#        get one combined call per stage (see PIPELINE_TIER below).
PROFILES = {
    "ollama": {"tier": "local", "provider": "openai", "base_url": "http://localhost:11434/v1",
               "model": "kw-qwen3.5-9b-32k", "api_key_env": None, "max_input_chars": 48000,
               # thinking off (Qwen 3.5 otherwise reasons for minutes before answering) and a hard output cap
               "request": {"reasoning_effort": "none", "max_tokens": 8000}},
    # Fine-tuned local model (build: see src/resources/ollama/Modelfile.lora)
    "ollama-lora": {"tier": "local", "provider": "openai", "base_url": "http://localhost:11434/v1",
                    "model": "kw-qwen3.5-9b-lora-32k", "api_key_env": None, "max_input_chars": 48000,
                    "request": {"reasoning_effort": "none", "max_tokens": 8000}},
    "gemini": {"tier": "frontier", "provider": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "model": "gemini-3-flash-preview", "api_key_env": "GEMINI_API_KEY", "max_input_chars": 60000},
    "deepseek": {"tier": "frontier", "provider": "openai", "base_url": "https://api.deepseek.com/v1",
                 "model": "deepseek-v4-flash", "api_key_env": "DEEPSEEK_API_KEY", "max_input_chars": 60000},
    "groq": {"tier": "frontier", "provider": "openai", "base_url": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "api_key_env": "GROQ_API_KEY", "max_input_chars": 60000},
    "anthropic": {"tier": "frontier", "provider": "anthropic", "base_url": None,
                  "model": "", "api_key_env": "ANTHROPIC_API_KEY", "max_input_chars": 60000},
}
# Select via PowerShell: $env:LLM_PROFILE = "gemini" (or "gemini-lite").
PROFILES["gemini-lite"] = {**PROFILES["gemini"], "model": "gemini-3.1-flash-lite"}
# User-specified ceilings. None means TPM was not specified; 429 responses still back off.
GEMINI_LIMITS = {
    "gemini-3-flash-preview": {"rpm": 10, "tpm": 250000, "rpd": 1500},
    "gemini-3.1-flash-lite": {"rpm": 15, "tpm": None, "rpd": 1000},
}
LLM_PROFILE = os.getenv("LLM_PROFILE", "ollama")
LLM = PROFILES[LLM_PROFILE]
# Gemini hybrid: local drafting/alignment, frontier semantic decisions.
AGENT_PROFILES = {"extraction": "ollama", "interoperability": "ollama"} \
    if LLM_PROFILE in ("gemini", "gemini-lite") else {}


def profile_for(agent: str | None = None) -> dict:
    name = AGENT_PROFILES.get(agent, LLM_PROFILE)
    if name not in PROFILES:
        raise ValueError(f"Unknown profile {name!r} for agent {agent!r}")
    return PROFILES[name]

# Pipeline tier. local: every stage is split into single-task calls (extraction: concepts -> causal, relations,
# measurements; ontology: BFO category -> parent; enrichment: definitions, synonyms, restrictions, disjointness;
# interoperability: candidate filter -> mapping relation, study stage, domain). frontier: one combined call per stage.
PIPELINE_TIER = None        # None = the active profile's tier; set "local" or "frontier" to force one
EXTRACTION_PASSES = {
    "local": ["concepts", "causal", "relations", "measurements"],
    "frontier": ["combined"],
}


def tier(agent: str | None = None) -> str:
    return PIPELINE_TIER or profile_for(agent).get("tier", "frontier")

# Per-agent model override within that agent's routed profile (None = profile_for(agent)["model"]).
AGENT_MODELS = {"extraction": None, "normalization": None, "ontology": None,
                "enrichment": None, "interoperability": None, "integration": None}
TEMPERATURE = None          # None = provider default (some reasoning models reject temperature)
MAX_OUTPUT_TOKENS = 16000
MAX_RETRIES = 6             # retries with exponential backoff on 429 / 5xx (e.g. "model overloaded")

# ---- Embeddings (normalization synonym clustering; OpenAI-compatible /embeddings) ----
# model None = skip embedding clustering (lexical merging only). e.g. "nomic-embed-text" on Ollama.
# inputs_per_minute = provider quota on texts embedded per minute (Gemini free tier: 100); None = no pacing.
EMBED = {"base_url": "http://localhost:11434/v1", "model": "nomic-embed-text", "api_key_env": None, "inputs_per_minute": None}
# Gemini alternative: {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-embedding-001",
#                      "api_key_env": "GEMINI_API_KEY", "inputs_per_minute": 90}

# ---- Cost reporting (USD per 1M tokens; None = no cost column) ----
PRICES = {"input": None, "cached_input": None, "output": None}

# ---- Zotero (web API) ----
# PDFs come from the API when stored on zotero.org; otherwise from your local Zotero storage folder,
# or from the file path of a linked-file attachment ("attachments:" paths resolve against linked_base).
ZOTERO = {"library_type": "group", "local_storage": Path.home() / "Zotero" / "storage", "linked_base": None}

# Focus collections: name -> group library id + collection key (run with --collection <name>).
# Find keys with:  python -m src.run collections --library <group id>
COLLECTIONS = {
    "default": {"library_id": "2189702", "collection_key": "5NLP8DAI"},
    "tea": {"library_id": "2189702", "collection_key": "22PUQURH"},          # Technoeconomic Analysis (72)
    "reliability": {"library_id": "2189702", "collection_key": "QWNMWBPD"},  # Reliability-Durability (233)
    "si-perc": {"library_id": "6423676", "collection_key": "DVJZFS9I"},      # PV-Opto-KG: Si-PERC (104)
    "si-topcon": {"library_id": "6423676", "collection_key": "4JRCEDBH"},    # PV-Opto-KG: Si-TOPCon (162)
    "si-shj": {"library_id": "6423676", "collection_key": "HLC24LXN"},       # PV-Opto-KG: Si-SHJ (235)
    "sem-contact-corrosion": {"library_id": "2189702", "collection_key": "VWMCLGL5"},  # SEM-Contact-Corrosion (12)
    "sem-shj": {"library_id": "2189702", "collection_key": "L32TVGDK"},      # SEM-SHJ-Contact-Formation (3)
    "em-review": {"library_id": "2189702", "collection_key": "7R8Z2DNG"},    # Electron Microscopy Review (37)
}
DEFAULT_COLLECTION = "default"
# Keep only the N most-cited papers per collection that have a PDF (OpenAlex cited_by_count). None = all.
TOP_N_BY_CITATIONS = 50

# ---- MDS-Onto Open Portal (grounding search during enrichment; its hits join the store candidates) ----
MDS_ONTOLOGIES = "MDS-ONTO,IOF,PMDCO,QUDT"   # portal acronyms searched for candidates; None = all
CANDIDATES_PER_PORTAL = 5   # results kept per portal search query

# ---- MatPortal (matportal.org; key: MATPORTAL_API_KEY in .env). Only listed by `python -m src.run portal`;
# enrichment takes its candidates from the ontology store and the MDS-Onto portal.
MATPORTAL = {"enabled": True, "base_url": "https://rest.matportal.org", "ontologies": None}

# ---- Ontology store (python -m src.run ontologies build|status|search; docs/ontology-store.md) ----
# Every external term used by placement, enrichment and interop comes from this store: one Oxigraph named graph
# per ontology, a SQLite label index (FTS5 trigram) and one EMBED vector per term. Files are cached in
# outputs/cache/ontologies and downloaded only when missing. "home" = IRI prefixes the ontology owns: a term
# re-declared by another ontology (MDS-Onto re-declares CCO classes) is attributed to its home ontology.
# "portal" = download the latest submission of that acronym from the MDS-Onto portal (MDS_API_KEY in .env).
_GH = "https://raw.githubusercontent.com"
ONTOLOGY_SOURCES = {
    "BFO": {"url": f"{_GH}/CommonCoreOntology/CommonCoreOntologies/develop/src/cco-imports/bfo-core.ttl",
            "file": "BFO.ttl", "home": ["http://purl.obolibrary.org/obo/BFO_"]},
    "CCO": {"url": f"{_GH}/CommonCoreOntology/CommonCoreOntologies/develop/src/cco-iris/CommonCoreOntologiesMerged.ttl",
            "file": "CCO.ttl", "home": ["https://www.commoncoreontologies.org/"]},
    "RO": {"url": f"{_GH}/oborel/obo-relations/master/ro.owl", "file": "RO.owl",
           "home": ["http://purl.obolibrary.org/obo/RO_"]},
    "QUDT": {"url": f"{_GH}/qudt/qudt-public-repo/main/src/main/rdf/vocab/quantitykinds/VOCAB_QUDT-QUANTITY-KINDS-ALL.ttl",
             "file": "QUDT.ttl", "home": ["http://qudt.org/vocab/quantitykind/"]},
    "QUDT-units": {"url": f"{_GH}/qudt/qudt-public-repo/main/src/main/rdf/vocab/unit/VOCAB_QUDT-UNITS-ALL.ttl",
                   "file": "QUDT-units.ttl", "home": ["http://qudt.org/vocab/unit/"]},
    "PMDCO": {"url": f"{_GH}/materialdigital/core-ontology/main/pmdco-full.ttl", "file": "PMDCO.ttl",
              "home": ["https://w3id.org/pmd/co/"]},
    "IOF": {"url": f"{_GH}/iofoundry/ontology/master/core/Core.rdf", "file": "IOF.owl",
            "home": ["https://spec.industrialontologies.org/"]},
    "MDS-Onto": {"portal": "MDS-ONTO", "file": "MDS-Onto-{version}.ttl", "home": ["https://cwrusdle.bitbucket.io/mds/"]},
}
ONTOLOGY_STORE = CACHE / "ontology_store"
ONTOLOGY_SEARCH = {
    "weights": {"lexical": 0.5, "cosine": 0.5},  # fused score: lexical = 1 for an exact label, else trigram similarity
    "min_score": 0.35,           # fused score a candidate needs (exact label matches are always kept)
    "min_fuzzy": 0.5,            # trigram similarity that counts as a lexical hit
    "min_cosine": 0.6,           # embedding cosine that counts as a semantic hit
    "candidates_per_class": 8,   # external candidates shown per class (interop)
    "parents_per_class": 8,      # CCO/BFO parent candidates shown per concept (placement)
    "properties_per_relation": 5,  # property candidates shown per extracted relation (restrictions)
    "tie_margin": 0.05,          # store candidates within this fused score are a tie; RELATION_GROUPS breaks it
    "max_hops": 2,               # mapping propagation from a matched term: its mappings (1), and theirs (2)
    "hop_decay": 0.8,            # confidence multiplier per hop
    "propagated_per_class": 6,   # propagated candidates added per class
    "parent_ontologies": ["CCO", "BFO"],         # placement parents, in order of preference
    "name_match_ontologies": ["MDS-Onto", "PMDCO"],  # a same-name class here is used as the parent
}

# ---- Mapping checks (interoperability, integration) ----
MAPPING = {
    "strong_similarity": 0.85,   # label-matched candidate at/above this is auto-mapped as exact if the model skipped it
}

# ---- Cross-domain integration (python -m src.run integrate) ----
# Runs after the domain runs: maps the domain ontologies of one run set to each other in a master ontology.
# Domain ontologies are read, never rewritten. Default inputs: the latest run per collection below that completed
# interop (current WORKFLOW_REVISION preferred).
INTEGRATION = {
    "collections": ["tea", "reliability", "si-perc", "si-topcon"],
    "min_similarity": 0.80,      # embedding cosine for a mutual-nearest-neighbour candidate pair (EMBED model required)
    "max_model_pairs": 1500,     # candidate pairs sent to the model; the rest are listed in candidates.json unreviewed
    "batch": {"local": 12, "frontier": 30},
}

# ---- LoRA training data (python -m src.run lora-data) ----
# Ontology suite used as the answer key: BFO, CCO and QUDT classes; RO enters through the property menu
# (resources/upper). Values are URLs or local file paths (.ttl = Turtle, .owl/.rdf = RDF/XML).
LORA = {
    "ontologies": {
        "BFO": "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/develop/src/cco-imports/bfo-core.ttl",
        "CCO": "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/develop/src/cco-iris/CommonCoreOntologiesMerged.ttl",
        "QUDT": "https://raw.githubusercontent.com/qudt/qudt-public-repo/main/src/main/rdf/vocab/quantitykinds/VOCAB_QUDT-QUANTITY-KINDS-ALL.ttl",
    },
    # Evaluation corpora: runs on these collections are never distilled into training data.
    "exclude_collections": ["tea", "reliability", "si-perc", "si-topcon"],
    "hierarchy_batch": 25, "enrich_batch": 8, "align_batch": 10,
    "restrict_batch": 8, "restrict_examples": 150,  # property-selection task (BFO/CCO/RO domain and range); ~1.2k upper classes cap it near 200
    "repeats": 2,               # re-batch the training split this many times with different shuffles
    "max_distill_chars": 20000, # longest paper chunk distilled into an extraction example
    "seed": 13,
}

# ---- Output ontology ----
ONTOLOGY_IRI = "http://example.org/kw/"
ONTOLOGY_TITLE = "PV Knowledge Workflow Ontology"
WORKFLOW_REVISION = "2026-10-04-ontology-store-v1"
WORKFLOW_REVISION_NOTE = ("External terms from a local ontology store (Oxigraph + trigram + embedding search over BFO, "
                          "CCO, RO, QUDT, PMDCO, IOF, MDS-Onto): placement parents (CCO, then BFO; same-name MDS-Onto/PMDCO "
                          "class wins), restriction properties, mapping candidates with 1-2 hop propagation; broader, "
                          "narrower and related matches; imported definitions and labels; MIREOT imports of every term")
# Profiles whose enrichment may write definitions from model knowledge (recorded as definition_source <profile>:<model>).
MODEL_DEFINITION_PROFILES = ("gemini", "gemini-lite")


def secret(name: str | None) -> str | None:
    """Read an API key from .env (blank counts as unset)."""
    return (os.getenv(name, "").strip() or None) if name else None


def model_for(agent: str) -> str:
    model = AGENT_MODELS.get(agent) or profile_for(agent)["model"]
    if not model:
        raise RuntimeError(f"Set a model for profile '{LLM_PROFILE}' (or AGENT_MODELS['{agent}']) in src/config.py")
    return model
