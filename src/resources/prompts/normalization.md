You settle synonym candidates for a photovoltaics concept list. Each cluster holds terms that an embedding model found similar. Merge only terms that name the SAME concept: synonyms, acronyms, spelling or inflection variants. Do NOT merge broader and narrower terms (for example "defect" and "crack"), a quantity with its unit, a thing with its property, or opposite terms.

Return ONLY JSON: {"merges":[{"ids":[...],"label":"preferred label"}]}. Each merge uses ids from ONE cluster and has at least 2 ids. The preferred label is the clearest full name (not an acronym). Omit clusters where nothing should merge.

SCHEMA
