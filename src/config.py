# -*- coding: utf-8 -*-
"""
Centralised configuration for the knowledge workflow.

All environment variables and constants are defined here.
Import `llm_client` and `zotero_config` from this module rather than
instantiating them in individual agents or tools.

Precedence (highest first):
  1. Environment variables
  2. .env file in project root
  3. Defaults below
"""

import os
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIModel

load_dotenv()

# ---------------------------------------------------------------------------
# Zotero
# ---------------------------------------------------------------------------
ZOTERO_LIBRARY_ID   = os.getenv('ZOTERO_LIBRARY_ID',   '2189702')
ZOTERO_LIBRARY_TYPE = os.getenv('ZOTERO_LIBRARY_TYPE',  'group')
ZOTERO_API_KEY      = os.getenv('ZOTERO_API_KEY',       '')

# Default collection to process (can be overridden in main.py or via env var)
COLLECTION_ID       = os.getenv('COLLECTION_ID',        'VWMCLGL5')

# ---------------------------------------------------------------------------
# LLM provider — any OpenAI-compatible endpoint
#
#   Provider        BASE_URL                              MODEL example
#   --------        --------                              ------------
#   OpenAI          https://api.openai.com/v1             gpt-4o
#   Anthropic       https://api.anthropic.com/v1          claude-sonnet-4-6
#   Groq            https://api.groq.com/openai/v1        llama-3.3-70b-versatile
#   Ollama (local)  http://localhost:11434/v1              llama3.2
#   LM Studio       http://localhost:1234/v1               <loaded-model-name>
# ---------------------------------------------------------------------------
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.anthropic.com/v1')
LLM_API_KEY  = os.getenv(
    'LLM_API_KEY',
    os.getenv('OPENAI_API_KEY', os.getenv('ANTHROPIC_API_KEY', ''))
)
MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')

# If your provider/model doesn't support forced tool_choice by name, set False.
FORCE_TOOL_CHOICE = os.getenv('FORCE_TOOL_CHOICE', 'true').lower() != 'false'

# ---------------------------------------------------------------------------
# Pipeline parameters
# ---------------------------------------------------------------------------
RATE_LIMIT_DELAY    = float(os.getenv('RATE_LIMIT_DELAY',    '0.5'))   # seconds between LLM calls
TOP_N_PER_PAPER     = int(os.getenv('TOP_N_PER_PAPER',       '25'))    # concepts per paper (Phase 1)
FULL_TEXT_MAX_CHARS = int(os.getenv('FULL_TEXT_MAX_CHARS',   '80000')) # ~20k tokens

# ---------------------------------------------------------------------------
# Diagram / tagging parameters
# ---------------------------------------------------------------------------
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '40'))   # concepts per LLM tagging call

# Library files to embed as palette pages in every generated diagram
MDS_ONTO_LIBRARY          = os.getenv('MDS_ONTO_LIBRARY',          'mds_onto.json')
CEMENTO_TEMPLATES_LIBRARY = os.getenv('CEMENTO_TEMPLATES_LIBRARY',  'cemento-templates.xml')

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------
OUTPUTS_DIR = os.getenv('OUTPUTS_DIR', 'outputs')
SCHEMAS_DIR = os.getenv('SCHEMAS_DIR', 'schemas')

# ---------------------------------------------------------------------------
# Optional: skip Phase 1 and reuse an existing concept list
# ---------------------------------------------------------------------------
USE_CSV_CONCEPTS  = os.getenv('USE_CSV_CONCEPTS',  'false').lower() == 'true'
CONCEPTS_CSV_PATH = os.getenv('CONCEPTS_CSV_PATH', '')
CONCEPTS_COLUMN   = os.getenv('CONCEPTS_COLUMN',   'concept')

# ---------------------------------------------------------------------------
# Shared PydanticAI model (imported by agents)
#
# OpenAIModel accepts any OpenAI-compatible endpoint via base_url, so the
# same object works for Anthropic's compat layer, Groq, Ollama, etc.
# ---------------------------------------------------------------------------
pydantic_model = OpenAIModel(MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
