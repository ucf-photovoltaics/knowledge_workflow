"""Pipeline settings. API keys live in .env; everything else is set here.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
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
_VLLM_EFFORT = os.getenv("VLLM_REASONING_EFFORT", "none")  # none, low, medium or high
PROFILES = {
    "ollama": {"tier": "local", "provider": "openai", "base_url": "http://localhost:11434/v1",
               "model": "kw-qwen3.5-9b-32k", "api_key_env": None, "max_input_chars": 48000,
               "outage_wait_s": 900,  # Ollama restarting or the model reloading: wait up to 15 min, then fail
               # thinking off (Qwen 3.5 otherwise reasons for minutes before answering) and a hard output cap
               "request": {"reasoning_effort": "none", "max_tokens": 8000}},
    # Fine-tuned local model (build: see src/resources/ollama/Modelfile.lora)
    "ollama-lora": {"tier": "local", "provider": "openai", "base_url": "http://localhost:11434/v1",
                    "model": "kw-qwen3.5-9b-lora-32k", "api_key_env": None, "max_input_chars": 48000,
                    "outage_wait_s": 900,
                    "request": {"reasoning_effort": "none", "max_tokens": 8000}},
    # vLLM on a cluster GPU node (scripts/slurm-sweep.sh). Same local-tier passes as "ollama", so runs differ only by model.
    "vllm": {"tier": "local", "provider": "openai", "base_url": os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
             "model": os.getenv("VLLM_MODEL", "mistralai/Mistral-Small-4-119B-2603"), "api_key_env": None,
             "max_input_chars": 48000, "outage_wait_s": 900,
             "request": {"reasoning_effort": _VLLM_EFFORT,
                         # thinking tokens count against max_tokens, so medium/high reasoning gets twice the budget
                         "max_tokens": 16000 if _VLLM_EFFORT in ("medium", "high") else 8000,
                         # Qwen-style templates ignore reasoning_effort, so thinking is also switched off explicitly.
                         # Not when reasoning is requested (an explicit flag would override it, e.g. Gemma 4), and
                         # never for Mistral tokenizers (vLLM rejects chat-template arguments for them).
                         "extra_body": {} if _VLLM_EFFORT != "none"
                         or "--tokenizer-mode mistral" in os.getenv("VLLM_EXTRA_ARGS", "")
                         else {"chat_template_kwargs": {"enable_thinking": False}}}},
    "gemini": {"tier": "frontier", "provider": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "model": "gemini-3-flash-preview", "api_key_env": "GEMINI_API_KEY", "max_input_chars": 60000},
    "deepseek": {"tier": "frontier", "provider": "openai", "base_url": "https://api.deepseek.com/v1",
                 "model": "deepseek-v4-flash", "api_key_env": "DEEPSEEK_API_KEY", "max_input_chars": 60000},
    "groq": {"tier": "frontier", "provider": "openai", "base_url": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "api_key_env": "GROQ_API_KEY", "max_input_chars": 60000},
    "anthropic": {"tier": "frontier", "provider": "anthropic", "base_url": None,
                  "model": "", "api_key_env": "ANTHROPIC_API_KEY", "max_input_chars": 60000},
}
# Thinking for chosen agents only (vLLM): VLLM_THINK_AGENTS="ontology,enrichment" sends those agents' calls with
# reasoning on, the rest with VLLM_REASONING_EFFORT. The server needs a --reasoning-parser for the model.
# Greedy decoding makes thinking loop, so these calls sample (Gemma's recommended 1.0 / 0.95 / 64 by default).
_THINK_TEMPERATURE = os.getenv("VLLM_THINK_TEMPERATURE", "1.0")
PROFILES["vllm-think"] = {**PROFILES["vllm"], "request": {
    "reasoning_effort": os.getenv("VLLM_THINK_EFFORT", "medium"),
    "max_tokens": int(os.getenv("VLLM_THINK_MAX_TOKENS", "16000")),
    **({"temperature": float(_THINK_TEMPERATURE), "top_p": float(os.getenv("VLLM_THINK_TOP_P", "0.95"))}
       if _THINK_TEMPERATURE else {}),
    "extra_body": {"top_k": int(os.getenv("VLLM_THINK_TOP_K", "64"))} if _THINK_TEMPERATURE else {}}}
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
if LLM_PROFILE == "vllm":
    AGENT_PROFILES.update({a: "vllm-think" for a in os.getenv("VLLM_THINK_AGENTS", "").replace(",", " ").split()})


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
TEMPERATURE = float(os.environ["LLM_TEMPERATURE"]) if os.environ.get("LLM_TEMPERATURE") else None
# unset = provider default (some reasoning models reject temperature); scripts/slurm-sweep.sh sets 0
MAX_OUTPUT_TOKENS = 16000
MAX_RETRIES = 6             # retries with exponential backoff on 429 / 5xx (e.g. "model overloaded")
# Reuse model answers from earlier runs: identical whole requests (outputs/cache/calls) and identical rows across
# runs, e.g. tea-n5 answers inside tea-n10 (outputs/cache/rows.sqlite3, src/agents/base.py RowCache).
# KW_FRESH=1 asks the model again for everything (benchmarks and the reuse check).
REUSE_ANSWERS = os.getenv("KW_FRESH", "") != "1"
# KW_SCRATCH=1: a benchmark or check run - kept out of eval_runs.csv, the sweep figures and integration's run choice.
SCRATCH_RUN = os.getenv("KW_SCRATCH", "") == "1"

# ---- Embeddings (normalization synonym clustering; OpenAI-compatible /embeddings) ----
# model None = skip embedding clustering (lexical merging only). e.g. "nomic-embed-text" on Ollama.
# inputs_per_minute = provider quota on texts embedded per minute (Gemini free tier: 100); None = no pacing.
EMBED = {"base_url": "http://localhost:11434/v1", "model": "nomic-embed-text", "api_key_env": None,
         "inputs_per_minute": None, "cache_version": 1,  # bump if a model is replaced under the same name
         # retrieval task prefixes (nomic-embed-text expects these; "" for models without them). Ontology-store
         # terms are documents, concepts searched against the store are queries; changing them needs `ontologies build`.
         "query_prefix": "search_query: ", "document_prefix": "search_document: "}
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
    # Use-case collections (scripts/use-cases.txt); PDF counts from the 2026-10-16 Zotero inventory.
    # "domain" names the field for the prompts (config.DOMAIN); without it a collection is photovoltaics.
    "accel-testing": {"library_id": "2189702", "collection_key": "HR3N6D86"},  # UCF DEPV: Reliability-Durability / Accelerated Testing (32 PDFs)
    "acrylic-hardcoats": {"library_id": "37619", "collection_key": "UZ5PZED4", "domain": "polymers"},  # CWRU-SDLE: PolymersLit / PMMA / AcrylicHardcoats (64 PDFs)
    "adv-manufacturing": {"library_id": "37619", "collection_key": "RUSNPYY6", "domain": "additive manufacturing"},  # CWRU-SDLE: AdvancedManufacturing (53 PDFs)
    "ai4science": {"library_id": "37619", "collection_key": "H6SE4JV9", "domain": "AI for science"},  # CWRU-SDLE: DataScience / AI4Science-FASST (72 PDFs)
    "backsheets": {"library_id": "37619", "collection_key": "A9G7PIW6"},  # CWRU-SDLE: PVlit / Backsheets (204 PDFs)
    "building-energy": {"library_id": "37619", "collection_key": "SR7EXM7B", "domain": "building energy"},  # CWRU-SDLE: GroupMembers / Shreyas (97 PDFs)
    "building-nn": {"library_id": "37619", "collection_key": "X7DVPQEK", "domain": "building energy"},  # CWRU-SDLE: BuildingEnergyEff / Neural Network (47 PDFs)
    "cdte": {"library_id": "6423676", "collection_key": "NEKYMJDL"},  # PV-Opto-KG: CdTe (51 PDFs)
    "cell-corrosion": {"library_id": "37619", "collection_key": "3QH98BPY"},  # CWRU-SDLE: PVlit / Cells / Cell-Corrosion (42 PDFs)
    "cell-cracking": {"library_id": "37619", "collection_key": "X4YREY6N"},  # CWRU-SDLE: PVlit / Cells / CellCracking (91 PDFs)
    "cell-metrology": {"library_id": "2189702", "collection_key": "AI25PZIX"},  # UCF DEPV: Characterization and Metrology / Cell Metrology (319 PDFs)
    "chem-reactions": {"library_id": "37619", "collection_key": "9FLFUHV3", "domain": "chemistry and chemical synthesis"},  # CWRU-SDLE: GroupMembers / QuynhDTran / ChemReactions (61 PDFs)
    "chemistry": {"library_id": "37619", "collection_key": "BJQ3H4ZY", "domain": "chemistry information extraction"},  # CWRU-SDLE: Chemistry (83 PDFs)
    "coatings": {"library_id": "37619", "collection_key": "U4Q83KBG", "domain": "polymer coatings"},  # CWRU-SDLE: PolymersLit / Coatings (81 PDFs)
    "contact-degr": {"library_id": "2189702", "collection_key": "ML5USF6J"},  # UCF DEPV: -Archived Collections- / Contact Degradation (66 PDFs)
    "digital-twin": {"library_id": "37619", "collection_key": "HDKGRHYA", "domain": "digital twins"},  # CWRU-SDLE: DataScience / DigitalTwin (44 PDFs)
    "diw-am": {"library_id": "37619", "collection_key": "9FZYE7EM", "domain": "additive manufacturing"},  # CWRU-SDLE: GroupMembers / Hein / DIW/AM (141 PDFs)
    "elec-components": {"library_id": "5987301", "collection_key": "CLEVUB8V", "domain": "infrared photodetectors"},  # UCF-DARTS: P13-AI-Assisted-Knowledge-Extraction / Dataset-Electron (107 PDFs)
    "encapsulants": {"library_id": "37619", "collection_key": "RZ49WRN3"},  # CWRU-SDLE: PVlit / Encapsulants (133 PDFs)
    "energy-resilience": {"library_id": "2189702", "collection_key": "R2XEADNT", "domain": "energy resilience"},  # UCF DEPV: Energy Resilience (61 PDFs)
    "eva-pe-degr": {"library_id": "37619", "collection_key": "M9GN3HHY", "domain": "polymer degradation"},  # CWRU-SDLE: GroupMembers / Klinke / EVA-PE-Degradation (52 PDFs)
    "extreme-weather": {"library_id": "2189702", "collection_key": "XHEJUKL7"},  # UCF DEPV: Extreme Weather (26 PDFs)
    "fair-data": {"library_id": "37619", "collection_key": "UWCPEV6E", "domain": "FAIR research data"},  # CWRU-SDLE: FAIR-Ontology / FAIR-data (40 PDFs)
    "field-studies": {"library_id": "2189702", "collection_key": "9E649EBP"},  # UCF DEPV: Reliability-Durability / Field Studies (38 PDFs)
    "fluoropolymer": {"library_id": "37619", "collection_key": "EGUBBBHV", "domain": "polymers"},  # CWRU-SDLE: PolymersLit / Fluoropolymer (94 PDFs)
    "gaas": {"library_id": "6423676", "collection_key": "G32B4IIS"},  # PV-Opto-KG: GaAs (54 PDFs)
    "geospatial": {"library_id": "37619", "collection_key": "V7CPNW5X", "domain": "geospatial data science"},  # CWRU-SDLE: DataScience / GeoSpatioTemporal (71 PDFs)
    "gnn": {"library_id": "37619", "collection_key": "PAB55QSY", "domain": "graph neural networks"},  # CWRU-SDLE: DataScience / GraphNeuralNetworks (177 PDFs)
    "iec-climatic": {"library_id": "37619", "collection_key": "5TF9N2Z7"},  # CWRU-SDLE: Standards / IEC / IEC-Climatic (69 PDFs)
    "image-ml": {"library_id": "37619", "collection_key": "DVTAU699", "domain": "image machine learning"},  # CWRU-SDLE: DataScience / ImageML (86 PDFs)
    "indentation": {"library_id": "37619", "collection_key": "73Q4SYTL", "domain": "nanoindentation and thin-film mechanics"},  # CWRU-SDLE: Materials / Indentation (50 PDFs)
    "kg-rdf": {"library_id": "37619", "collection_key": "WNHDSEVJ", "domain": "knowledge graphs"},  # CWRU-SDLE: FAIR-Ontology / KnowledgeGraphs-RDF (43 PDFs)
    "lifetime-degr": {"library_id": "37619", "collection_key": "HMBT8DV3"},  # CWRU-SDLE: PVlit / LifetimeDegradation (72 PDFs)
    "lithography": {"library_id": "37619", "collection_key": "PJ6EWCFC", "domain": "lithography"},  # CWRU-SDLE: SemiconductorsLit / LithographyLit / ARMR (32 PDFs)
    "matdatasci": {"library_id": "37619", "collection_key": "UCAPCC7G", "domain": "materials data science"},  # CWRU-SDLE: DataScience / MatDataSci (59 PDFs)
    "metallization": {"library_id": "2189702", "collection_key": "WZHTQQLX"},  # UCF DEPV: Metallization (121 PDFs)
    "microstructure-sim": {"library_id": "37619", "collection_key": "8MYPHITN", "domain": "microstructure simulation and characterization"},  # CWRU-SDLE: GroupMembers / Gabriel / Microstructure-Simulation (55 PDFs)
    "module-metrology": {"library_id": "2189702", "collection_key": "IBBXLNG6"},  # UCF DEPV: Characterization and Metrology / Module Metrology (94 PDFs)
    "onto-chem": {"library_id": "37619", "collection_key": "HILDJZU3", "domain": "chemistry ontologies and knowledge graphs"},  # CWRU-SDLE: FAIR-Ontology / Onto-Chem (40 PDFs)
    "plant-performance": {"library_id": "37619", "collection_key": "NGRSRICF"},  # CWRU-SDLE: PVlit / PV-PlantPerformance (56 PDFs)
    "pmma": {"library_id": "37619", "collection_key": "SZZNAEJZ", "domain": "polymer degradation"},  # CWRU-SDLE: PolymersLit / PMMA (47 PDFs)
    "pv-cells-annot": {"library_id": "5987301", "collection_key": "HSWHBIMI"},  # UCF-DARTS: P13-AI-Assisted-Knowledge-Extraction / Dataset-Photovol (103 PDFs)
    "reasoning": {"library_id": "37619", "collection_key": "2BJVUBI5", "domain": "ontology reasoning"},  # CWRU-SDLE: FAIR-Ontology / Reasoning (42 PDFs)
    "recycling": {"library_id": "37619", "collection_key": "FI9BFJRJ"},  # CWRU-SDLE: PVlit / Recycling-CircularEconomy (60 PDFs)
    "rubber-microplastics": {"library_id": "37619", "collection_key": "9UR82HDT", "domain": "rubber and tire materials"},  # CWRU-SDLE: GroupMembers / Hein / Rubber-Microplastics (34 PDFs)
    "semis": {"library_id": "37619", "collection_key": "J5WTX9RG", "domain": "semiconductor microelectronics"},  # CWRU-SDLE: SemiconductorsLit (37 PDFs)
    "servicelife": {"library_id": "37619", "collection_key": "97G2FTE4"},  # CWRU-SDLE: RelPhys-SLP (43 PDFs)
    "sic": {"library_id": "37619", "collection_key": "QBMET8FE", "domain": "silicon carbide"},  # CWRU-SDLE: Materials / SiC (53 PDFs)
    "solar-forecast": {"library_id": "37619", "collection_key": "4SQFK67E"},  # CWRU-SDLE: PVlit / SolarForecast (43 PDFs)
    "spatial-char": {"library_id": "2189702", "collection_key": "8CP6VFBU"},  # UCF DEPV: Characterization and Metrology / Spatially-Resolved Cha (58 PDFs)
    "timeseries": {"library_id": "37619", "collection_key": "7W8F2922", "domain": "time series statistics"},  # CWRU-SDLE: Statistics / TimeSeriesAnalysis (134 PDFs)
    "topcon-rel": {"library_id": "2189702", "collection_key": "NEEKPD6J"},  # UCF DEPV: Reliability-Durability / TOPCon (37 PDFs)
    "xct": {"library_id": "37619", "collection_key": "Y5QLU9XG", "domain": "X-ray computed tomography of materials"},  # CWRU-SDLE: DataScience / XCT (47 PDFs)
    "xrd": {"library_id": "37619", "collection_key": "39II8T8R", "domain": "X-ray diffraction and scattering"},  # CWRU-SDLE: DataScience / XRD-WAXS-SAXS (86 PDFs)
}
DEFAULT_COLLECTION = "default"

# ---- Domain wording in the prompts ----
# The prompts name the field the papers come from ({{domain}}) and give examples ({{ex:<name>}}). A collection may set
# "domain" (default "photovoltaics"); src/run.py sets DOMAIN per run, and integration joins its runs' domains.
# For photovoltaics the prompts render exactly as written for PV; any other domain also gets the neutral examples.
DEFAULT_DOMAIN = "photovoltaics"
DOMAIN = DEFAULT_DOMAIN
PROMPT_EXAMPLES = {  # name: (photovoltaics wording, wording for any other domain)
    "materials": ("wafer, layer, film, paste, encapsulant, dopant, gas, chemical",
                  "substrate, layer, film, powder, polymer, additive, gas, chemical"),
    "devices": ("cell, module, contact, junction, interface, stack",
                "device, component, part, joint, interface, assembly"),
    "equipment": ("furnace, PECVD tool, solar simulator, SEM",
                  "furnace, deposition tool, test chamber, SEM"),
    "process_steps": ("texturing, diffusion, deposition, firing, annealing, lamination, cleaning, testing",
                      "mixing, casting, deposition, curing, annealing, machining, cleaning, testing"),
    "parameters": ("temperature, time, pressure, gas flow, thickness, doping level, dose, ramp rate",
                   "temperature, time, pressure, gas flow, thickness, concentration, dose, ramp rate"),
    "properties": ("efficiency, Voc, Jsc, FF, lifetime, sheet resistance, series resistance, recombination current, reflectance, cost, degradation rate",
                   "efficiency, strength, modulus, conductivity, lifetime, resistance, yield, reflectance, cost, degradation rate"),
    "phenomena": ("recombination, LeTID, corrosion, delamination, cracks, PID",
                  "diffusion, fatigue, corrosion, delamination, cracks, creep"),
    "methods": ("EL, PL, IV, SIMS, modelling, simulation",
                "SEM, XRD, FTIR, tensile testing, modelling, simulation"),
    "stressors": ("damp heat, UV exposure, illumination, bias, climate",
                  "humidity, UV exposure, heat, mechanical load, climate"),
    "label_example": ('"rear AlOx passivation layer", not just "layer"',
                      '"UV-cured acrylic topcoat", not just "coating"'),
    "quality": ('("the module has an efficiency"); has_disposition: a tendency ("modules susceptible to PID")',
                '("the coating has a thickness"); has_disposition: a tendency ("joints susceptible to fatigue")'),
    "parthood": ('("the rear contact is part of the cell", "the process has a firing step")',
                 '("the topcoat is part of the coating system", "the process has a curing step")'),
    "causal_param": ('("higher firing temperature increases contact resistance")',
                     '("higher curing temperature increases hardness")'),
    "causal_stressor": ('("damp heat causes corrosion of the Ag fingers")',
                        '("humidity causes corrosion of the steel substrate")'),
    "causal_finding": ('("thinner oxide improved Voc"), and prevention or mitigation ("hydrogenation prevents LeTID")',
                       '("thinner layers improved adhesion"), and prevention or mitigation ("a UV absorber prevents yellowing")'),
    "configuration": ("solar cell does not necessarily imply an amorphous silicon film or a phosphorus-diffused emitter",
                      "coating does not necessarily imply the specific resin or cure schedule one paper used"),
    "measured_thing": ('("efficiency" is not "solar cell")',
                       '("efficiency" is not "device")'),
    "material_entities": ("materials, layers, wafers, cells, modules, equipment",
                          "materials, layers, substrates, devices, components, equipment"),
    "cat_quality": ("efficiency, Voc, temperature, reflectance",
                    "efficiency, strength, temperature, reflectance"),
    "cat_disposition": ("susceptibility to PID, degradation propensity",
                        "susceptibility to corrosion, degradation propensity"),
    "cat_function": ("passivation function, current collection",
                     "protective function, load bearing"),
    "onto_quality": ("efficiency, open-circuit voltage, temperature, reflectance",
                     "efficiency, tensile strength, temperature, reflectance"),
    "onto_function": ("susceptibility to degradation, passivation function",
                      "susceptibility to degradation, protective function"),
    "onto_process": ("degradation, annealing, light soaking, deposition, an act of measuring",
                     "degradation, annealing, curing, deposition, an act of measuring"),
}


def domain_of(collection: dict) -> str:
    """The field a collection's papers come from, as the prompts name it."""
    return collection.get("domain", DEFAULT_DOMAIN)
# Keep only the N most-cited papers per collection that have a PDF (OpenAlex cited_by_count). None = all.
TOP_N_BY_CITATIONS = 50

# ---- Portal searches during enrichment: MDS-Onto portal (MDS_API_KEY) and MatPortal (MATPORTAL_API_KEY) ----
# Every ontology each portal hosts is searched (None = no acronym filter). A hit for a term in the ontology store
# joins the candidates; a hit outside the store is a facet hint only and is counted per ontology in run.json.
MDS_ONTOLOGIES = None       # or comma-separated portal acronyms, e.g. "MDS-ONTO,IOF,PMDCO,QUDT"
MATPORTAL = {"enabled": True, "base_url": "https://rest.matportal.org", "ontologies": None}
CANDIDATES_PER_PORTAL = 10  # results kept per portal search query
# Materials Project (MATERIALS_PROJECT_API_KEY): computed properties of the crystalline material a class names
# (src/tools/materials_project.py), attached to material-entity classes as annotations, never as mapping candidates.
MATERIALS_PROJECT = {"enabled": True, "base_url": "https://api.materialsproject.org",
                     "per_class": 3,                   # entries kept per class, most stable first
                     "max_energy_above_hull": 0.1}     # eV/atom; less stable polymorphs are left out

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
# KW_ONTOLOGY_STORE points a job at a private copy (scripts/slurm-sweep.sh) so a rebuild cannot break it mid-run
ONTOLOGY_STORE = Path(os.getenv("KW_ONTOLOGY_STORE") or CACHE / "ontology_store")
# The SQLite answer and embedding caches. Slurm jobs use node-local copies (scripts/cache_sync.py): SQLite locking
# does not work across the nodes of a network filesystem, and concurrent writers there corrupt the file.
ROWS_DB = Path(os.getenv("KW_ROWS_DB") or CACHE / "rows.sqlite3")
EMBED_DB = Path(os.getenv("KW_EMBED_DB") or CACHE / "embeddings.sqlite3")
ONTOLOGY_SEARCH = {
    "weights": {"lexical": 0.4, "cosine": 0.6},  # fused score: lexical = 1 for an exact label, else trigram similarity
    "min_score": 0.35,           # fused score a candidate needs (exact label matches are always kept)
    "min_fuzzy": 0.5,            # trigram similarity that counts as a lexical hit (labels must share a whole word)
    "min_cosine": 0.75,          # embedding cosine that counts as a semantic hit (nomic-embed-text: any two terms ~0.5)
    "candidates_per_class": 8,   # external candidates from the store shown per class (interop)
    "portal_per_class": 5,       # plus up to this many portal terms outside the store (SKOS mappings only),
    "portal_min_score": 0.6,     # each a same-name term or one with at least this fused score
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
# Local tier study stage and domain tags: "combined" = one call per batch returns both (default since 2026-10-15),
# "split" = a stage call and a domain call per batch, as before. KW_FACET_CALLS overrides it (the facets check).
FACET_CALLS = os.getenv("KW_FACET_CALLS", "combined")
MAPPING = {
    "strong_similarity": 0.85,   # label-matched candidate at/above this is auto-mapped as exact if the model skipped it
    "row_retries": 2,            # interop passes (screening, study stage, domain): rows left out are re-sent twice,
                                 # in batches of half, then a quarter, of the first size (at least 5)
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
WORKFLOW_REVISION = "2026-10-17-lineage-quality"
WORKFLOW_REVISION_NOTE = ("Exact original-to-canonical concept lineage, original-label retention through enrichment, "
                          "per-label paper provenance in OWL exports, and malformed extraction quarantine. "
                          "External terms from a local ontology store "
                          "(Oxigraph + trigram + embedding search over BFO, "
                          "CCO, RO, QUDT, PMDCO, IOF, MDS-Onto): placement parents (CCO, then BFO; same-name MDS-Onto/PMDCO "
                          "class wins), restriction properties, mapping candidates with 1-2 hop propagation; broader, "
                          "narrower and related matches; imported definitions and labels; MIREOT imports of every term; "
                          "v2: MDS-Onto portal and MatPortal searched over all their ontologies; v3: parent answers read "
                          "tolerantly (format variants, CCO/BFO class by name inside the category, close spellings), "
                          "ontology/uncertain.json, figures and grouped report after each run and integration; interop "
                          "passes re-send missing rows twice; answers inside an echoed schema are read; screening prompt "
                          "ends with an example answer instead of the schema; v4: portal terms outside the store are mapping "
                          "candidates (SKOS only), portal hits under another IRI of a store ontology matched by label; "
                          "v5: explicit row coverage, task batches and answer examples, downstream response and embedding "
                          "caches, early paper limits, short-section packing, deduplicated portal queries and vector top-k; "
                          "2026-10-14: BFO category from the extraction type (the model only marks non-classes), "
                          "model merge labels read as text, a restarting local server waited out for outage_wait_s; "
                          "2026-10-15: answers reused per identical row across runs (corpus sizes), study stage and "
                          "domain in one local call, definitions and disjointness in batches of 8, each sibling pair "
                          "asked once for disjointness (next siblings by label), overload halves the request limit; "
                          "2026-10-16: prompts name the collection's domain (default photovoltaics, unchanged); local "
                          "parent pass offers each concept its 5 nearest same-category corpus concepts by embedding "
                          "instead of one top-150 list; exact CCO/BFO label matches offered outside the category; fuzzy "
                          "label matches need a shared whole word; nomic query/document prefixes; fused weight 0.4/0.6 "
                          "lexical/cosine; 5 nearest store classes kept")
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
