"""
kw — Knowledge Workflow (refactored, single-flow package).

One linear pipeline (see knowledge_base/08_pipeline_spec.md):

    INPUT(mode) -> CONCEPTS -> MINE(LLM + REBEL) -> CONSOLIDATE
                -> ONTOLOGY -> JSON-LD -> LoRA

Invariants: JSON-LD is emitted only after the ontology; LoRA fine-tunes only
after the ontology is finished. REBEL and the LLM run together during mining.
"""
__version__ = "1.0.0"
