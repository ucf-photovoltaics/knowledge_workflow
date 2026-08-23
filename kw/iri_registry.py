# -*- coding: utf-8 -*-
"""
Stable class IRIs across runs.

The problem this solves: `_cls_iri` was `domain_ns + to_camel(label)`, computed
fresh every run. Two consequences, both of which corrupt cross-run comparison:

  * A RELABEL MINTS A NEW CLASS. "open circuit voltage" and "open-circuit
    voltage" are the same concept to a reader and two different IRIs to the
    emitter, so re-running a collection after the extractor words something
    slightly differently silently grows the ontology and inflates the class
    count. Every number the paper quotes across runs inherits that drift.
  * CAMEL-IDENTICAL LABELS COLLIDE. "fill factor" and "Fill Factor" and
    "fill-factor" all camel to FillFactor, so whichever is emitted second is
    dropped by the seen-set with no warning.

The registry pins a normalised label to the IRI it first minted, so a later
variant reuses that IRI and contributes a `skos:altLabel` instead of a new class.

It is deliberately a plain JSON file, human-readable and diffable: this is
provenance, and a reviewer should be able to see when an IRI was minted and what
labels have mapped to it. Keys are normalised labels; values carry the IRI and
the observed surface forms.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path


def normalise(label: str) -> str:
    """Fold a surface label to its registry key.

    Case, punctuation, hyphenation, unicode dashes and plural 's' all vary
    between extraction runs without changing what the concept IS. Everything
    that varies gets folded; anything that could change meaning is kept.
    """
    s = unicodedata.normalize('NFKD', str(label or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'[‐-―]', '-', s)          # unicode dashes -> hyphen
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    # Fold a trailing plural on the head word only: "solar cells" == "solar cell",
    # but never touch words where it would change the term (gas, glass, stress).
    words = s.split()
    if words:
        head = words[-1]
        if len(head) > 3 and head.endswith('s') and not head.endswith(('ss', 'us', 'is')):
            words[-1] = head[:-1]
    return ' '.join(words)


class IRIRegistry:
    """Normalised label -> minted IRI, persisted as JSON."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        self._dirty = False
        if self.path.is_file():
            try:
                self._data = json.loads(self.path.read_text(encoding='utf-8'))
            except Exception:
                # A corrupt registry must not take a run down; it rebuilds itself.
                # Losing pinning is a quality problem, losing the run is worse.
                self._data = {}

    # -- lookup ------------------------------------------------------------
    def iri_for(self, label: str, mint) -> str:
        """The IRI for this label, minting and recording one on first sight.

        `mint` is a callable taking the label and returning a fresh IRI. It is
        only consulted when the normalised label has never been seen.
        """
        key = normalise(label)
        if not key:
            return mint(label)
        entry = self._data.get(key)
        if entry and entry.get('iri'):
            if label not in entry.setdefault('labels', []):
                entry['labels'].append(label)
                self._dirty = True
            return entry['iri']
        iri = mint(label)
        self._data[key] = {'iri': iri, 'labels': [label]}
        self._dirty = True
        return iri

    def alt_labels(self, label: str) -> list[str]:
        """Surface forms previously seen for this concept, excluding the current one.

        These become skos:altLabel, which is how a relabel stays visible instead
        of vanishing into a second class.
        """
        entry = self._data.get(normalise(label)) or {}
        return [l for l in entry.get('labels', []) if l != label]

    # -- persistence -------------------------------------------------------
    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self.path) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        self._dirty = False

    def __len__(self) -> int:
        return len(self._data)
