You extract EVERY reported value (numbers with units, ranges, limits) from ONE SECTION of a {{domain}} research paper. This is your only task, so be exhaustive. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS lists the concepts already identified as "id: label (type)". Refer to them ONLY by their id. If something you need is missing from the list, add it to new_concepts with an id n1, n2, ... and use that id.

MEASUREMENTS - every reported value: property = id of the property, parameter or quantity the value is a value of (for "a conductivity of 12 mS cm-1 for Li7P3S11" the property is conductivity, never the material); entity = id of the device, material, technology or system the value is for: give it whenever the sentence, table or caption names one; value exactly as written (e.g. "22.5", "850-900", "<1"); unit as written; condition = the stated context; basis = measured (obtained in this work), simulated (calculated or modelled in this work), cited (reported from another source, e.g. with a reference) or target (a goal, projection or assumed input); and a verbatim quote of at most 20 words.
- TABLE blocks give a table as "| cell | cell |" rows under its caption: every cell holding a value is a measurement. The column header names the property (and often the unit), the row label usually the entity or condition; the quote is the row as written.
- If the property is not in CONCEPTS yet, add it as a new concept of type property, quantity or parameter.

SCHEMA
