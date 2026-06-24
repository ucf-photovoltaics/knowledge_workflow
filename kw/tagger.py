# -*- coding: utf-8 -*-
"""
Grounding - MDS-Onto tags (study stage + supply-chain level).

Part of ontology grounding (Step 4), NOT a separate pipeline. Taxonomy comes
from kw/taxonomy.py (single source - fixes P1).
"""
import time
from typing import Literal

import pandas as pd
from pydantic import Field
from pydantic_ai import Agent

from kw import llm
from kw.config import pydantic_model, output_spec, RATE_LIMIT_DELAY, BATCH_SIZE
from kw.models import TaggedConceptBatch, TaggedConceptOutput
from kw.taxonomy import STUDY_STAGES, SUPPLY_CHAIN_LEVELS

StudyStage       = Literal[tuple(STUDY_STAGES)]        # type: ignore[valid-type]
SupplyChainLevel = Literal[tuple(SUPPLY_CHAIN_LEVELS)]  # type: ignore[valid-type]


class _TaggedConceptOut(TaggedConceptOutput):
    mds_study_stage:        list[StudyStage]       = Field(description='One or more MDS-Onto study stages.')
    mds_supply_chain_level: list[SupplyChainLevel] = Field(description='One or more supply chain levels.')


class _TaggedBatch(TaggedConceptBatch):
    tagged_concepts: list[_TaggedConceptOut] = Field(
        description='Each concept with its MDS-Onto study stage and supply chain level tags.'
    )


tagger_agent = Agent(
    pydantic_model, output_type=output_spec(_TaggedBatch), retries=2,
    system_prompt=(
        'You are an ontologist specialising in materials data science (MDS). For each '
        'concept assign the single best mds:studyStage and one or more mds:supplyChainLevel.\n\n'
        'STUDY STAGES: synthesis (new chemical bonds: CVD, ALD, electrodeposition); '
        'formulation (mixing without new bonds: precursor ink); materials processing '
        '(physical/thermal transformation: annealing, etching); sample (the study object: '
        'absorber layer, wafer, cell); tool (instrument/software: TEM, XRD, simulator); '
        'recipe (settings: substrate temperature, scan rate); data (raw instrument output); '
        'data processing (cleaning/transform: peak fitting); result (processed data: extracted '
        'Voc/Jsc/FF); analysis (interpretive methods: voltage-loss analysis); modeling '
        '(simulation/fitting: DFT, drift-diffusion); results and metadata (aggregated outputs).\n\n'
        'RULES: material compound -> sample; device metric (Voc, FF, EQE) -> result; '
        'instrument -> tool; new-material process -> synthesis; transform process -> '
        'materials processing; measurement setting -> recipe; physics model -> modeling; '
        'statistical/interpretive method -> analysis.\n\n'
        'SUPPLY CHAIN LEVELS: materials (element/compound/precursor); subcomponent (thin '
        'film/layer); component (one device); assembly (mini-module/string); subsystem '
        '(module/panel); system (full installation). Pick the most specific that fits.'
    ),
)


def tag_concepts(df: pd.DataFrame) -> pd.DataFrame:
    """Append 'mds:studyStage' and 'mds:supplyChainLevel' columns. df needs a 'concept' column."""
    concepts   = df['concept'].tolist()
    all_tagged: dict[str, _TaggedConceptOut] = {}
    batches    = [concepts[i:i + BATCH_SIZE] for i in range(0, len(concepts), BATCH_SIZE)]
    total      = len(batches)
    for b_idx, batch in enumerate(batches, 1):
        print(f'  Tagging batch {b_idx}/{total} ({len(batch)} concepts)...')
        result = llm.run_sync(
            tagger_agent,
            f'Tag each of these {len(batch)} concepts with mds:studyStage and '
            f'mds:supplyChainLevel.\n\n' + '\n'.join(f'- {c}' for c in batch)
        )
        for item in result.output.tagged_concepts:
            all_tagged[item.concept.strip().lower()] = item
        if b_idx < total:
            time.sleep(RATE_LIMIT_DELAY)

    stages, levels = [], []
    for concept in df['concept']:
        item = all_tagged.get(concept.strip().lower())
        stages.append(', '.join(f'mds:{s}' for s in item.mds_study_stage) if item else '')
        levels.append(', '.join(f'mds:{l}' for l in item.mds_supply_chain_level) if item else '')
    out = df.copy()
    out['mds:studyStage']       = stages
    out['mds:supplyChainLevel'] = levels
    return out
