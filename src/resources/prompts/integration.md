You compare classes from two photovoltaics domain ontologies that were built separately from different literature (for example techno-economic analysis and reliability). Each input row is a candidate pair with an id, class A and class B. Each class has a label, its domain, its BFO kind, its parent and a definition (often blank). match is "=" when the two names (or a synonym) are the same after normalization, otherwise the similarity of the names (0-1).

For each pair choose one relation of A to B:
- equivalent: the same concept and the same kind of entity, so every instance of A is a B and every B is an A
- exact: the same concept, but the two domains may model it as a different kind of entity
- close: overlapping meaning, interchangeable in some uses but not all
- broader: A is a more general concept than B (B is a kind of A)
- narrower: A is a more specific concept than B (A is a kind of B)
- none: different concepts, including ones that only share a word ("module cost" is not "module"), a measured quantity versus the thing it is measured on ("efficiency" is not "solar cell"), or an abbreviation that stands for different things in the two domains

Judge from the labels, kinds, parents and definitions together. The same name in two domains usually means the same concept, but not always. Use equivalent or exact only when you are confident; when unsure prefer close or none.

Return ONLY JSON matching the schema, with one entry per input id.

SCHEMA
