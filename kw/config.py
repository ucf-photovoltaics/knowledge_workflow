# -*- coding: utf-8 -*-
"""
Centralised configuration + the canonical namespace registry.

Precedence: environment variables > .env > defaults below.
Import the shared `pydantic_model` from here; never instantiate clients elsewhere.
"""

import os
from dotenv import load_dotenv
from pydantic_ai import NativeOutput, PromptedOutput

# Version-robust import: pydantic-ai >=2 renamed OpenAIModel -> OpenAIChatModel.
try:
    from pydantic_ai.models.openai import OpenAIModel as _OpenAIModel
except ImportError:                                  # pydantic-ai >= 2.0
    from pydantic_ai.models.openai import OpenAIChatModel as _OpenAIModel

load_dotenv()

# ---------------------------------------------------------------------------
# Zotero
# ---------------------------------------------------------------------------
ZOTERO_LIBRARY_ID   = os.getenv('ZOTERO_LIBRARY_ID',   '2189702')
ZOTERO_LIBRARY_TYPE = os.getenv('ZOTERO_LIBRARY_TYPE', 'group')
ZOTERO_API_KEY      = os.getenv('ZOTERO_API_KEY',      '')
COLLECTION_ID       = os.getenv('COLLECTION_ID',       '5NLP8DAI')

# ---------------------------------------------------------------------------
# LLM provider — any OpenAI-compatible endpoint
# ---------------------------------------------------------------------------
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.anthropic.com/v1')
LLM_API_KEY  = os.getenv('LLM_API_KEY',
                         os.getenv('OPENAI_API_KEY', os.getenv('ANTHROPIC_API_KEY', '')))
MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')
# RESERVED: read but not yet wired into the agents. See LLM_OUTPUT_MODE below.
FORCE_TOOL_CHOICE = os.getenv('FORCE_TOOL_CHOICE', 'true').lower() != 'false'

# How agents get structured output: tool | native | prompted
LLM_OUTPUT_MODE = os.getenv('LLM_OUTPUT_MODE', 'tool').lower()


def output_spec(output_type):
    """Wrap an agent's result type according to LLM_OUTPUT_MODE."""
    if LLM_OUTPUT_MODE == 'native':
        return NativeOutput(output_type)
    if LLM_OUTPUT_MODE == 'prompted':
        return PromptedOutput(output_type)
    return output_type  # 'tool' (default)

# ---------------------------------------------------------------------------
# Pipeline parameters
# ---------------------------------------------------------------------------
RATE_LIMIT_DELAY    = float(os.getenv('RATE_LIMIT_DELAY',    '0.2'))
TOP_N_PER_PAPER     = int(os.getenv('TOP_N_PER_PAPER',       '40'))
FULL_TEXT_MAX_CHARS = int(os.getenv('FULL_TEXT_MAX_CHARS',   '80000'))
BATCH_SIZE          = int(os.getenv('BATCH_SIZE',            '40'))
# Concept extraction dials (also exposed as CLI flags --top-n/--min-relevance/--max-concepts).
MIN_RELEVANCE       = float(os.getenv('MIN_RELEVANCE',        '0.5'))  # drop concepts below this score
MAX_CONCEPTS        = int(os.getenv('MAX_CONCEPTS',          '100'))     # 0 = no hard cap (normalizer targets 30-80)
# Step 1 concept source: 'abstract' | 'abstract+intro' | 'full-text' (chunks whole paper).
CONCEPT_SOURCE      = os.getenv('CONCEPT_SOURCE', 'full-text').lower()
INTRO_MAX_CHARS     = int(os.getenv('INTRO_MAX_CHARS',       '18000'))   # cap on sliced intro length

MDS_ONTO_LIBRARY          = os.getenv('MDS_ONTO_LIBRARY',          os.path.join('data', 'mds_onto.json'))
CEMENTO_TEMPLATES_LIBRARY = os.getenv('CEMENTO_TEMPLATES_LIBRARY', os.path.join('data', 'cemento-templates.xml'))

OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')
SCHEMAS_DIR = os.getenv('SCHEMAS_DIR', 'schemas')

# ---------------------------------------------------------------------------
# Visualization + benchmarking (runs at the end of the pipeline)
# ---------------------------------------------------------------------------
EMIT_VISUAL        = os.getenv('EMIT_VISUAL', 'true').lower() != 'false'
VISUAL_WITH_VALUES = os.getenv('VISUAL_WITH_VALUES', 'true').lower() == 'true'
# Cumulative one-row-per-run benchmark log (sits next to eval/metrics.csv).
BENCHMARK_CSV      = os.getenv('BENCHMARK_CSV', os.path.join('eval', 'graph_benchmark.csv'))

# ---------------------------------------------------------------------------
# Resilience (T4.2) + checkpointing (T4.1)
# ---------------------------------------------------------------------------
LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', '3'))
LLM_BACKOFF     = float(os.getenv('LLM_BACKOFF',   '2.0'))
USE_CHECKPOINT  = os.getenv('USE_CHECKPOINT', 'true').lower() != 'false'

# Long-text mining via chunking (T3.3). Off by default = legacy truncation.
CHUNK_FULL_TEXT = os.getenv('CHUNK_FULL_TEXT', 'true').lower() == 'true'
CHUNK_SIZE      = int(os.getenv('CHUNK_SIZE',    '15000'))
CHUNK_OVERLAP   = int(os.getenv('CHUNK_OVERLAP', '2500'))
# Mining concurrency: >1 mines papers in parallel (needs a backend that serves
# parallel requests, e.g. Ollama with OLLAMA_NUM_PARALLEL>=2). 1 = sequential.
MINE_WORKERS    = int(os.getenv('MINE_WORKERS', '2'))

# Validation gate switches (T1.1/T1.2/T1.3). Reasoner/SHACL off by default,
# degrade gracefully. OOPS! is ON because it is a REQUIRED gate check (see below).
RUN_REASONER   = os.getenv('RUN_REASONER', 'false').lower() == 'true'
RUN_OOPS       = os.getenv('RUN_OOPS',     'true').lower() == 'true'
RUN_SHACL      = os.getenv('RUN_SHACL',    'false').lower() == 'true'
OOPS_ENDPOINT  = os.getenv('OOPS_ENDPOINT', 'https://oops.linkeddata.es/rest')
SHACL_SHAPES   = os.getenv('SHACL_SHAPES',
                           os.path.join(os.path.dirname(__file__), 'shapes', 'mds_shapes.ttl'))

# ---------------------------------------------------------------------------
# Validation gate (Step 4): which checks must PASS before the MDS-Onto upload.
# ---------------------------------------------------------------------------
# REQUIRED checks block the OntoPortal upload when they do not pass. Strict
# semantics: a required check that errors / cannot run counts as NOT pass.
# Advisory checks are always reported but never block. Comma-separated names;
# known: ontocheck, oops, alignment, reasoner, shacl.
REQUIRED_CHECKS = {c.strip().lower() for c in
                   os.getenv('REQUIRED_CHECKS', 'ontocheck,oops').split(',') if c.strip()}

# --- OntoCheck (CWRU SDLE) — required benchmark ---------------------------
RUN_ONTOCHECK = os.getenv('RUN_ONTOCHECK', 'true').lower() != 'false'
# Metrics whose result must pass for the ontocheck gate to pass. Each has a
# pass rule applied in validate.py. Coverage-style metrics use the targets below.
ONTOCHECK_GATE_METRICS = {m.strip() for m in os.getenv(
    'ONTOCHECK_GATE_METRICS',
    'duplicateLabels,missingDomainRange,mdsDesignCheck,humanLicense,'
    'isolatedElements,definitionCoverage').split(',') if m.strip()}
# Coverage thresholds (fraction 0-1 of classes that must comply).
MDS_DESIGN_TARGET          = float(os.getenv('MDS_DESIGN_TARGET',          '0.90'))
DEFINITION_COVERAGE_TARGET = float(os.getenv('DEFINITION_COVERAGE_TARGET', '0.90'))
# Run the remaining (non-gate) metrics for the report. Network metrics
# (externalLinks/rdfDump/sparqlEndpoint) are advisory and only run when allowed.
ONTOCHECK_RUN_ADVISORY = os.getenv('ONTOCHECK_RUN_ADVISORY', 'true').lower() != 'false'
ONTOCHECK_NETWORK      = os.getenv('ONTOCHECK_NETWORK', 'false').lower() == 'true'

# Provenance: ORCID stamped as dcterms:creator on every emitted entry (§7.1).
# Empty -> the triple is skipped. Set to your ORCID (e.g. 0000-0002-1234-5678).
CREATOR_ORCID = os.getenv('CREATOR_ORCID', '')
# Which canonical-property selection passes are active (kw/mds_props.py).
# 'deterministic' = Pass 1 only; 'hybrid' = + shortlisted-LLM fallback for the tail.
PROPERTY_SELECTION = os.getenv('PROPERTY_SELECTION', 'hybrid').lower()

# OntoPortal submission (opt-in). Uses MDSONTO_PORTAL + MDSONTO_API_KEY from mdsonto.py.
SUBMIT_TO_PORTAL         = os.getenv('SUBMIT_TO_PORTAL', 'true').lower() == 'true'
PORTAL_ONTOLOGY_ACRONYM  = os.getenv('PORTAL_ONTOLOGY_ACRONYM', '')
PORTAL_ONTOLOGY_NAME     = os.getenv('PORTAL_ONTOLOGY_NAME', '')
PORTAL_CONTACT_NAME      = os.getenv('PORTAL_CONTACT_NAME', '')
PORTAL_CONTACT_EMAIL     = os.getenv('PORTAL_CONTACT_EMAIL', '')

# Entity resolution / merge (T3.1) + LoRA adapter hook (T1.5)
MERGE_REBEL       = os.getenv('MERGE_REBEL', 'true').lower() != 'false'
MERGE_SIM_THRESHOLD = float(os.getenv('MERGE_SIM_THRESHOLD', '0.70'))
LORA_ADAPTER_PATH = os.getenv('LORA_ADAPTER_PATH', '')

# ---------------------------------------------------------------------------
# Ontology shape (domain-richness vs upper-ontology weight)
# ---------------------------------------------------------------------------
# BFO grounding is OFF by default — it adds upper-ontology parents that bloat the
# graph for a focused domain. Turn on only when you need BFO interoperability.
GROUND_BFO       = os.getenv('GROUND_BFO', 'false').lower() == 'true'
# Promote each concept to an owl:Class under its MDS branch (domain taxonomy).
CONCEPT_CLASSES  = os.getenv('CONCEPT_CLASSES', 'true').lower() != 'false'
# Generate a one-line skos:definition per concept (one batched LLM pass).
DEFINE_CONCEPTS  = os.getenv('DEFINE_CONCEPTS', 'true').lower() != 'false'
# Infer concept-to-concept relationships with the LLM (in addition to REBEL).
RELATE_CONCEPTS  = os.getenv('RELATE_CONCEPTS', 'true').lower() != 'false'

# ---------------------------------------------------------------------------
# Canonical namespace registry
# ---------------------------------------------------------------------------
NS = {
    'mds':  'https://cwrusdle.bitbucket.io/mds/',
    'bfo':  'http://purl.obolibrary.org/obo/BFO_',
    'cco':  'https://www.commoncoreontologies.org/',
    'qudt': 'http://qudt.org/schema/qudt/',
    'prov': 'http://www.w3.org/ns/prov#',
    'skos': 'http://www.w3.org/2004/02/skos/core#',
}
MDS_NS = NS['mds']
load_dotenv()


def _make_model():
    try:
        from pydantic_ai.providers.openai import OpenAIProvider
        return _OpenAIModel(MODEL, provider=OpenAIProvider(base_url=LLM_BASE_URL,
                                                           api_key=LLM_API_KEY))
    except Exception:
        return _OpenAIModel(MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


pydantic_model = _make_model()
