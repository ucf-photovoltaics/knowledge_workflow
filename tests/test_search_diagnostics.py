"""Oversized queries never reach providers; repeated diagnostics remain reviewable."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.tools import lexical, matportal, mds_portal, mds_onto_open_api, materials_project, progress


@pytest.mark.parametrize('query', ['', 'x' * 513, '界' * 60])
@pytest.mark.parametrize('provider', [matportal, mds_portal])
def test_bad_portal_queries_fail_before_network(monkeypatch, provider, query):
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid query reached the network')
    monkeypatch.setattr(provider.requests, 'get', unexpected)
    with pytest.raises(ValueError):
        provider.search(query)


def test_query_boundary_and_materials_guard(monkeypatch):
    assert lexical.validate_search_query('x' * 512) == 'x' * 512
    assert lexical.validate_search_query('boron-doped emitter') == 'boron-doped emitter'
    monkeypatch.setattr(materials_project, '_get', lambda *a, **k: pytest.fail('Network called'))
    with pytest.raises(ValueError):
        materials_project.search('formula', 'x' * 513, 10)
    with pytest.raises(ValueError):
        mds_onto_open_api.search_mdsonto('x' * 513)


def test_repeated_diagnostics_are_redacted_and_thread_safe(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_API_KEY', 'private-test-value')
    monkeypatch.setattr(progress, '_folder', tmp_path)
    monkeypatch.setattr(progress, '_run_id', 'fixture')
    monkeypatch.setattr(progress, '_stage', ['enrich'])
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda i: progress.log(f'MatPortal search failed {i}: apikey=private-test-value'), range(20)))
    progress._warning('provider warning', UserWarning, 'fixture.py', 1)
    progress._handler.emit(logging.LogRecord('provider', logging.WARNING, 'fixture.py', 2,
                                            'provider warning from logging', (), None))
    events = [json.loads(line) for line in (tmp_path / 'warnings_errors.jsonl').read_text().splitlines()]
    assert len(events) == 22
    assert all(e['run_id'] == 'fixture' and e['stage'] == 'enrich' for e in events)
    assert 'private-test-value' not in (tmp_path / 'run.log').read_text()
    assert 'private-test-value' not in (tmp_path / 'warnings_errors.jsonl').read_text()
    assert progress.redact('apikey=unconfigured-value&x=1 Bearer unconfigured-token') == 'apikey=***&x=1 Bearer ***'
