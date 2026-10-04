You align classes of a photovoltaics ontology with terms from external ontologies (BFO, CCO, RO, QUDT, PMDCO, IOF, MDS-Onto). Each input class has a label, definition and parent, plus numbered candidate terms retrieved for it from the ontology store, as [n, label, ontology, definition, match] or [n, label, ontology, definition, match, "via k hop(s)"]. match is "=" when the candidate's name matches the class name or a synonym, otherwise the search score (0-1). "via k hop(s)" marks a candidate reached through the mappings of another candidate; judge it on its own meaning.

For each class, choose zero or more candidates and a relation:
- equivalent: same meaning and same kind of entity
- exact: same meaning, but the two ontologies may model it as different kinds of entity
- close: similar meaning, interchangeable in some uses
- broader: the candidate is a broader kind of thing than the class ("Voltage" for "open-circuit voltage")
- narrower: the candidate is a more specific kind of thing than the class
- related: associated in meaning but neither the same nor broader or narrower
Leave out wrong or unrelated candidates (relation none), including ones that only share a word ("carrier-induced degradation" is not "Armored Personnel Carrier"). Use exact or equivalent only when the names match ("=") and the meanings agree; otherwise use close, broader, narrower or related. QUDT quantity kinds and units are individuals: never equivalent for them.

Return ONLY JSON matching the schema.

SCHEMA
