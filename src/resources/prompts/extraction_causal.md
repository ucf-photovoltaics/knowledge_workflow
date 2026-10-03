You extract EVERY cause -> effect claim from ONE SECTION of a photovoltaics research paper. This is your only task, so be exhaustive. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS lists the concepts already identified as "id: label (type)". Refer to them ONLY by their id. If something you need is missing from the list, add it to new_concepts with an id n1, n2, ... and use that id.

CAUSAL - the most important part. Extract EVERY cause -> effect claim, including:
- process parameter -> property ("higher firing temperature increases contact resistance");
- stressor -> degradation ("damp heat causes corrosion of the Ag fingers");
- mechanism chains: split "A leads to B, which reduces C" into A -> B and B -> C;
- experimental findings and trends ("thinner oxide improved Voc"), and prevention or mitigation ("hydrogenation prevents LeTID").
- polarity from the enum; condition = the stated context (temperature, time, climate, bias), else "".
- evidence = verbatim quote of at most 20 words. Direction matters: cause is what changes first.
- cause and effect MUST be ids from CONCEPTS or new_concepts, never phrases.

SCHEMA
