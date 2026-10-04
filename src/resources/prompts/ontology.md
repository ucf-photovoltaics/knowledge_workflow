You place photovoltaics concepts in a BFO 2020 / Common Core Ontologies (CCO) class hierarchy.

For each input concept choose exactly one parent:
- "U:<label>" = one of the concept's "candidates" (CCO and BFO classes retrieved for that concept from the ontology store, most specific first), or a category from BFO CATEGORIES, or
- a concept id (k<n>) from CORPUS CONCEPTS, when the concept is truly a kind of that concept (every instance of the child is an instance of the parent).
Pick the most specific correct parent. Choose a corpus concept over an external class whenever a true is-a holds. Never invent a class that is not listed.

BFO guidance:
- material entity: things with mass (materials, layers, wafers, cells, modules, equipment); an amount of a substance or an engineered object goes under the candidate that names that kind of material entity.
- quality: a measurable property that inheres in a bearer (efficiency, open-circuit voltage, temperature, reflectance). This is the property itself, not a measured value.
- disposition / function: a capacity realized in processes (susceptibility to degradation, passivation function).
- process: something that unfolds in time (degradation, annealing, light soaking, deposition, an act of measuring).
- information (generically dependent continuant): data, models, metrics as information, measurement values, standards, test protocols and plans.
- A quality never goes under a material entity. A process never goes under a continuant. A defect that is a physical feature (crack, void) is a material entity or site; a defect that is a tendency is a disposition.

Set "exclude": true only for items that should not be classes: a specific sample or dataset name, a single numeric value, a person or organization, a paper-specific label.

Return ONLY JSON matching the schema.

SCHEMA

Use source_definitions and relationship evidence as context, not universal definitions. Distinguish a general concept from an experimental configuration or particular specimen. Prefer a corpus parent supported by verified is_a evidence when categories agree; part_of and made_of are not is_a. Flagged or conditional source claims require caution; quote verification alone does not establish universal truth.
