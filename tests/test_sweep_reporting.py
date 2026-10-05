"""Sweep reports must preserve failed attempts and consistent integration selection."""
import csv
from types import SimpleNamespace

from src import figures, report


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_integration_selection_requires_all_inputs_and_nonempty_set(tmp_path):
    write_csv(tmp_path / 'eval_integrations.csv', [
        {'row_type': 'integration', 'run_id': 'chosen', 'input_runs': 'tea+reliability'},
        {'row_type': 'integration', 'run_id': 'other-profile', 'input_runs': 'tea+frontier'},
        {'row_type': 'integration', 'run_id': 'empty', 'input_runs': ''},
        {'row_type': 'integration', 'run_id': 'repeat', 'input_runs': 'tea+reliability'},
    ])
    selected = figures.load_integrations(tmp_path, ['tea', 'reliability'], ['chosen'])
    assert [row['run_id'] for row in selected] == ['chosen']
    assert figures.load_integrations(tmp_path, []) == []


def test_explicit_empty_selection_does_not_load_other_runs(tmp_path):
    (tmp_path / 'unrelated').mkdir()
    write_csv(tmp_path / 'eval_runs.csv', [
        {'row_type': 'run', 'run_id': 'unrelated', 'collection': 'tea',
         'workflow_revision': 'revision', 'llm_profile': 'ollama'},
    ])
    rows, _ = figures.load_runs(tmp_path, 'revision', None, [])
    assert rows == []


def test_csv_keeps_one_header_and_failed_outcomes(tmp_path):
    path = tmp_path / 'summary.csv'
    statuses = [
        {'kind': 'domain', 'run_id': 'good', 'status': 'completed', 'limit': '5', 'detail': ''},
        {'kind': 'domain', 'run_id': 'bad', 'status': 'failed', 'limit': '5', 'detail': 'connection failed'},
        {'kind': 'integration', 'run_id': 'skipped', 'status': 'skipped', 'limit': '5', 'detail': 'too few domains'},
    ]
    report._write_csv(path, [{'run_id': 'good', 'total_wall_min': 2}], [], statuses)
    with path.open(encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert rows[0]['total_wall_min'] == '2'
    assert rows[1]['status'] == 'failed' and rows[1]['total_wall_min'] == ''
    assert rows[2]['row_type'] == 'integration' and rows[2]['status'] == 'skipped'


def test_report_with_no_completed_runs_still_lists_failures(tmp_path):
    statuses = [{'kind': 'domain', 'run_id': 'bad', 'status': 'failed', 'limit': '5',
                 'detail': 'stopped <model> | unavailable'}]
    out = SimpleNamespace(folder=tmp_path, index=[], tables={}, skipped=[], integration_ids=[])
    report.write(out, [], tmp_path, 'revision', [], [], statuses=statuses)
    assert 'Sweep outcomes' in (tmp_path / 'report.md').read_text()
    html = (tmp_path / 'report.html').read_text()
    assert 'bad' in html and 'stopped &lt;model&gt;' in html
