# -*- coding: utf-8 -*-
"""
MDS-Onto taxonomy - the SINGLE source of truth (fixes P1).

Both the tagger and the optional draw.io / explorer outputs import these lists
from here, so the study-stage / supply-chain vocabularies can never diverge.

The study-stage order below mirrors the MDS-Onto "Study Stages" cycle graphic
(the canonical scientific-investigation workflow). The explorer lays nodes out
left-to-right / around the cycle in exactly this order, and draw.io colours match.
"""

# Canonical study stages, in the left-to-right workflow order of the graphic.
# (inputs: synthesis / formulation / materials processing + tool / recipe feed
#  the sample; then the linear chain through to reporting / semantic search.)
STUDY_STAGES = [
    'synthesis',
    'formulation',
    'materials processing',
    'tool',
    'recipe',
    'sample',
    'exposure',
    'characterization tool',
    'data',
    'data processing',
    'results',
    'modeling',
    'analysis',
    'inference',
    'insights',
    'reports',
    'semantic search',
]

# Zero-based position of each stage, used for left-to-right / cycle ordering.
STAGE_ORDER = {stage: i for i, stage in enumerate(STUDY_STAGES)}

# Display colour per stage (single hex), pulled from the Study Stages graphic.
STAGE_COLORS = {
    'synthesis':             '#8e44ad',
    'formulation':           '#2ecc71',
    'materials processing':  '#a64d79',
    'tool':                  '#aed6f1',
    'recipe':                '#d5dbdb',
    'sample':                '#95a5a6',
    'exposure':              '#2e86de',
    'characterization tool': '#e67e22',
    'data':                  '#ff6fb5',
    'data processing':       '#5dade2',
    'results':               '#7d3c98',
    'modeling':              '#3498db',
    'analysis':              '#6c3483',
    'inference':             '#e84393',
    'insights':              '#d4ac0d',
    'reports':               '#c0392b',
    'semantic search':       '#34495e',
    'unclassified':          '#bdc3c7',
}

# Map legacy / messy stage tags onto the canonical vocabulary so older outputs
# (and the "mds:" prefixed CSV tags) still bin correctly.
_STAGE_ALIASES = {
    'result': 'results',
    'results and metadata': 'results',
    'metadata': 'reports',
    'characterization-tool': 'characterization tool',
    'characterization': 'characterization tool',
    'charact tool': 'characterization tool',
    'char tool': 'characterization tool',
    'semanticsearch': 'semantic search',
    'semantic-search': 'semantic search',
}


def normalize_stage(raw: str) -> str:
    """Normalise one stage token to a canonical study stage.

    Strips an optional ``mds:`` prefix, lower-cases, collapses whitespace, and
    applies the alias table. Unknown / empty tokens return ``'unclassified'``.
    """
    if not raw:
        return 'unclassified'
    s = str(raw).strip()
    if s.lower().startswith('mds:'):
        s = s[4:]
    s = ' '.join(s.replace('_', ' ').replace('-', ' ').split()).lower()
    s = _STAGE_ALIASES.get(s, s)
    return s if s in STAGE_ORDER else 'unclassified'


def normalize_stages(raw: str) -> list:
    """Split a comma-separated stage cell into a de-duplicated, ordered list.

    Returns canonical stages sorted by their position in STUDY_STAGES. Empty /
    unparseable input yields an empty list (caller decides the fallback).
    """
    if not raw:
        return []
    seen = {}
    for part in str(raw).split(','):
        st = normalize_stage(part)
        if st != 'unclassified':
            seen[st] = True
    return sorted(seen, key=lambda s: STAGE_ORDER[s])


SUPPLY_CHAIN_LEVELS = [
    'materials', 'subcomponent', 'component', 'assembly', 'subsystem', 'system',
]
