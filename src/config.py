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
                "enrichment": None, "interoperability": None}
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

# ---- MDS-Onto Open Portal ----
MDS_ONTOLOGIES = "MDS-ONTO,IOF,PMDCO,QUDT"   # portal acronyms searched for candidates; None = all
# (BFO and CCO are matched locally from resources/upper, so they are not searched on the portals)

# ---- MatPortal (matportal.org, materials-science OntoPortal; key: MATPORTAL_API_KEY in .env) ----
# Searched alongside the MDS-Onto portal for candidate terms. ontologies: comma-separated acronyms; None = all.
MATPORTAL = {"enabled": True, "base_url": "https://rest.matportal.org", "ontologies": None}
CANDIDATES_PER_PORTAL = 5   # results kept per portal per search query

# ---- Mapping candidates (enrichment) and mapping checks (interoperability) ----
MAPPING = {
    "candidates_total": 8,       # candidates shown to the model per class, after re-ranking
    "min_similarity": 0.6,       # embedding cosine a non-exact candidate needs to be kept (EMBED model required)
    "strong_similarity": 0.85,   # label-matched candidate at/above this is auto-mapped as exact if the model skipped it
    "local_upper_top": 3,        # nearest BFO/CCO classes added as local candidates
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
WORKFLOW_REVISION = "2026-10-03-evidence-hierarchy-domain-iris-v1"


def secret(name: str | None) -> str | None:
    """Read an API key from .env (blank counts as unset)."""
    return (os.getenv(name, "").strip() or None) if name else None


def model_for(agent: str) -> str:
    model = AGENT_MODELS.get(agent) or profile_for(agent)["model"]
    if not model:
        raise RuntimeError(f"Set a model for profile '{LLM_PROFILE}' (or AGENT_MODELS['{agent}']) in src/config.py")
    return model
