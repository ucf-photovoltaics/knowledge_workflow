"""Review artifacts for evidence-backed placements and cross-domain candidates."""
import json
import re
from collections import defaultdict

from src.tools.owl import bfo_category, lineage


def context(concepts, relations):
    by_id = {c['id']: c for c in concepts}
    rows = defaultdict(list)
    for r in relations:
        if r.get('s') in by_id and r.get('o') in by_id:
            rows[r['s']].append({'p': r['p'], 'target': r['o'], 'label': by_id[r['o']]['label'],
                                  'evidence': r.get('evidence', [])[:2]})
    return rows


def paper_parents(classes, relations):
    live = {c['id']: c for c in classes if not c['excluded']}
    candidates = defaultdict(list)
    for r in relations:
        if r.get('p') == 'is_a' and r.get('s') in live and r.get('o') in live \
                and any(e.get('verified') is True for e in r.get('evidence', [])):
            candidates[r['s']].append(r)
    for cid, edges in candidates.items():
        c = live[cid]
        eligible = []
        for r in edges:
            parent = r['o']
            if parent == cid or cid in lineage(parent, live):
                c.setdefault('review_flags', []).append('paper_parent_cycle')
            elif bfo_category(cid, live) != bfo_category(parent, live):
                c.setdefault('review_flags', []).append('paper_parent_category_conflict')
            else:
                eligible.append(r)
        targets = {r['o'] for r in eligible}
        chosen = c['parent'] if c['parent'] in targets else next(iter(targets)) if len(targets) == 1 else None
        if chosen:
            c['parent'], c['parent_source'] = chosen, 'paper_is_a'
            c['parent_evidence'] = [e for r in eligible if r['o'] == chosen for e in r.get('evidence', [])]
        elif targets:
            c.setdefault('review_flags', []).append('ambiguous_paper_parents')
    for c in live.values():
        if c['parent_source'] in ('category_default', 'type_default', 'cycle_break'):
            c.setdefault('review_flags', []).append('unresolved_placement')


def issues(classes):
    return [{'id': c['id'], 'label': c['label'], 'iri': c['iri'], 'flags': c.get('review_flags', []),
             'parent': c['parent'], 'definition_status': c.get('definition_status', ''),
             'source_definitions': c.get('definitions', [])}
            for c in classes if not c['excluded'] and c.get('review_flags')]


def correspondences(outputs, run_id, domain, classes):
    # Labels nominate candidates only; no equivalence assertions are emitted.
    def key(label):
        return re.sub(r'\s+', ' ', label.casefold()).strip()
    current = defaultdict(list)
    live = {c['id']: c for c in classes if not c['excluded']}
    def parent(c, by_id):
        p = by_id.get(c['parent'])
        return {'iri': p['iri'], 'label': p['label']} if p else {'iri': c['parent'], 'label': c['parent']}
    for c in live.values():
        current[key(c['label'])].append(c)
    found = []
    for path in sorted(outputs.glob('*/ontology/enriched.json')):
        other_run = path.parent.parent.name
        if other_run == run_id:
            continue
        manifest = path.parent.parent / 'run.json'
        if not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text(encoding='utf-8'))
            other_domain = m.get('collection', {}).get('name')
            if not other_domain or other_domain == domain or 'interop' not in m.get('stages', {}):
                continue
            previous = json.loads(path.read_text(encoding='utf-8'))
            old = {c['id']: c for c in previous if not c['excluded']}
            for c in old.values():
                for target in current.get(key(c['label']), []):
                    a, b = parent(target, live), parent(c, old)
                    found.append({'relation': 'candidate_only', 'label': target['label'],
                                  'iri': target['iri'], 'other_iri': c['iri'], 'other_run': other_run,
                                  'other_domain': other_domain, 'parent': a, 'other_parent': b,
                                  'category_conflict': bfo_category(target['id'], live) != bfo_category(c['id'], old),
                                  'parent_difference': key(a['label']) != key(b['label']),
                                  'definition': target.get('definition', ''), 'other_definition': c.get('definition', ''),
                                  'definition_difference': target.get('definition', '') != c.get('definition', '')})
        except (ValueError, KeyError, TypeError) as e:
            found.append({'other_run': other_run, 'review_error': type(e).__name__})
    return found
