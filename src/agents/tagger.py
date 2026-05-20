# -*- coding: utf-8 -*-
"""
Tagger agent.

Enriches a DataFrame of canonical concepts with MDS-Onto study stage
and supply chain level tags.

PydanticAI infers the tool schema from TaggedConceptBatch — no manual
JSON tool dict, enum injection, or parse_tool_call required.
The enum constraints for study stage and supply chain level are encoded
directly in the Pydantic field descriptions and Literal types below.
"""

import time
import pandas as pd
from typing import Literal

from pydantic import Field
from pydantic_ai import Agent

from src.config import pydantic_model, RATE_LIMIT_DELAY, BATCH_SIZE
from src.models.tag import TaggedConceptBatch, TaggedConceptOutput
from src.tools.drawio_builder import STUDY_STAGES, SUPPLY_CHAIN_LEVELS

# ---------------------------------------------------------------------------
# Tighten the result-type: narrow string fields to Literal enums so
# PydanticAI's schema forces the model to pick valid values.
# ---------------------------------------------------------------------------

StudyStage      = Literal[tuple(STUDY_STAGES)]       # type: ignore[valid-type]
SupplyChainLevel = Literal[tuple(SUPPLY_CHAIN_LEVELS)] # type: ignore[valid-type]


class _TaggedConceptOut(TaggedConceptOutput):
    mds_study_stage:        list[StudyStage]       = Field(description='One or more MDS-Onto study stages.')
    mds_supply_chain_level: list[SupplyChainLevel] = Field(description='One or more supply chain levels.')


class _TaggedBatch(TaggedConceptBatch):
    tagged_concepts: list[_TaggedConceptOut] = Field(
        description='Each concept with its MDS-Onto study stage and supply chain level tags.'
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

tagger_agent = Agent(
    pydantic_model,
    result_type=_TaggedBatch,
    system_prompt=(
        'You are an ontologist specialising in materials data science (MDS). '
        'You will receive concept labels from solar cell / semiconductor literature. '
        'For each concept assign EXACTLY one primary mds:studyStage (the stage '
        'where the concept most naturally lives) and one or more mds:supplyChainLevel values.\n\n'

        '--- MDS-Onto STUDY STAGES (pick the single best fit) ---\n\n'

        'synthesis\n'
        '  Creating a new substance by forming new chemical bonds.\n'
        '  Ex: CVD growth, electrodeposition, sol-gel synthesis, ALD.\n\n'

        'formulation\n'
        '  Mixing existing substances WITHOUT new bond formation.\n'
        '  Ex: preparing precursor ink, blending solvents, mixing dopant solutions.\n\n'

        'materials processing\n'
        '  Physical/thermal/mechanical transformation toward final form.\n'
        '  Ex: annealing, etching, CdCl2 heat treatment, laser scribing, lamination.\n\n'

        'sample\n'
        '  The physical study object itself.\n'
        '  Ex: CdTe absorber layer, perovskite thin film, silicon wafer, completed solar cell.\n\n'

        'tool\n'
        '  An instrument or software platform used to make measurements.\n'
        '  Ex: TEM, XRD, SEM, AFM, SIMS, solar simulator, Raman spectrometer.\n\n'

        'recipe\n'
        '  Settings/parameters defining HOW a measurement or process is performed.\n'
        '  Ex: substrate temperature, scan rate, deposition pressure, gas flow rate.\n\n'

        'data\n'
        '  Raw, unprocessed instrument output.\n'
        '  Ex: raw XRD pattern, as-acquired TEM image, raw IV curve.\n\n'

        'data processing\n'
        '  Computation applied to raw data to clean or transform it.\n'
        '  Ex: background subtraction, noise filtering, peak fitting, deconvolution.\n\n'

        'result\n'
        '  Processed data ready for interpretation.\n'
        '  Ex: corrected XRD, extracted Voc/Jsc/FF, fitted carrier lifetime.\n\n'

        'analysis\n'
        '  Methods/reasoning applied to results to draw conclusions.\n'
        '  Ex: voltage-loss analysis, Shockley-Queisser comparison, ANOVA.\n\n'

        'modeling\n'
        '  Computational simulation or physics-based fitting.\n'
        '  Ex: DFT calculation, drift-diffusion simulation, TCAD, optical modeling.\n\n'

        'results and metadata\n'
        '  Final aggregated outputs or study metadata.\n'
        '  Ex: champion efficiency table, degradation rate, dataset DOI.\n\n'

        '--- DECISION RULES ---\n'
        '- Material compound (CdTe, perovskite) → sample\n'
        '- Device metric (Voc, FF, lifetime, EQE) → result\n'
        '- Instrument name (TEM, XRD) → tool\n'
        '- Process forming new material → synthesis\n'
        '- Process transforming existing material → materials processing\n'
        '- Measurement setting or condition → recipe\n'
        '- Computational/physics model → modeling\n'
        '- Statistical or interpretive method → analysis\n\n'

        '--- MDS-Onto SUPPLY CHAIN LEVELS ---\n'
        '   materials       — raw element, compound, or precursor\n'
        '   subcomponent    — thin film, deposited layer, or processed structure\n'
        '   component       — complete single device (one solar cell)\n'
        '   assembly        — small integrated unit (mini-module, cell string)\n'
        '   subsystem       — module, panel, or interconnected string\n'
        '   system          — full installation, array, or grid-connected system\n\n'

        'Pick the most specific stage possible. If genuinely ambiguous, '
        'choose what the concept PRIMARILY IS, not how it might be used.'
    ),
    retries=2,
)

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def tag_concepts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'mds:studyStage' and 'mds:supplyChainLevel' columns to *df*.
    Processes concepts in batches of BATCH_SIZE.

    Input df must have a 'concept' column.
    Returns a new DataFrame with the two tag columns appended.
    """
    concepts   = df['concept'].tolist()
    all_tagged: dict[str, _TaggedConceptOut] = {}
    batches    = [concepts[i:i + BATCH_SIZE] for i in range(0, len(concepts), BATCH_SIZE)]
    total      = len(batches)

    for b_idx, batch in enumerate(batches, 1):
        print(f'  Tagging batch {b_idx}/{total} ({len(batch)} concepts)…')
        concept_list = '\n'.join(f'- {c}' for c in batch)
        result = tagger_agent.run_sync(
            f'Tag each of the following {len(batch)} concepts with the '
            f'appropriate mds:studyStage and mds:supplyChainLevel values.\n\n'
            f'{concept_list}'
        )
        for item in result.data.tagged_concepts:
            all_tagged[item.concept.strip().lower()] = item
        if b_idx < total:
            time.sleep(RATE_LIMIT_DELAY)

    study_stages  = []
    supply_levels = []
    for concept in df['concept']:
        key  = concept.strip().lower()
        item = all_tagged.get(key)
        if item:
            study_stages.append(', '.join(f'mds:{s}' for s in item.mds_study_stage))
            supply_levels.append(', '.join(f'mds:{l}' for l in item.mds_supply_chain_level))
        else:
            study_stages.append('')
            supply_levels.append('')

    out = df.copy()
    out['mds:studyStage']       = study_stages
    out['mds:supplyChainLevel'] = supply_levels
    return out
