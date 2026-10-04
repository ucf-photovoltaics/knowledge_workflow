You choose the parent class for photovoltaics concepts that were already assigned the BFO category shown in CATEGORY.
Choose exactly one parent per concept:
- "U:<label>" = one of the concept's "candidates" (CCO and BFO classes of this category retrieved for that concept from the ontology store), or
- a concept id (k<n>) from CORPUS CONCEPTS when the concept is truly a kind of it (every instance of the child is an instance of the parent).
Pick the most specific correct parent; prefer a corpus concept whenever a true is-a holds. Never invent a class that is not listed.
If the category shown is clearly wrong for a concept, answer "U:<category>" with the correct category from OTHER CATEGORIES instead.

Return ONLY JSON matching the schema.

SCHEMA

Use source_definitions and relationship evidence as context, not universal definitions. Distinguish a general concept from an experimental configuration or particular specimen. Prefer a corpus parent supported by verified is_a evidence when categories agree; part_of and made_of are not is_a. Flagged or conditional source claims require caution; quote verification alone does not establish universal truth.
