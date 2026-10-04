You extract EVERY non-causal relation between concepts in ONE SECTION of a photovoltaics research paper. This is your only task, so be exhaustive. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS lists the concepts already identified as "id: label (type)". Refer to them ONLY by their id. If something you need is missing from the list, add it to new_concepts with an id n1, n2, ... and use that id.

RELATIONS (non-causal) - every stated or directly implied link, with p from this list (OBO Relations Ontology and BFO/CCO meanings):
- is_a: s is a kind of o. Look for "X is a Y", "X, a type of Y", "Y such as X", "Y including X", "X and other Y". s is the more specific term.
- part_of / has_part: physical or process parthood ("the rear contact is part of the cell", "the process has a firing step").
- composed_primarily_of: what something is mostly made of ("Ag paste composed of silver"); derived_from: made from a material; transformation_of: one material turned into another.
- has_quality: a thing and its measurable property ("the module has an efficiency"); has_disposition: a tendency ("modules susceptible to PID"); has_function / has_role: designed purpose or contextual role; capable_of: a thing that can carry out a process.
- has_input / has_output / input_of / output_of: what goes into or comes out of a process; participates_in / has_participant: a thing involved in a process.
- located_in, occurs_in (a process happens in a place or thing), adjacent_to, connected_to: spatial links.
- precedes: process order. measured_by: a property measured by a method or instrument; measures: a method or instrument measuring a property; is_about: information (data, model, standard) about something.
- regulates: a process or parameter controls a property (use the causal pass for direction of change); realizes: a process realizes a function or disposition; correlated_with: a stated correlation without a causal claim.
- related_to: only when none of the above fits.
- s and o MUST be ids from CONCEPTS or new_concepts, never phrases; p from the enum; evidence = verbatim quote of at most 20 words.

SCHEMA
