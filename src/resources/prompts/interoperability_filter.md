You screen candidate terms from external ontologies for photovoltaics ontology classes. Each class has numbered candidates as [n, label, ontology, definition, match] (match is "=" for a name match, else meaning similarity 0-1).
For each class return the numbers of the candidates that are about the SAME thing or a broader kind of it. Reject candidates that only share a word ("carrier-induced degradation" is not "Armored Personnel Carrier") or name a different thing. Return an empty list when none fits.

Return ONLY JSON matching the schema.

SCHEMA
