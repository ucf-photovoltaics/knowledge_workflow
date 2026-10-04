You write existential axioms for classes of a BFO/CCO-aligned photovoltaics ontology: "every <class> <property> some <target>".
Use ONLY the class's relations. Each relation gives the target class id ("o"), what the papers said ("paper": the extracted predicate and how many papers support it) and "properties": candidate object properties retrieved for that relation from the ontology store, as "P:<ONTOLOGY>:<label> (domain; range) - definition". Choose the candidate whose meaning, domain and range fit the relation best and answer p = "P:<ONTOLOGY>:<label>" exactly as listed; never name a property that is not listed. target o = the relation's class id.
Include an axiom only if it holds for EVERY instance of the class; leave out anything that holds only sometimes, and leave out a relation when no candidate fits. Return an empty list when none qualifies.

Return ONLY JSON matching the schema.

SCHEMA
