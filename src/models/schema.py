# -*- coding: utf-8 -*-
"""
Pydantic models for Phase 2 schema population.
"""

from pydantic import BaseModel


class SchemaValue(BaseModel):
    """The paper-specific value and source quote for one concept."""
    canonical: str
    value:     str = ''
    quote:     str = ''

    def formatted(self) -> str:
        """Return 'value | quote', 'value', 'quote', or '' as appropriate."""
        if self.value and self.quote:
            return f'{self.value} | {self.quote}'
        return self.value or self.quote


class SchemaRow(BaseModel):
    """One paper's row in the wide-format schema table."""
    domain: str
    doi:    str = ''
    # concept label -> formatted cell string ("value | quote")
    cells:  dict[str, str] = {}


# ---------------------------------------------------------------------------
# PydanticAI result-type wrapper
# ---------------------------------------------------------------------------

class SchemaValueList(BaseModel):
    """result_type for the schema_builder agent."""
    values: list[SchemaValue] = Field(
        description='Paper-specific value and source quote for each canonical concept.'
    )
