# -*- coding: utf-8 -*-
"""
Pydantic models for MDS-Onto concept tagging (V6 pipeline).
"""

from pydantic import BaseModel


class TaggedConcept(BaseModel):
    """A concept enriched with MDS-Onto study stage and supply chain level."""
    concept:                str
    doc_frequency:          int = 1
    mds_study_stage:        str = ''   # e.g. "mds:sample"
    mds_supply_chain_level: str = ''   # e.g. "mds:materials, mds:subcomponent"


# ---------------------------------------------------------------------------
# PydanticAI result-type wrapper
# ---------------------------------------------------------------------------

class TaggedConceptBatch(BaseModel):
    """result_type for the tagger agent."""
    tagged_concepts: list['TaggedConceptOutput'] = Field(
        description='Each concept with its MDS-Onto study stage and supply chain level tags.'
    )


class TaggedConceptOutput(BaseModel):
    """Per-concept output from the tagger agent (no doc_frequency — that is added later)."""
    concept:                str   = Field(description='Concept label, exactly as provided.')
    mds_study_stage:        list[str] = Field(description='One or more MDS-Onto study stages.')
    mds_supply_chain_level: list[str] = Field(description='One or more supply chain levels.')
