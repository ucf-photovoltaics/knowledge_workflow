"""Corpus source adapters. Each yields the uniform contract that every
downstream stage consumes:

    {title_lower: {key, title, doi, abstract, date, authors, full_text}}

`kw.zotero` is the reference source; `kw.sources.patents` adds patents.
"""
