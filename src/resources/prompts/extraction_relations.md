You extract EVERY non-causal relation between concepts in ONE SECTION of a photovoltaics research paper. This is your only task, so be exhaustive. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS lists the concepts already identified as "id: label (type)". Refer to them ONLY by their id. If something you need is missing from the list, add it to new_concepts with an id n1, n2, ... and use that id.

RELATIONS (non-causal) - every stated or directly implied link: composition (made_of, has_part, part_of), is_a, has_property, measured_by, process order (precedes), inputs/outputs (input_of, output_of), used_for, located_in, participates_in.
- s and o MUST be ids from CONCEPTS or new_concepts, never phrases; p from the enum; evidence = verbatim quote of at most 20 words.

SCHEMA
