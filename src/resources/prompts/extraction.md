You extract a faithful, detailed concept graph from ONE SECTION of a {{domain}} research paper. Be thorough: capture every domain concept, relation, cause-and-effect claim and reported value this section states. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS - extract ALL of these that the section mentions:
- materials and material forms ({{ex:materials}});
- devices, device parts and structures ({{ex:devices}});
- equipment and instruments ({{ex:equipment}});
- process steps ({{ex:process_steps}});
- process parameters ({{ex:parameters}});
- measured properties and quantities ({{ex:properties}});
- phenomena, mechanisms, defects and failure modes ({{ex:phenomena}});
- characterization and analysis methods ({{ex:methods}});
- conditions and stressors ({{ex:stressors}});
- information artifacts (standards, datasets, models, metrics).
Skip only generic words (study, result, approach, figure), people, institutions and citations.
- label: a singular noun phrase as written in the paper. Lowercase, except acronyms, chemical formulas and proper names. Keep specific qualifiers ({{ex:label_example}}).
- If CONCEPTS ALREADY FOUND is given, reuse those exact labels for the same things.
- type: from the enum. process step -> process; process parameter -> parameter; measured quantity -> property or quantity.
- synonyms: acronyms and alternate names used in the text.
- definition: one sentence only if the text defines or clearly characterizes it; otherwise "".
- figures: ids (F<n>) of the listed figures that show this concept.
- ids: c1, c2, ... unique within your answer.

RELATIONS (non-causal) - every stated or directly implied link, with p from this list (OBO Relations Ontology and BFO/CCO meanings):
- is_a: s is a kind of o. Look for "X is a Y", "X, a type of Y", "Y such as X", "Y including X", "X and other Y". s is the more specific term.
- part_of / has_part: physical or process parthood {{ex:parthood}}.
- composed_primarily_of: what something is mostly made of ("Ag paste composed of silver"); derived_from: made from a material; transformation_of: one material turned into another.
- has_quality: a thing and its measurable property {{ex:quality}}; has_function / has_role: designed purpose or contextual role; capable_of: a thing that can carry out a process.
- has_input / has_output / input_of / output_of: what goes into or comes out of a process; participates_in / has_participant: a thing involved in a process.
- located_in, occurs_in (a process happens in a place or thing), adjacent_to, connected_to: spatial links.
- precedes: process order. measured_by: a property measured by a method or instrument; measures: a method or instrument measuring a property; is_about: information (data, model, standard) about something.
- regulates: a process or parameter controls a property (use the causal pass for direction of change); realizes: a process realizes a function or disposition; correlated_with: a stated correlation without a causal claim.
- related_to: only when none of the above fits.
- s and o MUST be concept ids (c1, c2, ...) from CONCEPTS, never phrases; p from the enum; evidence = verbatim quote of at most 20 words.

CAUSAL - the most important part. Extract EVERY cause -> effect claim, including:
- process parameter -> property {{ex:causal_param}};
- stressor -> degradation {{ex:causal_stressor}};
- mechanism chains: split "A leads to B, which reduces C" into A -> B and B -> C;
- experimental findings and trends {{ex:causal_finding}}.
- polarity from the enum; condition = the stated context (temperature, time, climate, bias), else "".
- evidence = verbatim quote of at most 20 words. Direction matters: cause is what changes first.
- cause and effect MUST be concept ids (c1, c2, ...) from your CONCEPTS list, never phrases. If a cause or effect is not in CONCEPTS yet, add it there first (e.g. "performance loss", "lifetime").

MEASUREMENTS - every reported value: property = id of the property, parameter or quantity the value is a value of (for "a conductivity of 12 mS cm-1 for Li7P3S11" the property is conductivity, never the material); entity = id of the device, material, technology or system the value is for: give it whenever the sentence, table or caption names one; value exactly as written (e.g. "22.5", "850-900", "<1"); unit as written; condition = the stated context; basis = measured (obtained in this work), simulated (calculated or modelled in this work), cited (reported from another source, e.g. with a reference) or target (a goal, projection or assumed input); and a verbatim quote of at most 20 words.
- TABLE blocks give a table as "| cell | cell |" rows under its caption: every cell holding a value is a measurement. The column header names the property (and often the unit), the row label usually the entity or condition; the quote is the row as written.
- If the property is not in CONCEPTS yet, add it to CONCEPTS as type property, quantity or parameter.

FIGURES - for each F<n> listed: the concept ids it depicts and what it shows in at most 12 words.

SCHEMA
