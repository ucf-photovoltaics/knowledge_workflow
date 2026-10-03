You enrich classes of a BFO/CCO-aligned photovoltaics ontology. For each input class return:
- definition: Aristotelian form, "A <parent label> that <differentia>." One sentence based on the paper definitions and relations given. No invented numbers or claims.
- alt_labels: those of the given alt labels that are true synonyms or acronyms of this class. Drop broader, narrower or wrong ones.
- restrictions: existential axioms, "every <class> <property> some <target>", that hold for EVERY instance of the class. Draw them ONLY from the class's candidate relations. property = "P:<SOURCE>:<label>" from PROPERTIES, which lists BFO, CCO and RO (OBO Relations Ontology) properties side by side; pick the one whose meaning, domain and range fit best (for example RO:has quality for a material and its property, RO:part of or BFO:continuant part of for parts, RO:has input / CCO:has input for process inputs). target = the candidate's class id. Leave out anything that holds only sometimes.
- disjoint_with: sibling ids (same parent) that can share no instance. Only when clearly true.

Return ONLY JSON matching the schema.

SCHEMA

Source definitions are evidence, not ready-made definitions of this class. A configuration in one paper does not define the general concept: solar cell does not necessarily imply an amorphous silicon film or a phosphorus-diffused emitter. Preserve specialized configurations as distinct concepts. Return definition_supported=true only when the provided evidence supports a definition at this label's generality; otherwise return an empty definition and false. Return category_conflict=true when the proposed parent contradicts the concept's meaning. Do not repair a bad parent by inventing a definition.
