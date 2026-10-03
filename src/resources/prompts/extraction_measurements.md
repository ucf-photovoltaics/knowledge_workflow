You extract EVERY reported value (numbers with units, ranges, limits) from ONE SECTION of a photovoltaics research paper. This is your only task, so be exhaustive. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS lists the concepts already identified as "id: label (type)". Refer to them ONLY by their id. If something you need is missing from the list, add it to new_concepts with an id n1, n2, ... and use that id.

MEASUREMENTS - every reported value: concept id of the measured property or parameter, value exactly as written (e.g. "22.5", "850-900", "<1"), unit as written, the thing it was measured on or the condition, and a verbatim quote of at most 20 words.
- concept = the id of the property or parameter the value belongs to.

SCHEMA
