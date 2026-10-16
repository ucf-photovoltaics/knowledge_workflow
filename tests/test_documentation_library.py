"""Verify documentation navigation, safe publication boundaries and Markdown rendering.

Author: Brent Thompson <brent.thompson@ucf.edu>
Uses isolated files; never launches or alters a pipeline run.
"""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from documentation_library import build_library


@pytest.fixture
def library_root(tmp_path):
    root = tmp_path / 'repo'
    for name in ('site-nav.css', 'site-nav.js', 'reviewer.css'):
        path = root / 'docs/ontology/viewer' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / 'docs/ontology/viewer' / name).read_text(encoding='utf-8'), encoding='utf-8')
    (root / 'docs/README.md').write_text('# Guide\n\n[Next](stages/normalize.md#review)\n\n[Contract](contract.json)\n\n<script>alert(1)</script>', encoding='utf-8')
    stage = root / 'docs/stages/normalize.md'
    stage.parent.mkdir(parents=True)
    stage.write_text('# Normalization\n\n## Review\n\n[Home](../README.md)\n\n[Source](../../src/example.py#L1)\n\n[Private](../../.env)', encoding='utf-8')
    (root / 'docs/contract.json').write_text('{"schema":1}', encoding='utf-8')
    (root / '.env').write_text('PRIVATE_FIXTURE=excluded', encoding='utf-8')
    source = root / 'src/example.py'
    source.parent.mkdir()
    source.write_text('print("<escaped>")', encoding='utf-8')
    inventory = root / 'docs/codebase/inventory.json'
    inventory.parent.mkdir()
    inventory.write_text(json.dumps([{'path': 'src/example.py'}, {'path': '../outside.py'}, {'path': '.env'}]), encoding='utf-8')
    return root


def test_links_headings_and_safe_sources(library_root):
    out = library_root / 'outputs/docs'
    out.mkdir(parents=True)
    (out / 'index.html').write_text('<h1>Journey</h1>', encoding='utf-8')
    result = build_library(library_root, out)
    guide = (out / 'library/docs/README.md.html').read_text(encoding='utf-8')
    stage = (out / 'library/docs/stages/normalize.md.html').read_text(encoding='utf-8')
    assert result['documents'] == 2
    assert 'stages/normalize.md.html#review' in guide
    assert 'contract.json' in guide
    assert '<script>alert(1)</script>' not in guide
    assert '&lt;script&gt;' in guide
    assert 'id="review"' in stage
    assert 'source/example' not in stage
    assert 'source/src/example.py.html#L1' in stage
    assert (out / 'source/src/example.py.html').is_file()
    assert '&lt;escaped&gt;' in (out / 'source/src/example.py.html').read_text(encoding='utf-8')
    assert '#unpublished-references' in stage
    assert not list(out.rglob('.env'))
    assert 'PRIVATE_FIXTURE' not in stage
    assert 'Information journey &amp; WebVOWL' in guide
    assert 'data-dashboard-link' in guide
    assert (out / 'library/docs/contract.json').read_text(encoding='utf-8') == '{"schema":1}'


def test_missing_graph_is_explained(library_root):
    out = library_root / 'outputs/docs'
    build_library(library_root, out)
    page = (out / 'library.html').read_text(encoding='utf-8')
    assert 'Interactive ontology views have not been exported yet' in page
    assert 'href="index.html"' not in page
    assert 'documentation-search' in page


def test_output_cannot_escape_outputs(library_root):
    with pytest.raises(ValueError, match='inside repository outputs'):
        build_library(library_root, library_root / 'public')
