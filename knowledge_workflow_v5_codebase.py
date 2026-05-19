# -*- coding: utf-8 -*-
"""
V5-Codebase: Provider-agnostic two-stage knowledge extraction from source code.

Mirrors the V5 Zotero pipeline but reads a local codebase instead of papers:
  - Unit of analysis : one class or top-level function per Python file
                       (equivalent to "one paper" in V5)
  - Phase 1          : extract ontology-ready concepts + study stage from each unit
  - Normalization    : deduplicate/merge near-synonyms across all units
  - Phase 2          : populate wide-format schema (value + code quote per concept)

Output files (saved to outputs/<codebase_name>/):
  concepts_<name>-v5codebase-<date>.csv   (flat: unit, file, canonical, code_term, study_stage, relevance)
  schema_<name>-v5codebase-<date>.csv     (wide: one row per unit, one column per concept)

Study stages are inferred by the LLM from code context.  Typical values seen in
MDS-Onto / PV-modeling codebases:
  Simulation, Modeling, DataProcessing, DataAnalysis, Characterization,
  Exposure, ParameterEstimation, Validation

Configuration (in order of precedence):
  1. Edit the CONFIG block below
  2. Environment variables: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
  3. .env file in project root
"""

from __future__ import annotations

import ast
import glob
import inspect
import json
import os
import re
import textwrap
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG — edit these or set the equivalent environment variables
# ---------------------------------------------------------------------------

# LLM provider (any OpenAI-compatible endpoint)
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.anthropic.com/v1')
LLM_API_KEY  = os.getenv('LLM_API_KEY',
               os.getenv('OPENAI_API_KEY',
               os.getenv('ANTHROPIC_API_KEY', '')))
MODEL        = os.getenv('LLM_MODEL', 'claude-sonnet-4-6')

# Codebase to scan
CODEBASE_DIR   = r'C:\Users\brent\dev\\'  # <-- change this
CODEBASE_NAME  = 'pvcollada'    + '/include'                  # <-- change this (used in filenames)
# Which file extensions to include
FILE_EXTENSIONS = ['.py', '.pvc2', '.xsd' ]

# Which paths/patterns to skip (relative to CODEBASE_DIR)
SKIP_PATTERNS = [
    '*/test*',
    '*/tests*',
    '*/_*',         # private/dunder modules
    '*/docs*',
    '*/setup.py',
    '*/conf.py',
    '*/conftest.py',
]

# Minimum non-blank lines for a unit to be included (filters out tiny stubs)
MIN_LINES = 10

# Maximum characters of source text sent to the LLM per unit  (~20k tokens)
UNIT_MAX_CHARS = 12_000

# Concepts to extract per unit in Phase 1
TOP_N_PER_UNIT = 20

# If True, skip Phase 1 and load concepts from an existing CSV
USE_CSV_CONCEPTS  = False
CONCEPTS_CSV_PATH = ''
CONCEPTS_COLUMN   = 'concept'

# Rate-limit delay between LLM calls (seconds)
RATE_LIMIT_DELAY = 0.5

# If your provider/model doesn't support forced tool_choice by name, set False.
FORCE_TOOL_CHOICE = True

# ---------------------------------------------------------------------------

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

# ---------------------------------------------------------------------------
# TOOL SCHEMAS
# ---------------------------------------------------------------------------

_EXTRACT_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_concepts',
        'description': (
            'Return key ontology-relevant concepts extracted from a Python '
            'class or module, together with the study stage each concept belongs to.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'concepts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'canonical': {
                                'type': 'string',
                                'description': (
                                    'Ontology-ready concept label: lowercase, 1-4 words, '
                                    'suitable as a reusable column header across multiple '
                                    'codebases. '
                                    'E.g. "cell temperature", "dc power output", '
                                    '"irradiance model", "angle of incidence", '
                                    '"ground cover ratio".'
                                )
                            },
                            'code_term': {
                                'type': 'string',
                                'description': (
                                    'The exact class name, attribute, parameter, or function '
                                    'name used in this code unit for that concept. '
                                    'E.g. "cell_temperature", "poa_global", "gcr", '
                                    '"SingleAxisTrackerMount".'
                                )
                            },
                            'study_stage': {
                                'type': 'string',
                                'description': (
                                    'The MDS-Onto study stage this concept belongs to. '
                                    'Infer from how the concept is used in the code. '
                                    'Typical values: Simulation, Modeling, DataProcessing, '
                                    'DataAnalysis, Characterization, Exposure, '
                                    'ParameterEstimation, Validation. '
                                    'Use the most specific stage that applies.'
                                )
                            },
                            'relevance': {
                                'type': 'number',
                                'description': (
                                    'Relevance score 0.0–1.0 indicating how central this '
                                    'concept is to the unit\'s purpose.'
                                )
                            }
                        },
                        'required': ['canonical', 'code_term', 'study_stage', 'relevance']
                    }
                }
            },
            'required': ['concepts']
        }
    }
}

_NORMALIZE_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_normalized_concepts',
        'description': (
            'Return a deduplicated, normalized list of ontology-ready concept labels '
            'distilled from candidate labels across the full codebase.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'concepts': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'description': (
                            'Canonical concept label: lowercase, 1-4 words, general '
                            'enough to apply across multiple classes or packages.'
                        )
                    }
                }
            },
            'required': ['concepts']
        }
    }
}

_SCHEMA_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_schema_values',
        'description': (
            'For each canonical concept, return the code-specific implementation '
            'detail and the most informative source line or docstring snippet.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'values': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'canonical': {
                                'type': 'string',
                                'description': 'The canonical concept label being answered.'
                            },
                            'value': {
                                'type': 'string',
                                'description': (
                                    'The specific identifier, type annotation, default value, '
                                    'or short description this code unit uses for the concept. '
                                    'Empty string if not present.'
                                )
                            },
                            'quote': {
                                'type': 'string',
                                'description': (
                                    'The single most informative line, docstring sentence, or '
                                    'short code snippet that defines or uses this concept. '
                                    'Empty string if not found.'
                                )
                            }
                        },
                        'required': ['canonical', 'value', 'quote']
                    }
                }
            },
            'required': ['values']
        }
    }
}

# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = (
    'You are a scientific software ontologist specialising in photovoltaic (PV) '
    'modeling and materials data science.\n'
    'You will be given Python source code for a single class or module from a PV '
    'modeling package (e.g. pvlib, PVsyst API, pv-collada).\n\n'
    'Your task: extract domain-specific concepts that should be represented in an '
    'OWL 2 ontology, providing TWO forms for each:\n'
    '1. canonical — a general, ontology-ready label (lowercase, 1-4 words) usable '
    'as a reusable column header across many PV packages. '
    'Good examples: "cell temperature", "dc power output", "irradiance model", '
    '"ground cover ratio", "angle of incidence correction". '
    'Bad examples: "sapm" (too specific/acronym), "result" (too vague), '
    '"0.25" (a value).\n'
    '2. code_term — the exact Python identifier (class, attribute, parameter, or '
    'function name) used in this specific code unit.\n\n'
    'Also assign a study_stage for each concept (infer from how it\'s used): '
    'Simulation, Modeling, DataProcessing, DataAnalysis, Characterization, '
    'Exposure, ParameterEstimation, or Validation.\n\n'
    'Focus on physical quantities, model parameters, algorithmic methods, '
    'performance metrics, and data structures. '
    'Score each 0.0–1.0 by centrality to the unit\'s purpose.'
)

_NORMALIZE_SYSTEM = (
    'You are a knowledge-graph ontologist specialising in photovoltaic systems '
    'and materials data science.\n'
    'You will receive candidate concept labels extracted by AI from multiple '
    'Python classes and modules in one or more PV modeling packages.\n\n'
    'Your task: return a clean, deduplicated, normalized set of ontology-ready '
    'labels suitable as column headers in an OWL 2 ontology schema.\n\n'
    'Rules:\n'
    '- Merge near-synonyms into one canonical form '
    '(e.g. "poa global irradiance", "plane of array irradiance", "poa_global" → '
    '"plane of array irradiance").\n'
    '- Keep labels lowercase, 1-4 words, general and reusable across packages.\n'
    '- Remove labels that are too vague ("result", "data", "model"), too specific '
    '("sapm_params_dict"), or exact duplicates.\n'
    '- Aim for 30–80 high-quality, distinct concepts covering the codebase.\n'
    '- Order them roughly by domain importance (most central PV concepts first).'
)

_SCHEMA_SYSTEM = (
    'You are a precise scientific software analyst.\n'
    'You will be given Python source code for a single class or module and a list '
    'of ontology concept labels.\n'
    'For EACH concept, find and return:\n'
    '  value — the exact Python identifier, type hint, default value, or very short '
    'description from this code unit (use the code\'s own terms). '
    'Empty string if not present.\n'
    '  quote — the single most informative line, docstring sentence, or short code '
    'snippet (≤120 chars) that best defines or uses this concept. '
    'Empty string if not found.\n\n'
    'Be precise. Do not paraphrase. Do not invent identifiers not in the code.'
)

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

def make_filename(codebase_name: str, username: str = 'Brent_Thompson',
                  version: str = '5codebase') -> str:
    date = datetime.now().strftime('%Y%m%d')
    name = codebase_name.replace(' ', '_').lower()
    return f"{name}-{username}-v{version}-{date}.csv"


def _tool_choice(name: str):
    if not FORCE_TOOL_CHOICE:
        return 'auto'
    return {'type': 'function', 'function': {'name': name}}


def _parse_tool_call(response, expected_name: str):
    msg = response.choices[0].message
    if not msg.tool_calls:
        return None
    for tc in msg.tool_calls:
        if tc.function.name == expected_name:
            try:
                return json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                return None
    try:
        return json.loads(msg.tool_calls[0].function.arguments)
    except json.JSONDecodeError:
        return None


def _should_skip(path: Path, base: Path) -> bool:
    rel = str(path.relative_to(base)).replace('\\', '/')
    for pat in SKIP_PATTERNS:
        if Path(rel).match(pat.lstrip('*/')):
            return True
        if pat.lstrip('*/') in rel:
            return True
    return False

# ---------------------------------------------------------------------------
# CODEBASE WALKER — splits files into class / module units
# ---------------------------------------------------------------------------

def _get_source_lines(filepath: Path) -> list[str]:
    try:
        return filepath.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:
        return []


def _dedent_block(lines: list[str]) -> str:
    return textwrap.dedent('\n'.join(lines))


def iter_code_units(codebase_dir: str | Path) -> Iterator[dict]:
    """
    Walk a codebase and yield one dict per class or top-level function:

        {
          'unit_id':   '<module>::<ClassName>',
          'unit_type': 'class' | 'function' | 'module',
          'file':      relative path string,
          'name':      class/function name,
          'docstring': first docstring (may be empty),
          'source':    full source text of the unit (truncated to UNIT_MAX_CHARS),
        }

    For files with no top-level classes or functions meeting MIN_LINES,
    the whole file is yielded as a 'module' unit.
    """
    base = Path(codebase_dir)
    for ext in FILE_EXTENSIONS:
        for filepath in sorted(base.rglob(f'*{ext}')):
            if _should_skip(filepath, base):
                continue

            rel = str(filepath.relative_to(base))
            source_lines = _get_source_lines(filepath)
            full_source   = '\n'.join(source_lines)

            try:
                tree = ast.parse(full_source, filename=str(filepath))
            except SyntaxError:
                # Yield as raw module unit on parse failure
                if len(source_lines) >= MIN_LINES:
                    yield {
                        'unit_id':   rel + '::module',
                        'unit_type': 'module',
                        'file':      rel,
                        'name':      filepath.stem,
                        'docstring': '',
                        'source':    full_source[:UNIT_MAX_CHARS],
                    }
                continue

            units_found = 0
            for node in ast.walk(tree):
                # Only process top-level classes and functions (depth == 1)
                if not isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                         ast.AsyncFunctionDef)):
                    continue
                # Skip private/dunder names unless it's __init__
                if node.name.startswith('_') and node.name != '__init__':
                    continue

                start = node.lineno - 1
                end   = node.end_lineno
                block_lines = source_lines[start:end]
                if len([l for l in block_lines if l.strip()]) < MIN_LINES:
                    continue

                docstring = ast.get_docstring(node) or ''
                unit_type = 'class' if isinstance(node, ast.ClassDef) else 'function'
                raw_source = _dedent_block(block_lines)

                yield {
                    'unit_id':   f"{rel}::{node.name}",
                    'unit_type': unit_type,
                    'file':      rel,
                    'name':      node.name,
                    'docstring': docstring[:800],
                    'source':    raw_source[:UNIT_MAX_CHARS],
                }
                units_found += 1

            # If nothing extracted, yield the whole file as a module unit
            if units_found == 0 and len(source_lines) >= MIN_LINES:
                yield {
                    'unit_id':   rel + '::module',
                    'unit_type': 'module',
                    'file':      rel,
                    'name':      filepath.stem,
                    'docstring': ast.get_docstring(tree) or '',
                    'source':    full_source[:UNIT_MAX_CHARS],
                }


def collect_units(codebase_dir: str | Path) -> dict[str, dict]:
    """
    Returns {unit_id: unit_dict} for all units found in the codebase.
    """
    units = {}
    for unit in iter_code_units(codebase_dir):
        units[unit['unit_id']] = unit
    return units

# ---------------------------------------------------------------------------
# AI AGENT — PHASE 1: CONCEPT EXTRACTION
# ---------------------------------------------------------------------------

def extract_concepts_from_unit(unit: dict, top_n: int = TOP_N_PER_UNIT) -> list[dict]:
    """
    Extract ontology concepts + study stages from one code unit.
    Returns [{canonical, code_term, study_stage, relevance}, ...] sorted by relevance.
    """
    header = (
        f"File: {unit['file']}\n"
        f"Unit: {unit['name']} ({unit['unit_type']})\n"
    )
    if unit['docstring']:
        header += f"Docstring: {unit['docstring'][:400]}\n\n"
    content = header + "Source code:\n\n" + unit['source']

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {'role': 'system', 'content': _EXTRACT_SYSTEM},
            {'role': 'user',   'content': (
                f'Extract the top {top_n} ontology-relevant concepts from this '
                f'Python code unit, with their study stage and code term.\n\n'
                f'{content}'
            )}
        ],
        tools=[_EXTRACT_TOOL],
        tool_choice=_tool_choice('return_concepts'),
    )
    result = _parse_tool_call(response, 'return_concepts')
    if result:
        concepts = result.get('concepts', [])
        return sorted(concepts, key=lambda c: c.get('relevance', 0), reverse=True)[:top_n]
    return []


def build_concept_table(units: dict, top_n: int = TOP_N_PER_UNIT):
    """
    Phase 1: Run per-unit concept extraction across the codebase.

    Returns:
      df_concepts    — flat DataFrame (unit_id, file, name, unit_type,
                                       canonical, code_term, study_stage, relevance)
      all_canonicals — list of all raw canonical labels (with duplicates)
    """
    rows = []
    all_canonicals = []
    unit_list = list(units.values())
    total = len(unit_list)

    for i, unit in enumerate(unit_list, 1):
        print(f'  [{i}/{total}] Extracting: {unit["unit_id"][:80]}')
        concepts = extract_concepts_from_unit(unit, top_n=top_n)
        for c in concepts:
            canon = c.get('canonical', '').strip().lower()
            rows.append({
                'unit_id':    unit['unit_id'],
                'file':       unit['file'],
                'name':       unit['name'],
                'unit_type':  unit['unit_type'],
                'canonical':  canon,
                'code_term':  c.get('code_term', ''),
                'study_stage': c.get('study_stage', ''),
                'relevance':  round(c.get('relevance', 0), 4),
            })
            all_canonicals.append(canon)
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return pd.DataFrame(rows), all_canonicals


def normalize_concept_list(all_canonicals: list[str]) -> list[str]:
    """
    Deduplication / normalization pass: merges near-synonyms, returns
    a clean list of 30–80 ontology-ready concept labels.
    """
    unique = sorted(set(c for c in all_canonicals if c))
    if not unique:
        return []

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {'role': 'system', 'content': _NORMALIZE_SYSTEM},
            {'role': 'user',   'content': (
                f'Here are {len(unique)} candidate concept labels extracted from '
                f'Python source code in PV modeling packages. '
                f'Normalize and deduplicate into a clean ontology-ready list '
                f'(30–80 concepts).\n\n'
                + '\n'.join(f'- {c}' for c in unique)
            )}
        ],
        tools=[_NORMALIZE_TOOL],
        tool_choice=_tool_choice('return_normalized_concepts'),
    )
    result = _parse_tool_call(response, 'return_normalized_concepts')
    if result:
        return [c.strip().lower() for c in result.get('concepts', []) if c.strip()]
    return unique[:80]

# ---------------------------------------------------------------------------
# AI AGENT — PHASE 2: SCHEMA POPULATION
# ---------------------------------------------------------------------------

def populate_schema_row(unit: dict, canonical_concepts: list[str]) -> dict:
    """
    For one code unit and the normalized concept list, extract the code-specific
    value and source quote for each concept.

    Returns: {canonical: {'value': str, 'quote': str}}
    """
    empty = {c: {'value': '', 'quote': ''} for c in canonical_concepts}
    source = unit.get('source', '')
    if not source:
        return empty

    header = f"File: {unit['file']}\nUnit: {unit['name']} ({unit['unit_type']})\n\n"
    content = header + source[:UNIT_MAX_CHARS]
    concept_list = '\n'.join(f'- {c}' for c in canonical_concepts)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {'role': 'system', 'content': _SCHEMA_SYSTEM},
            {'role': 'user',   'content': (
                f'Python source code:\n\n{content}\n\n'
                f'---\n'
                f'For each concept below, return the code-specific value '
                f'and source quote:\n\n{concept_list}'
            )}
        ],
        tools=[_SCHEMA_TOOL],
        tool_choice=_tool_choice('return_schema_values'),
    )
    result = _parse_tool_call(response, 'return_schema_values')
    if not result:
        return empty

    out = empty.copy()
    for item in result.get('values', []):
        canon = item.get('canonical', '').strip().lower()
        if canon in out:
            out[canon] = {
                'value': item.get('value', '').strip(),
                'quote': item.get('quote', '').strip(),
            }
    return out


def build_schema_csv(units: dict, canonical_concepts: list[str],
                     domain: str) -> pd.DataFrame:
    """
    Phase 2: Build the wide-format schema DataFrame.

    One row per code unit:
      domain, unit_id, file, unit_type,
      <concept_1> ... <concept_N>  —  "value | source quote"
    """
    rows = []
    unit_list = list(units.values())
    total = len(unit_list)

    for i, unit in enumerate(unit_list, 1):
        print(f'  [{i}/{total}] Schema row: {unit["unit_id"][:80]}')
        schema_data = populate_schema_row(unit, canonical_concepts)

        row = {
            'domain':    domain,
            'unit_id':   unit['unit_id'],
            'file':      unit['file'],
            'unit_type': unit['unit_type'],
        }
        for concept in canonical_concepts:
            cv    = schema_data.get(concept, {'value': '', 'quote': ''})
            value = cv.get('value', '')
            quote = cv.get('quote', '')
            if value and quote:
                row[concept] = f'{value} | {quote}'
            elif value:
                row[concept] = value
            elif quote:
                row[concept] = quote
            else:
                row[concept] = ''
        rows.append(row)
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    fixed_cols = ['domain', 'unit_id', 'file', 'unit_type']
    columns    = fixed_cols + canonical_concepts
    return pd.DataFrame(rows, columns=columns)

# ---------------------------------------------------------------------------
# STUDY-STAGE SUMMARY  (bonus output)
# ---------------------------------------------------------------------------

def build_study_stage_summary(df_concepts: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot the flat concepts table to show, for each canonical concept,
    which study stages were assigned and how often.

    Returns DataFrame: canonical | most_common_stage | stage_counts | unit_count
    """
    if df_concepts.empty:
        return pd.DataFrame()

    summary = []
    for canon, grp in df_concepts.groupby('canonical'):
        stage_counts = grp['study_stage'].value_counts().to_dict()
        most_common  = grp['study_stage'].mode().iloc[0] if not grp['study_stage'].empty else ''
        summary.append({
            'canonical':        canon,
            'most_common_stage': most_common,
            'stage_counts':     json.dumps(stage_counts),
            'unit_count':       grp['unit_id'].nunique(),
            'avg_relevance':    round(grp['relevance'].mean(), 4),
        })

    return (pd.DataFrame(summary)
              .sort_values('avg_relevance', ascending=False)
              .reset_index(drop=True))

# ---------------------------------------------------------------------------
# WORKFLOW
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    print(f'Provider : {LLM_BASE_URL}')
    print(f'Model    : {MODEL}')
    print(f'Codebase : {CODEBASE_DIR}')
    print(f'Name     : {CODEBASE_NAME}\n')

    # 1. Walk codebase and split into class/function units
    print('[Scan] Walking codebase and extracting code units ...')
    units = collect_units(CODEBASE_DIR)
    print(f'  Found {len(units)} units (classes + functions + module fallbacks).')

    if not units:
        print('ERROR: No code units found. Check CODEBASE_DIR and FILE_EXTENSIONS.')
        raise SystemExit(1)

    # Report distribution
    type_counts = {}
    for u in units.values():
        type_counts[u['unit_type']] = type_counts.get(u['unit_type'], 0) + 1
    for k, v in sorted(type_counts.items()):
        print(f'  {k}: {v}')

    # -----------------------------------------------------------------------
    # Concept list: extract fresh or load from CSV
    # -----------------------------------------------------------------------
    if USE_CSV_CONCEPTS and CONCEPTS_CSV_PATH:
        print(f'\n[Concepts] Loading from CSV: {CONCEPTS_CSV_PATH}')
        normalized_concepts = (
            pd.read_csv(CONCEPTS_CSV_PATH)[CONCEPTS_COLUMN]
            .dropna().str.strip().str.lower().tolist()
        )
        print(f'  Loaded {len(normalized_concepts)} concepts.')
        df_concepts = pd.DataFrame()

    else:
        # Phase 1 — extract per-unit concepts
        print(f'\n[Phase 1] Extracting concepts ({TOP_N_PER_UNIT}/unit) with {MODEL} ...')
        df_concepts, all_canonicals = build_concept_table(units, top_n=TOP_N_PER_UNIT)
        print(f'  {len(df_concepts)} concept-unit pairs extracted.')
        print(f'  {len(set(all_canonicals))} unique raw canonical labels.')

        # Normalization pass
        print(f'\n[Normalization] Normalizing concept list with {MODEL} ...')
        time.sleep(RATE_LIMIT_DELAY)
        normalized_concepts = normalize_concept_list(all_canonicals)
        print(f'  Normalized to {len(normalized_concepts)} canonical concepts:')
        for c in normalized_concepts[:10]:
            print(f'    - {c}')
        if len(normalized_concepts) > 10:
            print(f'    ... and {len(normalized_concepts) - 10} more')

    # -----------------------------------------------------------------------
    # Phase 2 — populate schema rows from unit source
    # -----------------------------------------------------------------------
    print(f'\n[Phase 2] Building schema CSV '
          f'({len(normalized_concepts)} concept columns) with {MODEL} ...')
    df_schema = build_schema_csv(units, normalized_concepts, CODEBASE_NAME)

    # -----------------------------------------------------------------------
    # Study-stage summary (bonus pivot)
    # -----------------------------------------------------------------------
    df_stages = build_study_stage_summary(df_concepts)

    # -----------------------------------------------------------------------
    # Save outputs
    # -----------------------------------------------------------------------
    out_dir = os.path.join('outputs', CODEBASE_NAME.lower())
    os.makedirs(out_dir, exist_ok=True)
    prefix = make_filename(CODEBASE_NAME)

    if not df_concepts.empty:
        concepts_file = os.path.join(out_dir, f'concepts_{prefix}')
        df_concepts.to_csv(concepts_file, index=False)
        print(f'\nSaved: {concepts_file}')

    schema_file = os.path.join(out_dir, f'schema_{prefix}')
    df_schema.to_csv(schema_file, index=False)
    print(f'Saved: {schema_file}')

    if not df_stages.empty:
        stages_file = os.path.join(out_dir, f'study_stages_{prefix}')
        df_stages.to_csv(stages_file, index=False)
        print(f'Saved: {stages_file}')

    # Copy schema to schemas/<codebase>/ for reuse
    schema_dir = os.path.join('schemas', CODEBASE_NAME.lower())
    os.makedirs(schema_dir, exist_ok=True)
    schema_copy = os.path.join(schema_dir, f'schema_{prefix}')
    df_schema.to_csv(schema_copy, index=False)
    print(f'Saved: {schema_copy}')

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------
    if not df_concepts.empty:
        print('\n--- Concept extraction (top 20 rows by relevance) ---')
        print(df_concepts.sort_values('relevance', ascending=False)
                         .head(20)
                         .to_string(index=False))

    if not df_stages.empty:
        print('\n--- Study-stage summary (top 15 concepts) ---')
        print(df_stages.head(15).to_string(index=False))

    print(f'\n--- Schema CSV preview ---')
    print(f'Shape: {df_schema.shape[0]} rows × {df_schema.shape[1]} columns')
    preview_cols = ['domain', 'unit_id', 'file'] + normalized_concepts[:4]
    available    = [c for c in preview_cols if c in df_schema.columns]
    print(df_schema[available].head(5).to_string())
    print(f'\nAll concept columns ({len(normalized_concepts)}):')
    for c in normalized_concepts:
        print(f'  {c}')
