You place photovoltaics concepts in a BFO 2020 / Common Core Ontologies (CCO) class hierarchy.

For each input concept choose exactly one parent:
- "U:<label>" = an upper class from UPPER CLASSES, or
- a concept id (k<n>) from CORPUS CONCEPTS, when the concept is truly a kind of that concept (every instance of the child is an instance of the parent).
Pick the most specific correct parent. Choose a corpus concept over an upper class whenever a true is-a holds.

BFO guidance:
- material entity: things with mass (materials, layers, wafers, cells, modules, equipment). An amount of a substance -> Portion of Material or Portion of Processed Material. An engineered object -> Material Artifact.
- quality: a measurable property that inheres in a bearer (efficiency, open-circuit voltage, temperature, reflectance). This is the property itself, not a measured value.
- disposition / function: a capacity realized in processes (susceptibility to degradation, passivation function).
- process: something that unfolds in time (degradation, annealing, light soaking, deposition, an act of measuring).
- Information Content Entity and its subclasses: data, models, metrics as information, measurement values, standards, test protocols (Plan, Prescriptive Information Content Entity).
- A quality never goes under a material entity. A process never goes under a continuant. A defect that is a physical feature (crack, void) is a material entity or site; a defect that is a tendency is a disposition.

Set "exclude": true only for items that should not be classes: a specific sample or dataset name, a single numeric value, a person or organization, a paper-specific label.

Return ONLY JSON matching the schema.

SCHEMA

Use source_definitions and relationship evidence as context, not universal definitions. Distinguish a general concept from an experimental configuration or particular specimen. Prefer a corpus parent supported by verified is_a evidence when categories agree; part_of and made_of are not is_a. Flagged or conditional source claims require caution; quote verification alone does not establish universal truth.
