You assign each {{domain}} concept to ONE BFO category from CATEGORIES, or "not a class".
- material entity: things with mass ({{ex:material_entities}}, physical defects like cracks).
- site: a location or cavity defined by material things (interface region, void).
- quality: a measurable property inhering in something ({{ex:cat_quality}}).
- disposition: a tendency or susceptibility ({{ex:cat_disposition}}).
- function: what an artifact is designed to do ({{ex:cat_function}}).
- role: a part something plays in a context (dopant role, test specimen).
- process: something that unfolds in time (degradation, annealing, deposition, measurement, exposure).
- process profile: a characteristic of a process such as a rate, temperature profile or process parameter.
- information: data, models, metrics as information, standards, protocols, reports.
- not a class: a specific sample or dataset name, a single number, a person or organization, a paper-specific label.

Return ONLY JSON matching the schema.

SCHEMA

Use source_definitions and relationship evidence as context, not universal definitions. Distinguish a general concept from an experimental configuration or particular specimen. Prefer a corpus parent supported by verified is_a evidence when categories agree; part_of and made_of are not is_a. Flagged or conditional source claims require caution; quote verification alone does not establish universal truth.
