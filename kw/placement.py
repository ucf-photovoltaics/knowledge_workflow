# -*- coding: utf-8 -*-
"""
Concept placement - decide which MDS-Onto branch a concept belongs under.

This replaces the first-substring-match keyword table that used to be the ONLY
classifier. That table did silent modelling: `contact resistance` matched
"resistance" and became a Measurement; `surface passivation layer` matched
"surface" and became a Characterization. Both are wrong, neither was reported,
and 41% of concepts ended up on a catch-all that hid the failure entirely.

The ladder, in order:

  1. PORTAL   - the grounded match's own parent. If MDS-Onto already told us what
                this concept is, that answer beats anything we can infer.
  2. LLM      - a typed assignment constrained to a Literal of the branch set, so
                the model cannot invent a branch. Batched, like kw/tagger.py.
  3. KEYWORD  - the old rules, kept as a last resort.
  4. UNPLACED - no branch claimed it. The concept is parented to its domain root
                (a real MDS domain IRI) and RECORDED. It is not filed under an
                invented catch-all, because "we could not decide" and "this is a
                generic concept" are different facts and only one of them is true.

Every decision is counted. `report()` returns the mix, and a high keyword or
unplaced rate is the signal that grounding is degraded - which is exactly what
the old design could not tell you.
"""
from __future__ import annotations

import os
import time
from collections import Counter

# Off by default: the LLM rung costs a call per batch. Turn it on for a real run;
# leave it off for offline tests and dry runs.
PLACEMENT_LLM = os.getenv('PLACEMENT_LLM', 'true').lower() != 'false'
PLACEMENT_BATCH_SIZE = int(os.getenv('PLACEMENT_BATCH_SIZE', '40'))

# Short glosses so the model knows what each branch is FOR. Keyed by curie; the
# text is sent verbatim in the system prompt.
BRANCH_HINTS: dict[str, str] = {
    'mds:Material':            'a substance: layer, paste, ink, oxide, encapsulant, alloy',
    'mds:Property':            'a measurable quantity of something: efficiency, Voc, fill factor, thickness, degradation rate',
    'mds:Measurement':         'a reported analytical outcome of a study, not the quantity itself',
    'mds:ManufacturingMethod': 'a process that produces or modifies a sample: deposition, annealing, etching, printing',
    'mds:Equipment':           'an instrument that does the measuring: SEM, solar simulator, spectrometer',
    'mds:Part':                'a fabricated artefact or device component: busbar, finger, emitter, module, interconnect',
    'mds:Sample':              'the specimen under study: wafer, substrate, coupon, test structure',
}

_SOURCES = ('portal', 'llm', 'keyword', 'unplaced')


class PlacementStats:
    """Per-run tally of how each concept got its branch."""

    def __init__(self) -> None:
        self.counts: Counter = Counter()
        self.unplaced: list[str] = []
        self.by_branch: Counter = Counter()

    def record(self, source: str, concept: str, branch: str | None) -> None:
        self.counts[source] += 1
        if branch:
            self.by_branch[branch] += 1
        if source == 'unplaced':
            self.unplaced.append(concept)

    @property
    def total(self) -> int:
        return sum(self.counts[s] for s in _SOURCES)

    def report(self) -> dict:
        t = self.total or 1
        return {
            'total': self.total,
            'counts': {s: self.counts[s] for s in _SOURCES},
            'rates': {s: round(self.counts[s] / t, 4) for s in _SOURCES},
            'unplaced_concepts': list(self.unplaced),
            'by_branch': dict(self.by_branch),
        }

    def summary_line(self) -> str:
        t = self.total or 1
        parts = [f'{s} {self.counts[s]} ({self.counts[s] / t:.0%})' for s in _SOURCES]
        return '  [placement] ' + ' | '.join(parts)


# Namespaces whose IRIs are acceptable as a real parent. MDS-Onto is itself
# BFO-grounded through PMDco and PROV-O, so an mds:/mdsdom: parent inherits that
# transitively -- which is the whole reason Kweave needs to emit no BFO of its own.
# bfo.is_compliant_iri deliberately excludes the MDS bases (it answers a stricter
# question: does this satisfy rule 1 *directly*), so placement asks its own.
GROUNDED_BASES = (
    'https://cwrusdle.bitbucket.io/mds/',
    'https://cwrusdle.bitbucket.io/mdsdom/',
    'https://www.commoncoreontologies.org/',
    'http://www.ontologyrepository.com/CommonCoreOntologies/',
    'http://purl.obolibrary.org/obo/',
)


def is_grounded_iri(iri: str) -> bool:
    """True when this IRI is a term we can legitimately hang a concept under."""
    return bool(iri) and str(iri).startswith(GROUNDED_BASES)


def classify_by_keyword(label: str, rules) -> str | None:
    """Keyword rung. None when nothing matches.

    Scored, not first-match. First-substring-match is what produced the original
    misclassifications: `contact resistance` hit "contact" in an early group and
    became a Part before "resistance" was ever considered, and `surface passivation
    layer` hit "passivation" and became a process before "layer" was reached.
    Reproducing that here would have moved the bug rather than fixed it.

    Two signals decide it:
      * HEAD POSITION. English technical compounds put the head noun last -- a
        "passivation layer" is a layer, a "contact resistance" is a resistance.
        A keyword matching at the end of the label outranks one matching earlier.
      * SPECIFICITY. Among matches in the same position, the longest keyword wins,
        because it is the more precise claim.

    Returning None rather than a catch-all is the point: the caller needs to tell
    'matched nothing' apart from 'matched the generic branch'.
    """
    lower = (label or '').strip().lower()
    if not lower:
        return None

    best_cls, best_score = None, 0.0
    for keywords, cls in rules:
        for kw in keywords:
            idx = lower.rfind(kw)
            if idx < 0:
                continue
            # How close to the end does this keyword finish? 1.0 == flush right.
            end = idx + len(kw)
            headedness = end / len(lower)
            score = headedness * 100 + len(kw)
            if score > best_score:
                best_cls, best_score = cls, score
    # Morphological tier, scored on the same scale so it can WIN rather than only
    # fill gaps. English nominalises measurable qualities with a small closed set
    # of suffixes -- crystallinity, resistivity, absorbance, hardness, durability.
    # A literal keyword list will never cover them, and they were the largest gap
    # when this was checked against the 1,192 real concepts in the portal cache.
    #
    # It has to compete, not just backfill: "solar cell durability" matches "cell"
    # mid-string, but the head word is "durability" and the concept is a property
    # of a cell, not a cell.
    words = lower.replace('_', ' ').replace('-', ' ').split()
    head = words[-1] if words else lower
    if len(head) > 5 and head.endswith(_PROPERTY_SUFFIXES):
        # Flush right by construction, so headedness is 1.0.
        suffix_score = 100 + len(head)
        if suffix_score > best_score:
            best_cls = 'mds:Property'
    return best_cls


# Suffixes that reliably nominalise a measurable quality.
_PROPERTY_SUFFIXES = ('ivity', 'ance', 'ence', 'ility', 'ness', 'ity', 'ude')


def classify_by_llm(labels: list[str], branch_curies: list[str]) -> dict[str, str]:
    """Typed branch assignment, constrained to `branch_curies`. {} on any failure.

    Never raises. A provider outage degrades the ladder to keywords, which is
    recorded as such - it must not take the run down, and it must not silently
    look like a successful classification.
    """
    if not PLACEMENT_LLM or not labels:
        return {}
    try:
        from typing import Literal

        from pydantic import BaseModel, Field
        from pydantic_ai import Agent

        from kw import llm
        from kw.config import pydantic_model, output_spec, RATE_LIMIT_DELAY

        Branch = Literal[tuple(branch_curies)]  # type: ignore[valid-type]

        class _Assignment(BaseModel):
            concept: str = Field(description='The concept, copied exactly.')
            branch: Branch = Field(description='The single best MDS-Onto branch.')

        class _Batch(BaseModel):
            assignments: list[_Assignment] = Field(description='One entry per concept.')

        hints = '\n'.join(f'  {c} - {BRANCH_HINTS[c]}'
                          for c in branch_curies if c in BRANCH_HINTS)
        agent = Agent(
            pydantic_model, output_type=output_spec(_Batch), retries=2,
            system_prompt=(
                'You are an ontologist working in materials data science. Assign each '
                'concept to exactly one MDS-Onto branch, using ONLY the branch names '
                f'listed here:\n{hints}\n\n'
                'Decide what the concept IS, not what subfield studies it. '
                '"surface passivation layer" is a Material even though it is studied by '
                'characterisation. "contact resistance" is a Property, not a Material, '
                'even though it involves a contact. A quantity you could put a number '
                'and a unit on is a Property.'
            ),
        )

        out: dict[str, str] = {}
        batches = [labels[i:i + PLACEMENT_BATCH_SIZE]
                   for i in range(0, len(labels), PLACEMENT_BATCH_SIZE)]
        for i, batch in enumerate(batches, 1):
            result = llm.run_sync(
                agent,
                f'Assign each of these {len(batch)} concepts to one branch.\n\n'
                + '\n'.join(f'- {c}' for c in batch),
            )
            for a in result.output.assignments:
                key = str(a.concept).strip().lower()
                if key:
                    out[key] = str(a.branch)
            if i < len(batches):
                time.sleep(RATE_LIMIT_DELAY)
        return out
    except Exception as exc:                      # noqa: BLE001 - deliberate
        print(f'  [placement] LLM assignment unavailable ({type(exc).__name__}: {exc}); '
              f'falling back to keyword rules for this run.')
        return {}
