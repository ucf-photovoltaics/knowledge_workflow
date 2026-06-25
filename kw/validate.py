# -*- coding: utf-8 -*-
"""
Validation gate (Step 4) — must PASS before the MDS-Onto upload.

The gate is a registry of checks. Each check returns a uniform result:

    {name, severity, status, summary, details}
      severity : 'required' | 'advisory'   (from config.REQUIRED_CHECKS)
      status   : 'pass' | 'fail' | 'error' | 'skip'

Strict semantics: the gate passes only when EVERY required check has
status == 'pass'. A required check that errors, is skipped, or cannot run
counts as NOT pass and therefore blocks the upload. Advisory checks are always
reported but never block.

Checks:
  * ontocheck  - CWRU SDLE OntoCheck metric suite (REQUIRED by default)
  * oops       - OOPS! critical-pitfall scan via REST (REQUIRED by default)
  * alignment  - fraction of classes tracing to a BFO/CCO/MDS/PMD parent
  * reasoner   - DL consistency via owlready2 + HermiT (opt-in RUN_REASONER)
  * shacl      - shape conformance via pyshacl       (opt-in RUN_SHACL)

`evaluate()` runs every check, writes nothing itself; call `write_report()` to
emit the detailed per-run report (validation_report.md + .json).
"""
from __future__ import annotations

import io
import os
import json
import logging
import contextlib
from datetime import datetime

import rdflib
from rdflib.namespace import RDF, RDFS, OWL

from kw.config import (
    NS, RUN_REASONER, RUN_OOPS, RUN_SHACL, OOPS_ENDPOINT, SHACL_SHAPES,
    REQUIRED_CHECKS, RUN_ONTOCHECK, ONTOCHECK_GATE_METRICS,
    MDS_DESIGN_TARGET, DEFINITION_COVERAGE_TARGET,
    ONTOCHECK_RUN_ADVISORY, ONTOCHECK_NETWORK,
)

UPPER_PREFIXES = (NS['bfo'], NS['cco'], NS['mds'],
                  'https://cwrusdle.bitbucket.io/mds', 'https://w3id.org/pmd/')
ALIGNMENT_TARGET = 0.80
SKOS_DEFINITION = rdflib.URIRef(NS['skos'] + 'definition')

# OntoCheck metrics that hit the network — advisory only unless ONTOCHECK_NETWORK.
_ONTOCHECK_NETWORK_METRICS = {'externalLinks', 'rdfDump', 'sparqlEndpoint'}
# Gate-metric names handled by dedicated logic below (so they are not double-run
# as advisory). 'definitionCoverage' is computed here from skos:definition.
_GATE_DISPATCHER_NAMES = {
    'duplicateLabels', 'missingDomainRange', 'mdsDesignCheck',
    'humanLicense', 'isolatedElements', 'definitionCheck',
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _result(name, status, summary, details=None):
    return {'name': name, 'severity': 'advisory', 'status': status,
            'summary': summary, 'details': details or {}}


def _unwrap(v):
    """OntoCheck returns some dict values as single-element sets (e.g. {3}).
    Pull the scalar back out; pass scalars through unchanged."""
    if isinstance(v, (set, frozenset)):
        return next(iter(v), 0)
    return v


def _json_safe(obj):
    if isinstance(obj, (set, frozenset)):
        return sorted(_json_safe(x) for x in obj)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, rdflib.term.Node):
        return str(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ---------------------------------------------------------------------------
# alignment (advisory) — also supplies the legacy top-level metrics
# ---------------------------------------------------------------------------
def alignment_ratio(g: rdflib.Graph) -> tuple[float, int, int]:
    classes = [c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, rdflib.URIRef)]
    aligned = sum(
        any(str(p).startswith(UPPER_PREFIXES)
            for p in g.objects(c, RDFS.subClassOf) if isinstance(p, rdflib.URIRef))
        for c in classes
    )
    total = len(classes) or 1
    return aligned / total, aligned, len(classes)


def _check_alignment(g: rdflib.Graph) -> dict:
    ratio, aligned, total = alignment_ratio(g)
    ok = ratio >= ALIGNMENT_TARGET
    return _result('alignment', 'pass' if ok else 'fail',
                   f'{aligned}/{total} classes ({ratio:.0%}) trace to BFO/CCO/MDS/PMD '
                   f'(target {ALIGNMENT_TARGET:.0%})',
                   {'alignment_ratio': round(ratio, 3), 'aligned_to_upper': aligned,
                    'classes': total})


# ---------------------------------------------------------------------------
# reasoner (advisory, opt-in)
# ---------------------------------------------------------------------------
def _check_reasoner(ttl_path: str) -> dict:
    if not RUN_REASONER:
        return _result('reasoner', 'skip', 'disabled (RUN_REASONER=false)')
    try:
        import owlready2
        onto = owlready2.get_ontology('file://' + os.path.abspath(ttl_path)).load()
        with onto:
            owlready2.sync_reasoner(infer_property_values=False)
        bad = list(owlready2.default_world.inconsistent_classes())
        if bad:
            return _result('reasoner', 'fail',
                           f'{len(bad)} unsatisfiable/inconsistent class(es)',
                           {'inconsistent': [str(c) for c in bad]})
        return _result('reasoner', 'pass', 'ontology is DL-consistent')
    except Exception as exc:
        return _result('reasoner', 'error', f'reasoner unavailable ({type(exc).__name__})',
                       {'error': str(exc)})


# ---------------------------------------------------------------------------
# OOPS! (required by default)
# ---------------------------------------------------------------------------
def _check_oops(ttl_path: str) -> dict:
    if not RUN_OOPS:
        return _result('oops', 'skip', 'disabled (RUN_OOPS=false)')
    try:
        import re
        import requests
        rdfxml = rdflib.Graph().parse(ttl_path, format='turtle').serialize(format='xml')
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<OOPSRequest><OntologyURI></OntologyURI>'
            f'<OntologyContent><![CDATA[{rdfxml}]]></OntologyContent>'
            '<Pitfalls></Pitfalls><OutputFormat>RDF/XML</OutputFormat></OOPSRequest>'
        )
        resp = requests.post(OOPS_ENDPOINT, data=body.encode('utf-8'),
                             headers={'Content-Type': 'application/xml'}, timeout=60)
        resp.raise_for_status()
        critical: list[str] = []
        for seg in re.findall(r'(?is)critical.{0,400}', resp.text):
            critical.extend(re.findall(r'P\d{2}', seg))
        critical = sorted(set(critical))
        if critical:
            return _result('oops', 'fail', f'{len(critical)} critical pitfall(s): '
                           + ', '.join(critical), {'critical': critical})
        return _result('oops', 'pass', 'no critical pitfalls', {'critical': []})
    except Exception as exc:
        return _result('oops', 'error', f'OOPS! unavailable ({type(exc).__name__})',
                       {'error': str(exc)})


# ---------------------------------------------------------------------------
# SHACL (advisory, opt-in)
# ---------------------------------------------------------------------------
def _check_shacl(ttl_path: str) -> dict:
    if not RUN_SHACL:
        return _result('shacl', 'skip', 'disabled (RUN_SHACL=false)')
    if not os.path.isfile(SHACL_SHAPES):
        return _result('shacl', 'error', f'shapes file not found: {SHACL_SHAPES}')
    try:
        from pyshacl import validate as shacl_validate
        conforms, _g, _t = shacl_validate(
            ttl_path, shacl_graph=SHACL_SHAPES, data_graph_format='turtle',
            shacl_graph_format='turtle', inference='none', advanced=True)
        return _result('shacl', 'pass' if conforms else 'fail',
                       'conforms' if conforms else 'shape violations')
    except Exception as exc:
        return _result('shacl', 'error', f'SHACL unavailable ({type(exc).__name__})',
                       {'error': str(exc)})


# ---------------------------------------------------------------------------
# OntoCheck (required by default)
# ---------------------------------------------------------------------------
def _definition_coverage(g: rdflib.Graph) -> tuple[float, int, int]:
    classes = [c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, rdflib.URIRef)]
    with_def = sum(1 for c in classes if next(g.objects(c, SKOS_DEFINITION), None) is not None)
    total = len(classes) or 1
    return with_def / total, with_def, len(classes)


def _run_gate_metric(metric: str, ttl_path: str, g: rdflib.Graph) -> dict:
    """Run one gate metric; return {score, passed, summary}. Stdout suppressed."""
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            if metric == 'duplicateLabels':
                from ontocheck import find_duplicate_labels_from_graph as f
                n = int(f(ttl_path))
                return {'score': n, 'passed': n == 0, 'summary': f'{n} duplicate label(s)'}
            if metric == 'missingDomainRange':
                from ontocheck import get_properties_missing_domain_and_range as f
                d = f(ttl_path)
                cd, cr = int(d['count_missing_domain']), int(d['count_missing_range'])
                return {'score': {'missing_domain': cd, 'missing_range': cr},
                        'passed': cd == 0 and cr == 0,
                        'summary': f'{cd} missing domain, {cr} missing range'}
            if metric == 'mdsDesignCheck':
                from ontocheck import mds_design_check_v_0_0_1 as f
                cov = float(f(ttl_path))
                return {'score': round(cov, 3), 'passed': cov >= MDS_DESIGN_TARGET,
                        'summary': f'MDS design coverage {cov:.0%} (target {MDS_DESIGN_TARGET:.0%})'}
            if metric == 'humanLicense':
                from ontocheck import check_human_readable_license_ttl as f
                v = int(f(ttl_path))
                return {'score': v, 'passed': v == 1,
                        'summary': 'human-readable license present' if v == 1
                                   else 'no human-readable license'}
            if metric == 'isolatedElements':
                from ontocheck import check_for_isolated_elements as f
                d = f(ttl_path)
                ic = int(_unwrap(d.get('Number of isolated classes', 0)))
                ip = int(_unwrap(d.get('Number of isolated properties', 0)))
                return {'score': {'isolated_classes': ic, 'isolated_properties': ip},
                        'passed': ic == 0 and ip == 0,
                        'summary': f'{ic} isolated class(es), {ip} isolated property(ies)'}
            if metric == 'definitionCoverage':
                cov, n, total = _definition_coverage(g)
                return {'score': round(cov, 3), 'passed': cov >= DEFINITION_COVERAGE_TARGET,
                        'summary': f'{n}/{total} classes defined ({cov:.0%}, '
                                   f'target {DEFINITION_COVERAGE_TARGET:.0%})'}
        return {'score': None, 'passed': False, 'summary': f'unknown gate metric {metric!r}'}
    except Exception as exc:
        return {'score': None, 'passed': False, 'summary': f'error: {type(exc).__name__}: {exc}'}


def _run_advisory_metrics(ttl_path: str) -> dict:
    """Run the non-gate OntoCheck metrics for the report. Never affects the gate."""
    out: dict = {}
    try:
        from ontocheck.run_assessment import METRIC_DISPATCHER
    except Exception as exc:
        return {'_error': f'{type(exc).__name__}: {exc}'}
    skip = set(_GATE_DISPATCHER_NAMES) | {'searchClass'}
    if not ONTOCHECK_NETWORK:
        skip |= _ONTOCHECK_NETWORK_METRICS
    for name, fn in METRIC_DISPATCHER.items():
        if name in skip:
            continue
        sink = io.StringIO()
        try:
            with contextlib.redirect_stdout(sink):
                score = fn(ttl_path)
            out[name] = {'score': _json_safe(score), 'status': 'ran'}
        except Exception as exc:
            out[name] = {'score': None, 'status': f'error: {type(exc).__name__}'}
    return out


def _check_ontocheck(ttl_path: str, g: rdflib.Graph) -> dict:
    if not RUN_ONTOCHECK:
        return _result('ontocheck', 'skip', 'disabled (RUN_ONTOCHECK=false)')
    try:
        import ontocheck  # noqa: F401  (presence check)
    except Exception as exc:
        return _result('ontocheck', 'error',
                       f'OntoCheck not installed ({type(exc).__name__}) — '
                       'pip install OntoCheck', {'error': str(exc)})

    gate: dict = {}
    all_pass = True
    for metric in sorted(ONTOCHECK_GATE_METRICS):
        res = _run_gate_metric(metric, ttl_path, g)
        gate[metric] = res
        all_pass = all_pass and bool(res['passed'])

    advisory = _run_advisory_metrics(ttl_path) if ONTOCHECK_RUN_ADVISORY else {}
    n_pass = sum(1 for r in gate.values() if r['passed'])
    failed = [m for m, r in gate.items() if not r['passed']]
    summary = f'{n_pass}/{len(gate)} gate metrics passed'
    if failed:
        summary += f' — failing: {", ".join(failed)}'
    return _result('ontocheck', 'pass' if all_pass else 'fail', summary,
                   {'gate_metrics': gate, 'advisory_metrics': advisory})


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def evaluate(ttl_path: str) -> dict:
    g = rdflib.Graph()
    g.parse(ttl_path, format='turtle')

    checks = [
        _check_ontocheck(ttl_path, g),
        _check_oops(ttl_path),
        _check_alignment(g),
        _check_reasoner(ttl_path),
        _check_shacl(ttl_path),
    ]
    # apply severity from config
    for c in checks:
        c['severity'] = 'required' if c['name'] in REQUIRED_CHECKS else 'advisory'

    required_failed = [c['name'] for c in checks
                       if c['severity'] == 'required' and c['status'] != 'pass']
    gate_passed = not required_failed

    # legacy/top-level fields (kept for pipeline.py + the benchmark CSV)
    align = next((c for c in checks if c['name'] == 'alignment'), None)
    align_d = align['details'] if align else {}
    oops = next((c for c in checks if c['name'] == 'oops'), None)

    return {
        'file': ttl_path,
        'triples': len(g),
        'classes': align_d.get('classes', 0),
        'aligned_to_upper': align_d.get('aligned_to_upper', 0),
        'alignment_ratio': align_d.get('alignment_ratio', 0.0),
        'alignment_pass': (align['status'] == 'pass') if align else False,
        'oops_status': oops['status'] if oops else 'skip',
        'oops_critical': (oops['details'].get('critical', []) if oops else []),
        'checks': checks,
        'required_checks': sorted(REQUIRED_CHECKS),
        'required_failed': required_failed,
        'gate_passed': gate_passed,
        'passed': gate_passed,   # backward-compatible alias
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
_STATUS_ICON = {'pass': '✅', 'fail': '❌', 'error': '⚠️', 'skip': '➖'}


def _render_md(report: dict, collection: str | None) -> str:
    verdict = 'PASS' if report['gate_passed'] else 'FAIL'
    upload = ('ALLOWED — required checks passed' if report['gate_passed']
              else 'BLOCKED — one or more required checks did not pass')
    lines = [
        f'# Validation report — {collection or os.path.basename(report["file"])}',
        '',
        f'_Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}_',
        '',
        f'## Gate: {verdict}',
        '',
        f'**MDS-Onto upload: {upload}.**',
        '',
        f'- Ontology: `{report["file"]}`',
        f'- Triples: {report["triples"]}  |  Classes: {report["classes"]}',
        f'- Required checks: {", ".join(report["required_checks"]) or "(none)"}',
    ]
    if report['required_failed']:
        lines.append(f'- Required checks failing: **{", ".join(report["required_failed"])}**')
    lines += ['', '## Checks', '',
              '| Check | Severity | Status | Summary |', '|---|---|---|---|']
    for c in report['checks']:
        icon = _STATUS_ICON.get(c['status'], c['status'])
        lines.append(f'| {c["name"]} | {c["severity"]} | {icon} {c["status"]} | {c["summary"]} |')

    # OntoCheck metric breakdown
    oc = next((c for c in report['checks'] if c['name'] == 'ontocheck'), None)
    if oc and oc['details'].get('gate_metrics'):
        lines += ['', '### OntoCheck gate metrics', '',
                  '| Metric | Result | Score |', '|---|---|---|']
        for m, r in sorted(oc['details']['gate_metrics'].items()):
            res = '✅ pass' if r['passed'] else '❌ fail'
            lines.append(f'| {m} | {res} | {r["summary"]} |')
        adv = oc['details'].get('advisory_metrics') or {}
        adv = {k: v for k, v in adv.items() if not k.startswith('_')}
        if adv:
            lines += ['', '### OntoCheck advisory metrics (not gated)', '',
                      '| Metric | Score | Status |', '|---|---|---|']
            for m, r in sorted(adv.items()):
                lines.append(f'| {m} | {r.get("score")} | {r.get("status")} |')
    if report.get('ontocheck_csv'):
        lines += ['', '---', '',
                  f"OntoCheck native report: `{os.path.basename(report['ontocheck_csv'])}` "
                  f"(per-metric scores) + `{os.path.basename(report['ontocheck_log'])}` "
                  "(detailed log)."]
    return '\n'.join(lines) + '\n'


def write_ontocheck_native(ttl_path: str, out_dir: str) -> dict | None:
    """Also emit OntoCheck's OWN report next to ours: ontocheck_scores.csv (one row
    per metric) + ontocheck.log (detailed per-metric output), via the package's
    run_ontology_assessment. Root logging handlers are detached/restored around the
    call so OntoCheck's logging writes to its file and never disturbs the pipeline's.
    Honours ONTOCHECK_NETWORK (skips the live-endpoint metrics unless enabled)."""
    if not (RUN_ONTOCHECK and ttl_path):
        return None
    try:
        from ontocheck.run_assessment import run_ontology_assessment, METRIC_DISPATCHER
    except Exception as exc:                                   # noqa: BLE001
        print(f'  [validate] OntoCheck native report skipped ({type(exc).__name__})')
        return None
    metrics = [m for m in METRIC_DISPATCHER if m != 'searchClass']
    if not ONTOCHECK_NETWORK:
        metrics = [m for m in metrics if m not in _ONTOCHECK_NETWORK_METRICS]
    csv_path = os.path.join(out_dir, 'ontocheck_scores.csv')
    log_path = os.path.join(out_dir, 'ontocheck.log')
    root = logging.getLogger()
    saved, saved_level = root.handlers[:], root.level
    root.handlers = []                       # let OntoCheck's basicConfig own the file
    try:
        run_ontology_assessment(ttl_path, metrics,
                                output_log_file=log_path, output_csv_file=csv_path)
    except Exception as exc:                                   # noqa: BLE001
        print(f'  [validate] OntoCheck native report failed ({type(exc).__name__}): {exc}')
        return None
    finally:
        for h in root.handlers[:]:
            try:
                h.close()
            except Exception:
                pass
        root.handlers, root.level = saved, saved_level          # restore pipeline logging
    return {'csv': csv_path, 'log': log_path}


def write_report(report: dict, out_dir: str, collection: str | None = None) -> dict:
    """Write validation_report.md + .json into out_dir (plus OntoCheck's native
    ontocheck_scores.csv + ontocheck.log); record paths on report."""
    os.makedirs(out_dir, exist_ok=True)
    native = write_ontocheck_native(report.get('file'), out_dir)
    if native:
        report['ontocheck_csv'] = native['csv']
        report['ontocheck_log'] = native['log']
    md_path = os.path.join(out_dir, 'validation_report.md')
    json_path = os.path.join(out_dir, 'validation_report.json')
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write(_render_md(report, collection))
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(_json_safe(report), fh, indent=2)
    report['report_md'] = md_path
    report['report_json'] = json_path
    return report
