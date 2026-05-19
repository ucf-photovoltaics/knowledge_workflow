# -*- coding: utf-8 -*-
"""
V6: Draw.io concept map generator with MDS-Onto metadata enrichment.

Automatically processes every concepts_*.csv produced by the V5 workflow
and generates one enriched CSV + one draw.io diagram per file.

Pipeline (runs once per concepts file found):
  1. Discover all concepts_*.csv files under OUTPUTS_DIR (V5 output location).
  2. Load unique canonical concept labels from each file.
  3. Call an LLM to tag every concept with:
       mds:studyStage        — one or more MDS-Onto study stages
       mds:supplyChainLevel  — one or more supply chain levels
  4. Save an enriched concepts CSV with those two new columns.
  5. Write a .drawio file with:
       Page 1  — concept map (nodes coloured by study stage)
       Page 2  — MDS-Onto Library (from mds_onto.json)
       Page 3  — Cemento Templates (from cemento-templates.xml)

The library pages are embedded directly from the existing mxlibrary files so
they are always up-to-date and require no manual "Load Library" step.

Configuration — edit the CONFIG block below, or set environment variables.

Override:
  Set INPUT_CSV to a single file path to process just that one file.
"""

from openai import OpenAI
import pandas as pd
import os, glob, json, time, math
import html as _html
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Leave '' to process ALL concepts_*.csv files found under OUTPUTS_DIR.
# Set to a specific file path to process just that one file.
INPUT_CSV = ''

# Where V5 saves its concepts_*.csv files (outputs/<collection>/).
OUTPUTS_DIR = 'outputs'

# mxlibrary files to embed as palette pages in every generated diagram.
# Paths are relative to the working directory (same folder as this script).
MDS_ONTO_LIBRARY          = 'mds_onto.json'
CEMENTO_TEMPLATES_LIBRARY = 'cemento-templates.xml'

# LLM — same defaults as V5 (Anthropic via openai-compat layer)
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.anthropic.com/v1')
LLM_API_KEY  = os.getenv('LLM_API_KEY',  os.getenv('ANTHROPIC_API_KEY', os.getenv('OPENAI_API_KEY', '')))
MODEL        = os.getenv('LLM_MODEL',    'claude-sonnet-4-6')

# How many concepts to send in one LLM call (keep ≤ 50 for reliability)
BATCH_SIZE = 40

RATE_LIMIT_DELAY = 0.5   # seconds between batch calls

# ---------------------------------------------------------------------------
# NODE & GROUP LAYOUT
# ---------------------------------------------------------------------------
NODE_W         = 160   # concept node width
NODE_H         = 55    # concept node height
GAP_X          = 15    # horizontal gap between nodes inside a group
GAP_Y          = 15    # vertical gap between nodes inside a group
GROUP_COLS_MAX = 8     # hard cap on nodes-per-row inside any swimlane
GROUP_COLS_MIN = 3     # minimum nodes-per-row (keeps small groups readable)
HEADER_H       = 36    # swimlane header height (shows stage name)
GROUP_PAD      = 12    # padding inside group between border and nodes
GRID_GAP       = 55    # gap between groups on the canvas
MARGIN         = 60    # outer canvas margin
CENTER_MIN_W   = 500   # minimum width of the centre blank workspace
CENTER_MIN_H   = 400   # minimum height of the centre blank workspace

# ---------------------------------------------------------------------------
# MDS-ONTO VOCABULARY
# ---------------------------------------------------------------------------

STUDY_STAGES = [
    'synthesis',
    'formulation',
    'materials processing',
    'sample',
    'tool',
    'recipe',
    'data',
    'data processing',
    'result',
    'analysis',
    'modeling',
    'results and metadata',
]

SUPPLY_CHAIN_LEVELS = [
    'materials',
    'subcomponent',
    'component',
    'assembly',
    'subsystem',
    'system',
]

# Colour per study stage (fill, stroke)
_STAGE_COLORS = {
    'synthesis':            ('#f4cccc', '#cc0000'),
    'formulation':          ('#fce5cd', '#e06c00'),
    'materials processing': ('#ead1dc', '#a64d79'),
    'sample':               ('#fff2cc', '#d6b656'),
    'tool':                 ('#dae8fc', '#3e7fc1'),
    'recipe':               ('#d5e8d4', '#82b366'),
    'data':                 ('#cfe2f3', '#4a86e8'),
    'data processing':      ('#f8cecc', '#b85450'),
    'result':               ('#d9ead3', '#38761d'),
    'analysis':             ('#e1d5e7', '#9673a6'),
    'modeling':             ('#ffe6cc', '#d79b00'),
    'results and metadata': ('#d0e0e3', '#006eaf'),
    'unclassified':         ('#f5f5f5', '#888888'),
    'unknown':              ('#ffffff', '#aaaaaa'),
}

_ZONE_TOP    = ['synthesis', 'formulation', 'materials processing', 'sample']
_ZONE_LEFT   = ['tool', 'data']
_ZONE_RIGHT  = ['recipe', 'data processing']
_ZONE_BOTTOM = ['result', 'analysis', 'modeling', 'results and metadata']
_ALL_ZONES   = _ZONE_TOP + _ZONE_LEFT + _ZONE_RIGHT + _ZONE_BOTTOM


def _stage_color(stage_str: str):
    """Return (fill, stroke) for the primary (first) study stage."""
    if not stage_str:
        return _STAGE_COLORS['unknown']
    first = stage_str.split(',')[0].strip().lower()
    return _STAGE_COLORS.get(first, _STAGE_COLORS['unknown'])

# ---------------------------------------------------------------------------
# LLM CLIENT
# ---------------------------------------------------------------------------

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

# ---------------------------------------------------------------------------
# TOOL SCHEMA
# ---------------------------------------------------------------------------

_TAG_TOOL = {
    'type': 'function',
    'function': {
        'name': 'return_tagged_concepts',
        'description': (
            'For each concept in the list, return the applicable MDS-Onto '
            'study stage(s) and supply chain level(s).'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'tagged_concepts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'concept': {
                                'type': 'string',
                                'description': 'The concept label, exactly as provided.'
                            },
                            'mds_study_stage': {
                                'type': 'array',
                                'description': (
                                    'One or more MDS-Onto study stages that best '
                                    'describe where this concept is used in a '
                                    'materials data science workflow.'
                                ),
                                'items': {
                                    'type': 'string',
                                    'enum': STUDY_STAGES,
                                }
                            },
                            'mds_supply_chain_level': {
                                'type': 'array',
                                'description': (
                                    'One or more supply chain levels that best '
                                    'describe the physical scale or integration '
                                    'level of this concept.'
                                ),
                                'items': {
                                    'type': 'string',
                                    'enum': SUPPLY_CHAIN_LEVELS,
                                }
                            },
                        },
                        'required': ['concept', 'mds_study_stage', 'mds_supply_chain_level'],
                    }
                }
            },
            'required': ['tagged_concepts'],
        }
    }
}

_TAG_SYSTEM = (
    'You are an ontologist specialising in materials data science (MDS). '
    'You will receive concept labels from solar cell / semiconductor literature. '
    'For each concept assign EXACTLY one primary mds:studyStage (the stage '
    'where the concept most naturally lives) and one or more mds:supplyChainLevel values.\n\n'

    '--- MDS-Onto STUDY STAGES (pick the single best fit) ---\n\n'

    'synthesis\n'
    '  Creating a new chemical substance or material by forming new chemical bonds.\n'
    '  Ex: CVD growth, electrodeposition, sol-gel synthesis, polymer synthesis from monomers,\n'
    '      selenization reaction, SILAR deposition, atomic layer deposition.\n\n'

    'formulation\n'
    '  Mixing or combining existing substances into a functional product WITHOUT new bond formation.\n'
    '  Ex: preparing precursor ink/solution, blending solvents, formulating a perovskite suspension,\n'
    '      preparing a CdCl2 treatment solution, mixing dopant solutions.\n\n'

    'materials processing\n'
    '  Physical, thermal, or mechanical transformation of a material toward its final form.\n'
    '  Ex: annealing, sintering, etching, CdCl2 heat treatment, scribing, polishing,\n'
    '      laser ablation patterning, module lamination, encapsulation process steps.\n\n'

    'sample\n'
    '  The physical study object itself — a solid, film, device, liquid, or structure.\n'
    '  Ex: CdTe absorber layer, perovskite thin film, silicon wafer, completed solar cell,\n'
    '      TEM specimen, module, Czochralski crystal, a-Si:H layer.\n\n'

    'tool\n'
    '  An instrument, piece of equipment, or software platform used to make measurements.\n'
    '  Ex: TEM, XRD, SEM, AFM, SIMS, EDS, photoluminescence spectrometer, IV tester,\n'
    '      solar simulator, Raman spectrometer, ellipsometer, EBSD, HRTEM.\n\n'

    'recipe\n'
    '  The settings, parameters, or metadata that define HOW a measurement or process is performed.\n'
    '  Ex: substrate temperature, scan rate, X-ray wavelength, deposition pressure,\n'
    '      bias voltage, measurement conditions, gas flow rate, exposure time.\n\n'

    'data\n'
    '  Raw, unprocessed output generated directly by an instrument.\n'
    '  Ex: raw XRD pattern, as-acquired TEM image, raw IV curve, raw EDS spectrum,\n'
    '      raw PL emission spectrum, raw time-resolved data.\n\n'

    'data processing\n'
    '  Any computational or manual manipulation applied to raw data to clean or transform it.\n'
    '  Ex: background subtraction, noise filtering, normalisation, dead-pixel correction,\n'
    '      peak fitting, deconvolution, image drift correction, flat-field correction.\n\n'

    'result\n'
    '  Processed, polished data ready for interpretation — the output of data processing.\n'
    '  Ex: corrected XRD pattern, calibrated efficiency map, extracted Voc/Jsc/FF values,\n'
    '      fitted carrier lifetime, corrected EQE spectrum, doping profile.\n\n'

    'analysis\n'
    '  Scripts, methods, statistical reasoning, or comparisons applied to Results to draw conclusions.\n'
    '  Ex: voltage-loss analysis, Shockley-Queisser comparison, failure mode attribution,\n'
    '      ANOVA, recombination pathway identification, correlation analysis, band-gap extraction.\n\n'

    'modeling\n'
    '  Computational simulation, theoretical calculation, or physics-based fitting.\n'
    '  Ex: DFT calculation, drift-diffusion simulation, equivalent circuit fitting,\n'
    '      recombination model, TCAD simulation, optical transfer-matrix modeling.\n\n'

    'results and metadata\n'
    '  Final aggregated outputs, summary statistics, publication-ready data, or study metadata.\n'
    '  Ex: champion efficiency table, degradation rate over field lifetime, dataset DOI,\n'
    '      study conditions summary, technology readiness level, module certification result.\n\n'

    '--- DECISION RULES ---\n'
    '- A material compound (CdTe, perovskite, silicon) → sample (it IS the study object)\n'
    '- A device parameter or metric (Voc, FF, lifetime, EQE) → result\n'
    '- An instrument name (TEM, XRD, SEM) → tool\n'
    '- A process step that forms new material (deposition, synthesis) → synthesis\n'
    '- A process step that transforms existing material (annealing, etching) → materials processing\n'
    '- A measurement setting or condition → recipe\n'
    '- A computational/physics model → modeling\n'
    '- A statistical or interpretive method → analysis\n\n'

    '--- MDS-Onto SUPPLY CHAIN LEVELS ---\n'
    '   materials       — raw element, compound, or precursor\n'
    '   subcomponent    — thin film, deposited layer, or processed structure\n'
    '   component       — complete single device (e.g. one solar cell)\n'
    '   assembly        — small integrated unit (e.g. mini-module, cell string)\n'
    '   subsystem       — module, panel, or interconnected string\n'
    '   system          — full installation, array, or grid-connected system\n\n'

    'Assign the most specific stage possible. If genuinely ambiguous between two stages, '
    'pick the one that describes what the concept PRIMARILY IS, not how it might be used.'
)

# ---------------------------------------------------------------------------
# CSV LOADING
# ---------------------------------------------------------------------------

def load_concepts(csv_path: str) -> pd.DataFrame:
    """
    Return a DataFrame with at least [concept, doc_frequency].
    Handles rankings_*.csv and concepts_*.csv formats.
    """
    df = pd.read_csv(csv_path)
    cols = {c.lower().strip() for c in df.columns}

    if 'concept' in cols and 'doc_frequency' in cols:
        # rankings (V1–V4): concept, doc_frequency, avg_relevance
        out = df.copy()
        out['concept'] = out['concept'].str.strip()

    elif 'canonical' in cols:
        # V4/V5 concepts: paper, doi, canonical, paper_term, relevance
        df['canonical'] = df['canonical'].str.strip().str.lower()
        out = (
            df.groupby('canonical')
              .agg(doc_frequency=('paper', 'nunique'))
              .reset_index()
              .rename(columns={'canonical': 'concept'})
        )

    elif 'concept' in cols and 'paper' in cols:
        # V3 concepts: paper, concept, relevance
        df['concept'] = df['concept'].str.strip().str.lower()
        out = (
            df.groupby('concept')
              .agg(doc_frequency=('paper', 'nunique'))
              .reset_index()
        )

    else:
        raise ValueError(
            f'Unrecognised CSV format in {csv_path}.\n'
            f'Expected one of:\n'
            f'  rankings : concept, doc_frequency\n'
            f'  V4/V5   : paper, doi, canonical, paper_term, relevance\n'
            f'  V3      : paper, concept, relevance\n'
            f'Found: {list(df.columns)}'
        )

    out = out.dropna(subset=['concept'])
    out = out[out['concept'].str.strip() != '']
    out = out.sort_values(
        ['doc_frequency', 'concept'],
        ascending=[False, True]
    ).reset_index(drop=True)
    return out

# ---------------------------------------------------------------------------
# LLM TAGGING
# ---------------------------------------------------------------------------

def _tag_batch(concepts: list[str]) -> list[dict]:
    """
    Send one batch of concept labels to the LLM.
    Returns a list of {concept, mds_study_stage, mds_supply_chain_level}.
    """
    concept_list = '\n'.join(f'- {c}' for c in concepts)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {'role': 'system', 'content': _TAG_SYSTEM},
            {'role': 'user',   'content': (
                f'Tag each of the following {len(concepts)} concepts with the '
                f'appropriate mds:studyStage and mds:supplyChainLevel values.\n\n'
                f'{concept_list}'
            )},
        ],
        tools=[_TAG_TOOL],
        tool_choice={'type': 'function', 'function': {'name': 'return_tagged_concepts'}},
    )
    msg = response.choices[0].message
    if not msg.tool_calls:
        return []
    try:
        result = json.loads(msg.tool_calls[0].function.arguments)
        return result.get('tagged_concepts', [])
    except (json.JSONDecodeError, IndexError):
        return []


def tag_concepts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add mds:studyStage and mds:supplyChainLevel columns to df.
    Processes concepts in batches.
    """
    concepts = df['concept'].tolist()
    all_tagged: dict[str, dict] = {}

    batches = [concepts[i:i + BATCH_SIZE] for i in range(0, len(concepts), BATCH_SIZE)]
    total = len(batches)

    for b_idx, batch in enumerate(batches, 1):
        print(f'  Tagging batch {b_idx}/{total} ({len(batch)} concepts)…')
        tagged = _tag_batch(batch)
        for item in tagged:
            c = item.get('concept', '').strip().lower()
            if c:
                all_tagged[c] = item
        if b_idx < total:
            time.sleep(RATE_LIMIT_DELAY)

    # Map tags back onto the dataframe
    study_stages = []
    supply_levels = []

    for concept in df['concept']:
        key = concept.strip().lower()
        item = all_tagged.get(key, {})

        stages = item.get('mds_study_stage', [])
        levels = item.get('mds_supply_chain_level', [])

        study_stages.append(', '.join(f'mds:{s}' for s in stages) if stages else '')
        supply_levels.append(', '.join(f'mds:{l}' for l in levels) if levels else '')

    df = df.copy()
    df['mds:studyStage']       = study_stages
    df['mds:supplyChainLevel'] = supply_levels
    return df

# ---------------------------------------------------------------------------
# DRAW.IO XML BUILDER  (concept-map page)
# ---------------------------------------------------------------------------

def _node_value(concept: str, study_stage: str, supply_level: str) -> str:
    """Build HTML label: concept name + mds: tag lines."""
    tags = []
    if study_stage:
        tags.append(study_stage)
    if supply_level:
        tags.append(supply_level)
    tag_html = (
        '<br/><font style="font-size:9px;color:#555555;">'
        + '<br/>'.join(tags)
        + '</font>'
    ) if tags else ''
    return f'<b>{concept}</b>{tag_html}'


def _optimal_group_cols(n: int) -> int:
    if n <= GROUP_COLS_MIN:
        return max(1, n)
    cols = round(math.sqrt(n * 1.5))
    return max(GROUP_COLS_MIN, min(GROUP_COLS_MAX, cols))


def _group_dims(n: int) -> tuple[int, int, int]:
    n_cols = _optimal_group_cols(n)
    cols   = min(n_cols, max(n, 1))
    rows   = math.ceil(n / n_cols) if n > 0 else 1
    w = cols * (NODE_W + GAP_X) - GAP_X + 2 * GROUP_PAD
    h = rows * (NODE_H + GAP_Y) - GAP_Y + 2 * GROUP_PAD + HEADER_H
    return w, h, n_cols


def _add_swimlane(root_el, container_id, label, fill, stroke, gx, gy, gw, gh):
    c = ET.SubElement(root_el, 'mxCell', {
        'id':     container_id,
        'value':  label,
        'style':  (
            f'swimlane;startSize={HEADER_H};'
            f'fillColor={fill};strokeColor={stroke};strokeWidth=2;'
            f'fontFamily=Helvetica;fontSize=13;fontStyle=1;'
            f'rounded=1;arcSize=3;'
        ),
        'vertex': '1',
        'parent': '1',
    })
    ET.SubElement(c, 'mxGeometry', {
        'x': str(int(gx)), 'y': str(int(gy)),
        'width': str(int(gw)), 'height': str(int(gh)),
        'as': 'geometry',
    })
    return c


def _place_nodes(root_el, concept_rows, container_id, n_cols, stroke, cell_id_start):
    cell_id = cell_id_start
    for j, row in enumerate(concept_rows):
        nx = GROUP_PAD + (j % n_cols) * (NODE_W + GAP_X)
        ny = HEADER_H + GROUP_PAD + (j // n_cols) * (NODE_H + GAP_Y)
        supply = row.get('mds:supplyChainLevel', '')
        label  = _node_value(str(row['concept']), '', supply)
        node = ET.SubElement(root_el, 'mxCell', {
            'id': f'concept-{cell_id}', 'value': label,
            'style': (
                'rounded=1;whiteSpace=wrap;html=1;'
                'align=center;verticalAlign=middle;'
                'fontFamily=Helvetica;fontSize=10;'
                'labelBackgroundColor=none;resizable=1;'
                f'fillColor=#ffffff;strokeColor={stroke};strokeWidth=1.5;'
            ),
            'vertex': '1', 'parent': container_id,
        })
        ET.SubElement(node, 'mxGeometry', {
            'x': str(int(nx)), 'y': str(int(ny)),
            'width': str(NODE_W), 'height': str(NODE_H),
            'as': 'geometry',
        })
        cell_id += 1
    return cell_id


def build_drawio_xml(df: pd.DataFrame, page_title: str = 'Concepts') -> ET.Element:
    """
    Build the concept-map diagram page and return the mxfile ET.Element.
    Callers should add extra pages (e.g. library palettes) before serialising.
    """

    # ---- 1. Bucket concepts by primary study stage -------------------------
    buckets: dict[str, list] = {s: [] for s in _ALL_ZONES + ['unclassified']}
    for _, row in df.iterrows():
        raw     = row.get('mds:studyStage', '')
        primary = raw.replace('mds:', '').split(',')[0].strip().lower() if raw else ''
        key     = primary if primary in buckets else 'unclassified'
        buckets[key].append(row)

    def zone_groups(zone):
        out = []
        for s in zone:
            rows = buckets.get(s, [])
            if rows:
                w, h, nc = _group_dims(len(rows))
                out.append((s, rows, w, h, nc))
        return out

    top_gs    = zone_groups(_ZONE_TOP)
    left_gs   = zone_groups(_ZONE_LEFT)
    right_gs  = zone_groups(_ZONE_RIGHT)
    bottom_gs = zone_groups(_ZONE_BOTTOM)

    def zone_row_dims(gs):
        if not gs: return 0, 0
        total_w = sum(w for _, _, w, _, _ in gs) + GRID_GAP * (len(gs) - 1)
        max_h   = max(h for _, _, _, h, _ in gs)
        return total_w, max_h

    def zone_col_dims(gs):
        if not gs: return 0, 0
        max_w   = max(w for _, _, w, _, _ in gs)
        total_h = sum(h for _, _, _, h, _ in gs) + GRID_GAP * (len(gs) - 1)
        return max_w, total_h

    top_w,    top_h    = zone_row_dims(top_gs)
    left_w,   left_h   = zone_col_dims(left_gs)
    right_w,  right_h  = zone_col_dims(right_gs)
    bottom_w, bottom_h = zone_row_dims(bottom_gs)

    # ---- 2. Resolve canvas and centre dimensions ---------------------------
    min_middle_w = left_w + (GRID_GAP if left_w else 0) + CENTER_MIN_W + (GRID_GAP if right_w else 0) + right_w
    inner_w  = max(top_w, bottom_w, min_middle_w)
    canvas_w = inner_w + 2 * MARGIN

    centre_w = max(inner_w - left_w - right_w
                   - (GRID_GAP if left_w  else 0)
                   - (GRID_GAP if right_w else 0),
                   CENTER_MIN_W)
    centre_h = max(left_h, right_h, CENTER_MIN_H)

    canvas_h = (2 * MARGIN
                + (top_h    + GRID_GAP if top_gs    else 0)
                + centre_h
                + (GRID_GAP + bottom_h if bottom_gs else 0))

    cx = MARGIN + left_w + (GRID_GAP if left_w else 0)
    cy = MARGIN + (top_h + GRID_GAP if top_gs else 0)

    # ---- 3. Build XML ------------------------------------------------------
    mxfile  = ET.Element('mxfile', {'host': 'knowledge_workflow_v6', 'version': '1.0'})
    diagram = ET.SubElement(mxfile, 'diagram', {'name': page_title, 'id': 'kw-v6'})
    model   = ET.SubElement(diagram, 'mxGraphModel', {
        'dx': '1422', 'dy': '762',
        'grid': '1', 'gridSize': '10',
        'guides': '1', 'tooltips': '1', 'connect': '1', 'arrows': '1',
        'fold': '1', 'page': '1', 'pageScale': '1',
        'pageWidth':  str(max(int(canvas_w), 1600)),
        'pageHeight': str(max(int(canvas_h), 1200)),
        'background': '#ffffff', 'math': '0', 'shadow': '0',
    })
    root_el = ET.SubElement(model, 'root')
    ET.SubElement(root_el, 'mxCell', {'id': '0'})
    ET.SubElement(root_el, 'mxCell', {'id': '1', 'parent': '0'})
    cell_id = 2

    # ---- 4. Centre blank workspace -----------------------------------------
    blank = ET.SubElement(root_el, 'mxCell', {
        'id':     'centre-blank',
        'value':  (
            '<font style="font-size:16px;color:#bbbbbb;">'
            '&#8592; Drag concepts here &#8594;'
            '</font>'
        ),
        'style':  (
            'rounded=1;whiteSpace=wrap;html=1;'
            'fillColor=#fafafa;strokeColor=#cccccc;strokeWidth=2;'
            'dashed=1;dashPattern=10 6;'
            'verticalAlign=middle;align=center;'
        ),
        'vertex': '1', 'parent': '1',
    })
    ET.SubElement(blank, 'mxGeometry', {
        'x': str(int(cx)), 'y': str(int(cy)),
        'width': str(int(centre_w)), 'height': str(int(centre_h)),
        'as': 'geometry',
    })

    # ---- 5. Helper: write a swimlane + its nodes ---------------------------
    def write_group(stage, rows, gx, gy, gw, gh, n_cols):
        nonlocal cell_id
        fill, stroke = _STAGE_COLORS.get(stage, _STAGE_COLORS['unknown'])
        cid = f'grp-{stage.replace(" ", "_").replace("-", "_")}'
        _add_swimlane(root_el, cid, f'mds:{stage}', fill, stroke, gx, gy, gw, gh)
        cell_id = _place_nodes(root_el, rows, cid, n_cols, stroke, cell_id)

    # ---- 6. TOP zone -------------------------------------------------------
    if top_gs:
        x_start = MARGIN + max(0, (inner_w - top_w) // 2)
        x = x_start
        for stage, rows, w, h, nc in top_gs:
            write_group(stage, rows, x, MARGIN, w, h, nc)
            x += w + GRID_GAP

    # ---- 7. LEFT zone ------------------------------------------------------
    if left_gs:
        y = cy
        for stage, rows, w, h, nc in left_gs:
            write_group(stage, rows, MARGIN, y, w, h, nc)
            y += h + GRID_GAP

    # ---- 8. RIGHT zone -----------------------------------------------------
    if right_gs:
        rx = cx + centre_w + GRID_GAP
        y  = cy
        for stage, rows, w, h, nc in right_gs:
            write_group(stage, rows, rx, y, w, h, nc)
            y += h + GRID_GAP

    # ---- 9. BOTTOM zone ----------------------------------------------------
    if bottom_gs:
        by      = cy + centre_h + GRID_GAP
        x_start = MARGIN + max(0, (inner_w - bottom_w) // 2)
        x = x_start
        for stage, rows, w, h, nc in bottom_gs:
            write_group(stage, rows, x, by, w, h, nc)
            x += w + GRID_GAP

    # ---- 10. Unclassified --------------------------------------------------
    leftover = buckets.get('unclassified', [])
    if leftover:
        w, h, nc = _group_dims(len(leftover))
        gy = canvas_h - MARGIN + GRID_GAP
        fill, stroke = _STAGE_COLORS['unclassified']
        cid = 'grp-unclassified'
        _add_swimlane(root_el, cid, 'mds:unclassified', fill, stroke, MARGIN, gy, w, h)
        cell_id = _place_nodes(root_el, leftover, cid, nc, stroke, cell_id)

    return mxfile


def _serialize_drawio(mxfile_el: ET.Element) -> str:
    """Convert an mxfile ET.Element to pretty-printed draw.io XML string."""
    raw    = ET.tostring(mxfile_el, encoding='unicode')
    pretty = minidom.parseString(raw).toprettyxml(indent='  ')
    lines  = pretty.splitlines()
    if lines and lines[0].startswith('<?xml'):
        lines = lines[1:]
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# LIBRARY PAGE EMBEDDING
# ---------------------------------------------------------------------------

def _load_mxlibrary(path: str) -> list[dict]:
    """
    Parse an mxlibrary file (either .xml or .json extension) and return
    the list of item dicts: [{xml, w, h, title}, ...].
    """
    with open(path, encoding='utf-8') as f:
        raw = f.read().strip()
    inner = raw.removeprefix('<mxlibrary>').removesuffix('</mxlibrary>')
    return json.loads(inner)


def _embed_library_page(
    mxfile_el: ET.Element,
    page_name: str,
    page_id:   str,
    items:     list[dict],
    cols:      int = 6,
    gap_x:     int = 20,
    gap_y:     int = 20,
    pad:       int = 30,
) -> None:
    """
    Append a diagram page to mxfile_el with all mxlibrary items tiled in a grid.

    Each item's mxGraphModel XML is decoded and its cells placed at the correct
    grid position. Handles both plain mxCell vertices and UserObject-wrapped
    edge cells (the format draw.io uses for labeled connectors with hyperlinks).
    """
    # --- calculate grid layout ---
    rows_list = [items[i:i + cols] for i in range(0, len(items), cols)]

    col_widths = []
    for c in range(cols):
        w = max((it['w'] for i, it in enumerate(items) if i % cols == c), default=120)
        col_widths.append(w)

    row_heights = [max(it['h'] for it in row) for row in rows_list]

    pw = sum(col_widths) + gap_x * max(cols - 1, 0) + 2 * pad
    ph = sum(row_heights) + gap_y * max(len(rows_list) - 1, 0) + 2 * pad

    diagram = ET.SubElement(mxfile_el, 'diagram', {'name': page_name, 'id': page_id})
    model   = ET.SubElement(diagram, 'mxGraphModel', {
        'pageWidth':  str(max(int(pw), 800)),
        'pageHeight': str(max(int(ph), 600)),
        'background': '#ffffff',
        'grid': '0',
    })
    root_el = ET.SubElement(model, 'root')
    ET.SubElement(root_el, 'mxCell', {'id': '0'})
    ET.SubElement(root_el, 'mxCell', {'id': '1', 'parent': '0'})

    uid = 2  # unique cell-id counter for this page

    for ri, row_items in enumerate(rows_list):
        oy = pad + sum(row_heights[:ri]) + gap_y * ri
        for ci, item in enumerate(row_items):
            ox = pad + sum(col_widths[:ci]) + gap_x * ci

            try:
                item_tree = ET.fromstring(_html.unescape(item['xml']))
            except ET.ParseError:
                uid += 10
                continue

            item_root = item_tree.find('root')
            if item_root is None:
                uid += 10
                continue

            # Collect all non-root-marker children
            children = [c for c in item_root if c.get('id') not in ('0', '1')]

            # Build a stable ID remap for this item
            id_map: dict[str, str] = {}
            for child in children:
                old = child.get('id', '')
                id_map[old] = f'{page_id}-{uid}'
                uid += 1

            # Emit each cell with remapped IDs and offset geometry
            for child in children:
                new_id = id_map.get(child.get('id', ''), f'{page_id}-{uid}')

                if child.tag == 'UserObject':
                    # UserObject wraps an mxCell — common for labeled edges with links
                    attrs = {k: v for k, v in child.attrib.items()}
                    attrs['id'] = new_id
                    user_el = ET.SubElement(root_el, 'UserObject', attrs)

                    inner = child.find('mxCell')
                    if inner is not None:
                        cell_attrs = {k: v for k, v in inner.attrib.items()}
                        cell_attrs.pop('id', None)
                        cell_attrs['parent'] = '1'
                        for a in ('source', 'target'):
                            if a in cell_attrs:
                                cell_attrs[a] = id_map.get(cell_attrs[a], cell_attrs[a])
                        ic_el = ET.SubElement(user_el, 'mxCell', cell_attrs)
                        _copy_geom_offset(inner, ic_el, ox, oy)

                else:
                    # Plain mxCell (vertex or edge)
                    cell_attrs = {k: v for k, v in child.attrib.items()}
                    cell_attrs['id'] = new_id
                    cell_attrs['parent'] = '1'
                    for a in ('source', 'target'):
                        if a in cell_attrs:
                            cell_attrs[a] = id_map.get(cell_attrs[a], cell_attrs[a])
                    cell_el = ET.SubElement(root_el, 'mxCell', cell_attrs)
                    _copy_geom_offset(child, cell_el, ox, oy)


def _copy_geom_offset(src_cell: ET.Element, dst_cell: ET.Element, ox: float, oy: float) -> None:
    """
    Copy the mxGeometry from src_cell into dst_cell, shifting all coordinate
    values (x/y on the geometry element and on any mxPoint children) by (ox, oy).
    """
    geom = src_cell.find('mxGeometry')
    if geom is None:
        return

    g_attrs = dict(geom.attrib)
    if 'x' in g_attrs:
        g_attrs['x'] = str(float(g_attrs['x']) + ox)
    if 'y' in g_attrs:
        g_attrs['y'] = str(float(g_attrs['y']) + oy)
    geom_el = ET.SubElement(dst_cell, 'mxGeometry', g_attrs)

    for pt in geom.findall('mxPoint'):
        pt_attrs = dict(pt.attrib)
        if 'x' in pt_attrs:
            pt_attrs['x'] = str(float(pt_attrs['x']) + ox)
        if 'y' in pt_attrs:
            pt_attrs['y'] = str(float(pt_attrs['y']) + oy)
        ET.SubElement(geom_el, 'mxPoint', pt_attrs)

    for arr in geom.findall('Array'):
        arr_el = ET.SubElement(geom_el, 'Array', dict(arr.attrib))
        for pt in arr.findall('mxPoint'):
            pt_attrs = dict(pt.attrib)
            if 'x' in pt_attrs:
                pt_attrs['x'] = str(float(pt_attrs['x']) + ox)
            if 'y' in pt_attrs:
                pt_attrs['y'] = str(float(pt_attrs['y']) + oy)
            ET.SubElement(arr_el, 'mxPoint', pt_attrs)


def _add_template_pages(mxfile_el: ET.Element) -> None:
    """
    Embed the MDS-Onto library and Cemento templates as extra pages in the
    diagram.  Falls back gracefully if a library file is not found.
    """
    specs = [
        (MDS_ONTO_LIBRARY,          'MDS-Onto Library',  'lib-mds-onto', 6),
        (CEMENTO_TEMPLATES_LIBRARY, 'Cemento Templates', 'lib-cemento',  2),
    ]
    for path, page_name, page_id, cols in specs:
        if not os.path.isfile(path):
            print(f'  [skip] library file not found: {path}')
            continue
        try:
            items = _load_mxlibrary(path)
            _embed_library_page(mxfile_el, page_name, page_id, items, cols=cols)
            print(f'  library  : "{page_name}" — {len(items)} items embedded')
        except Exception as exc:
            print(f'  [warn] could not embed {path}: {exc}')

# ---------------------------------------------------------------------------
# PROCESS ONE FILE
# ---------------------------------------------------------------------------

def _process_one(csv_path: str, date_stamp: str) -> tuple[str, str]:
    """
    Load, tag, and save outputs for a single concepts CSV.
    Returns (csv_out_path, drawio_out_path).
    """
    stem = os.path.splitext(os.path.basename(csv_path))[0]

    # Derive the collection slug from the containing directory name.
    # V5 writes to outputs/<slug>/concepts_*.csv, so the parent dir IS the slug.
    slug = os.path.basename(os.path.dirname(os.path.abspath(csv_path)))
    out_dir = os.path.join(OUTPUTS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    # Load
    df = load_concepts(csv_path)
    print(f'  Concepts : {len(df)}')

    # Tag
    print(f'  Tagging  : mds:studyStage + mds:supplyChainLevel …')
    df = tag_concepts(df)

    # Save enriched CSV
    csv_out = os.path.join(out_dir, f'enriched_{stem}-v6-{date_stamp}.csv')
    df.to_csv(csv_out, index=False)
    print(f'  CSV      : {csv_out}')

    # Build concept-map page, embed library pages, then serialise
    page_title = slug.replace('_', ' ').replace('-', ' ').title()
    mxfile_el  = build_drawio_xml(df, page_title=page_title)
    _add_template_pages(mxfile_el)
    xml = _serialize_drawio(mxfile_el)

    drawio_out = os.path.join(out_dir, f'diagram_{stem}-v6-{date_stamp}.drawio')
    with open(drawio_out, 'w', encoding='utf-8') as fh:
        fh.write(xml)
    print(f'  draw.io  : {drawio_out}')

    return csv_out, drawio_out

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    print(f'Provider : {LLM_BASE_URL}')
    print(f'Model    : {MODEL}\n')

    date_stamp = datetime.now().strftime('%Y%m%d')

    # ---- locate input file(s) ----------------------------------------------
    if INPUT_CSV:
        csv_files = [INPUT_CSV]
    else:
        pattern   = os.path.join(OUTPUTS_DIR, '**', 'concepts_*.csv')
        csv_files = sorted(glob.glob(pattern, recursive=True))
        if not csv_files:
            raise FileNotFoundError(
                f'No concepts_*.csv files found under "{OUTPUTS_DIR}".\n'
                f'Run the V5 workflow first to generate concepts files, '
                f'or set INPUT_CSV to a specific path.'
            )

    print(f'Found {len(csv_files)} concepts file(s) to process:\n')
    for p in csv_files:
        print(f'  {p}')
    print()

    # ---- process each file -------------------------------------------------
    all_outputs: list[tuple[str, str]] = []

    for idx, csv_path in enumerate(csv_files, 1):
        print(f'[{idx}/{len(csv_files)}] {os.path.basename(csv_path)}')
        try:
            csv_out, drawio_out = _process_one(csv_path, date_stamp)
            all_outputs.append((csv_out, drawio_out))
        except Exception as exc:
            print(f'  ERROR: {exc}')
        print()

    # ---- summary -----------------------------------------------------------
    print('=' * 60)
    print(f'Done — {len(all_outputs)}/{len(csv_files)} files processed\n')
    print('Outputs:')
    for csv_out, drawio_out in all_outputs:
        print(f'  {drawio_out}')
        print(f'  {csv_out}')
    print('\nOpen .drawio files in draw.io → File → Open from → This Device')
    print('Library pages (MDS-Onto Library, Cemento Templates) are included as tabs.')
