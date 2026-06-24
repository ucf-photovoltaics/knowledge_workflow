# -*- coding: utf-8 -*-
"""
MDS-Onto taxonomy — the SINGLE source of truth (fixes P1).

Both the tagger and the optional draw.io output import these lists from here,
so the study-stage / supply-chain vocabularies can never diverge again.
(The old 7-stage set in cemento_connect.py is retired.)
"""

STUDY_STAGES = [
    'synthesis', 'formulation', 'materials processing', 'sample',
    'tool', 'recipe', 'data', 'data processing',
    'result', 'analysis', 'modeling', 'results and metadata',
]

SUPPLY_CHAIN_LEVELS = [
    'materials', 'subcomponent', 'component', 'assembly', 'subsystem', 'system',
]
