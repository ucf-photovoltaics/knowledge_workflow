You screen candidate terms from external ontologies for photovoltaics ontology classes. Each class has numbered candidates retrieved from the ontology store as [n, label, ontology, definition, match] (match is "=" for a name match, else the search score 0-1; a sixth entry "via k hop(s)" marks a candidate reached through another candidate's mappings).
For each class return the numbers of the candidates that are about the SAME thing, a broader or narrower kind of it, or a closely related thing. Reject candidates that only share a word ("carrier-induced degradation" is not "Armored Personnel Carrier") or name a different thing. Return an empty list when none fits.

Return ONLY JSON matching the schema.

SCHEMA
