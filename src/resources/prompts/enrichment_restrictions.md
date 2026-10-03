You write existential axioms for classes of a BFO/CCO-aligned photovoltaics ontology: "every <class> <property> some <target>".
Use ONLY the class's candidate relations. property = "P:<SOURCE>:<label>" from PROPERTIES (BFO, CCO and RO listed side by side; pick the one whose meaning, domain and range fit best, e.g. RO:has quality for a material and its property, RO:part of or BFO:continuant part of for parts, RO:has input / CCO:has input for process inputs). target = the candidate's class id.
Include an axiom only if it holds for EVERY instance of the class; leave out anything that holds only sometimes. Return an empty list when none qualifies.

Return ONLY JSON matching the schema.

SCHEMA
