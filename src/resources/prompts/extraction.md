You extract a faithful, detailed concept graph from ONE SECTION of a photovoltaics research paper. Be thorough: capture every domain concept, relation, cause-and-effect claim and reported value this section states. Be faithful: use only what this text says, in the paper's own words; never add background knowledge. Return ONLY one JSON object that matches the schema at the end. No prose.

CONCEPTS - extract ALL of these that the section mentions:
- materials and material forms (wafer, layer, film, paste, encapsulant, dopant, gas, chemical);
- devices, device parts and structures (cell, module, contact, junction, interface, stack);
- equipment and instruments (furnace, PECVD tool, solar simulator, SEM);
- process steps (texturing, diffusion, deposition, firing, annealing, lamination, cleaning, testing);
- process parameters (temperature, time, pressure, gas flow, thickness, doping level, dose, ramp rate);
- measured properties and quantities (efficiency, Voc, Jsc, FF, lifetime, sheet resistance, series resistance, recombination current, reflectance, cost, degradation rate);
- phenomena, mechanisms, defects and failure modes (recombination, LeTID, corrosion, delamination, cracks, PID);
- characterization and analysis methods (EL, PL, IV, SIMS, modelling, simulation);
- conditions and stressors (damp heat, UV exposure, illumination, bias, climate);
- information artifacts (standards, datasets, models, metrics).
Skip only generic words (study, result, approach, figure), people, institutions and citations.
- label: a singular noun phrase as written in the paper. Lowercase, except acronyms, chemical formulas and proper names. Keep specific qualifiers ("rear AlOx passivation layer", not just "layer").
- If CONCEPTS ALREADY FOUND is given, reuse those exact labels for the same things.
- type: from the enum. process step -> process; process parameter -> parameter; measured quantity -> property or quantity.
- synonyms: acronyms and alternate names used in the text.
- definition: one sentence only if the text defines or clearly characterizes it; otherwise "".
- figures: ids (F<n>) of the listed figures that show this concept.
- ids: c1, c2, ... unique within your answer.

RELATIONS (non-causal) - every stated or directly implied link: composition (made_of, has_part, part_of), is_a, has_property, measured_by, process order (precedes), inputs/outputs (input_of, output_of), used_for, located_in, participates_in.
- s and o MUST be concept ids (c1, c2, ...) from CONCEPTS, never phrases; p from the enum; evidence = verbatim quote of at most 20 words.

CAUSAL - the most important part. Extract EVERY cause -> effect claim, including:
- process parameter -> property ("higher firing temperature increases contact resistance");
- stressor -> degradation ("damp heat causes corrosion of the Ag fingers");
- mechanism chains: split "A leads to B, which reduces C" into A -> B and B -> C;
- experimental findings and trends ("thinner oxide improved Voc"), and prevention or mitigation ("hydrogenation prevents LeTID").
- polarity from the enum; condition = the stated context (temperature, time, climate, bias), else "".
- evidence = verbatim quote of at most 20 words. Direction matters: cause is what changes first.
- cause and effect MUST be concept ids (c1, c2, ...) from your CONCEPTS list, never phrases. If a cause or effect is not in CONCEPTS yet, add it there first (e.g. "performance loss", "lifetime").

MEASUREMENTS - every reported value: concept id of the measured property or parameter, value exactly as written (e.g. "22.5", "850-900", "<1"), unit as written, the thing it was measured on or the condition, and a verbatim quote of at most 20 words.

FIGURES - for each F<n> listed: the concept ids it depicts and what it shows in at most 12 words.

SCHEMA
