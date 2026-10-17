"""Check saved environments and Slurm sweep accounting without a GPU or model server.

Author: Brent Thompson <brent.thompson@ucf.edu>
Fixtures cover resume boundaries, cache/failed-attempt tokens, power integration and missing counters.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import figures, report, run


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def samples(folder, name, rows):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f'gpu-metrics-{name}.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['timestamp_epoch', 'gpu_uuid', 'power_w', 'utilization_pct'])
        writer.writerows(rows)


def test_environment_queries_selected_devices_and_excludes_secrets(monkeypatch):
    monkeypatch.setenv('KW_GPU_IDS', 'GPU-selected')
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '0')
    monkeypatch.setenv('KW_VLLM_TP', '2')
    monkeypatch.setenv('KW_VLLM_VERSION', 'fixture-version')
    monkeypatch.setenv('SLURM_JOB_ID', '123')
    monkeypatch.setenv('SLURM_JOB_PARTITION', 'gpu')
    monkeypatch.setenv('SLURMD_NODENAME', 'node-a')
    monkeypatch.setenv('VLLM_EXTRA_ARGS', '--dtype=bfloat16 --api-key excluded-fixture --max-model-len 8192')
    monkeypatch.setenv('OPENAI_API_KEY', 'excluded-fixture')
    query = Mock(return_value=SimpleNamespace(stdout='GPU-selected, Example GPU, 81920\n'))
    monkeypatch.setattr(run.subprocess, 'run', query)
    env = run._environment()
    assert env['gpu_count'] == 1
    assert env['gpus'][0]['memory_bytes'] == 81920 * 1024 ** 2
    assert '--id=GPU-selected' in query.call_args.args[0]
    assert query.call_args.kwargs['timeout'] == 5
    assert env['slurm']['job_id'] == '123' and env['slurm']['node'] == 'node-a'
    assert env['serving']['tensor_parallel_size'] == '2'
    assert env['serving']['max_model_len'] == '8192'
    assert env['serving']['dtype'] == 'bfloat16'
    assert env['vllm_version'] == 'fixture-version'
    assert 'excluded-fixture' not in json.dumps(env)


@pytest.mark.parametrize('error', [FileNotFoundError(), subprocess.TimeoutExpired('nvidia-smi', 5)])
def test_missing_gpu_probe_is_nonfatal(monkeypatch, error):
    monkeypatch.delenv('CUDA_VISIBLE_DEVICES', raising=False)
    monkeypatch.setattr(run.subprocess, 'run', Mock(side_effect=error))
    env = run._environment()
    assert env['gpu_count'] is None and env['gpu_status'] == 'unavailable'
    assert env['python_version']


def test_run_saves_environment_before_work_and_keeps_resume_history(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'OUTPUTS', tmp_path)
    monkeypatch.setattr(run, 'configure_logging', Mock())
    monkeypatch.setattr(run.config, 'COLLECTIONS', {'tea': {'domain': 'tea'}})
    monkeypatch.setattr(run.config, 'SCRATCH_RUN', True)
    monkeypatch.setattr(run.config, 'domain_of', lambda _: 'tea')
    monkeypatch.setattr(run, '_config', lambda: {})
    monkeypatch.setattr(run, '_git', lambda: 'commit')
    monkeypatch.setattr(run, '_environment', Mock(side_effect=[{'host': 'node-a'}, {'host': 'node-b'}]))
    run.Run('fixture', 'tea')
    first = json.loads((tmp_path / 'fixture/run.json').read_text())
    assert first['environment']['host'] == 'node-a'
    run.Run('fixture', 'tea')
    saved = json.loads((tmp_path / 'fixture/run.json').read_text())
    assert saved['environment']['host'] == 'node-b'
    assert [e['host'] for e in saved['environment_history']] == ['node-a', 'node-b']


def test_power_integral_weighted_utilization_and_allocation_totals(tmp_path):
    write(tmp_path / 'sweep-session-a.json', {'started_at': 0, 'ended_at': 60, 'gpu_count': 2})
    samples(tmp_path, 'a', [[0, 'A', 100, 20], [30, 'A', 200, 40], [60, 'A', 100, 60],
                            [0, 'B', 100, 80], [30, 'B', 100, 80], [60, 'B', 100, 80]])
    got = figures.gpu_statistics(tmp_path)
    assert got['wall_s'] == 60
    assert got['gpu_hours'] == pytest.approx(120 / 3600)
    assert got['energy_kwh'] == pytest.approx(15000 / 3_600_000)
    assert got['gpu_utilization_pct'] == pytest.approx(60)
    assert got['power_gpu_hours'] == pytest.approx(120 / 3600)


def test_resume_sessions_do_not_bridge_idle_gaps_or_double_count_samples(tmp_path):
    for tag, start in [('a', 0), ('b', 600)]:
        write(tmp_path / f'sweep-session-{tag}.json', {'started_at': start, 'ended_at': start + 30, 'gpu_count': 1})
        samples(tmp_path, tag, [[start, 'A', 100, 50], [start + 30, 'A', 100, 50]])
    samples(tmp_path, 'duplicate', [[0, 'A', 100, 50], [30, 'A', 100, 50]])
    got = figures.gpu_statistics(tmp_path)
    assert got['wall_s'] == 60
    assert got['gpu_hours'] == pytest.approx(60 / 3600)
    assert got['energy_kwh'] == pytest.approx(6000 / 3_600_000)
    assert 'Overlapping' in ' '.join(got['notes'])


def test_missing_power_and_long_gaps_stay_explicit(tmp_path):
    samples(tmp_path, 'a', [[0, 'A', 'N/A', 50], [30, 'A', 'N/A', 50], [300, 'A', 100, 60]])
    got = figures.gpu_statistics(tmp_path)
    assert got['energy_kwh'] is None
    assert got['gpu_utilization_pct'] == 50
    assert got['utilization_gpu_hours'] == pytest.approx(30 / 3600)
    assert 'gaps' in ' '.join(got['notes'])


def test_failed_attempt_tokens_and_cache_hits_are_accounted_once(tmp_path):
    for name, tokens in [('good', 100), ('failed', 50), ('integration', 25)]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / 'ledger.jsonl').write_text('\n'.join(json.dumps(row) for row in [
            {'input_tokens': tokens, 'output_tokens': 10, 'cache_hit': False},
            {'input_tokens': 9999, 'output_tokens': 9999, 'cache_hit': True}]) + '\n', encoding='utf-8')
    context = figures.run_context(tmp_path, [], ['good'], [
        {'kind': 'domain', 'run_id': 'good'}, {'kind': 'domain', 'run_id': 'failed'},
        {'kind': 'integration', 'run_id': 'integration'}])
    assert context['totals']['input_tokens'] == 175
    assert context['totals']['output_tokens'] == 30


def test_parallel_runs_use_submission_wall_and_gpu_allocation_once(tmp_path):
    sweep = tmp_path / 'sweep'
    write(sweep / 'sweep-session-a.json', {'started_at': 0, 'ended_at': 60, 'gpu_count': 2})
    for name in ['tea', 'reliability']:
        write(tmp_path / name / 'run.json', {'stages': {'extract': {'wall_s': 60}},
              'compute': {'total': {'input_tokens': 100, 'output_tokens': 20}}})
    totals = figures.run_context(tmp_path, [], ['tea', 'reliability'], sweep_folder=sweep)['totals']
    assert totals['wall_s'] == 60
    assert totals['gpu_hours'] == pytest.approx(120 / 3600)
    assert totals['tokens_per_s'] == 4


def test_partial_ledger_and_legacy_wall_are_labeled(tmp_path):
    write(tmp_path / 'partial/run.json', {'stages': {'extract': {'wall_s': 60}}})
    (tmp_path / 'partial/ledger.jsonl').write_text('{"input_tokens":10,"output_tokens":2}\n{"input_tokens":', encoding='utf-8')
    totals = figures.run_context(tmp_path, [], ['partial'])['totals']
    assert totals['input_tokens'] == 10 and totals['output_tokens'] == 2
    assert 'summed recorded stage' in totals['wall_basis']
    assert 'partial' in ' '.join(totals['notes'])
    assert totals['gpu_hours'] is None
    assert figures.run_context(tmp_path, [], [])['totals']['input_tokens'] is None


def test_setup_and_totals_in_both_reports_without_probe(tmp_path, monkeypatch):
    write(tmp_path / 'fixture/run.json', {'git_commit': 'abc', 'config': {'model_extraction': 'model-a',
          'embed_model': 'embed-a', 'workflow_revision': 'rev-a'}, 'compute': {'total': {'input_tokens': 100, 'output_tokens': 20}},
          'environment': {'host': '<node-a>', 'gpu_status': 'unavailable', 'python_version': '3.x',
                          'serving': {'max_model_len': '8192'}, 'slurm': {}}})
    monkeypatch.setattr(run, '_environment', Mock(side_effect=AssertionError('must use saved environment')))
    out = SimpleNamespace(folder=tmp_path, index=[], tables={}, skipped=[], integration_ids=[])
    rows = [{'run_id': 'fixture', 'collection': 'tea'}]
    report.write(out, rows, tmp_path, 'rev-a', ['fixture'], [])
    md, html = ((tmp_path / filename).read_text(encoding='utf-8') for filename in ('report.md', 'report.html'))
    assert md.index('## Setup') < md.index('## Contents')
    assert 'embed-a' in md and 'abc' in md and 'model-a' in md
    assert '100 input tokens' in md and '20 output tokens' in md
    assert 'GPU-hours: not recorded' in md
    assert '&lt;node-a&gt;' in html and '<node-a>' not in html
    assert 'additional model work recorded at each' in report.READ['compute_by_stage']


def test_bad_run_id_cannot_read_outside_outputs(tmp_path):
    with pytest.raises(ValueError, match='inside the outputs'):
        figures.run_context(tmp_path, [], ['../private'])


@pytest.mark.parametrize('termination,expected', [('exit 7', 7), ('kill -TERM $$', 143)])
def test_sampler_cleanup_and_exit_status_in_bash(tmp_path, termination, expected):
    bash = os.getenv('KW_TEST_BASH') or (shutil.which('bash') if os.name != 'nt' else None)
    if not bash:
        pytest.skip('Set KW_TEST_BASH to a real Bash executable for the shell fixture.')
    source = (Path(__file__).resolve().parents[1] / 'scripts/slurm-sweep.sh').read_text(encoding='utf-8')
    sampler = source.split('# One file per submission:', 1)[1].split('weights_gb()', 1)[0]
    sampler = '# One file per submission:' + sampler
    log = (tmp_path / 'logs').as_posix()
    python = sys.executable.replace('\\', '/')
    harness = tmp_path / 'fixture.sh'
    harness.write_text(f'''#!/usr/bin/env bash
set -uo pipefail
LOG='{log}'
mkdir -p "$LOG"
NGPU=1
SLURM_JOB_ID=fixture
SWEEP_STARTED_AT=$(date -u +%s)
GPU_QUERY=()
python3() {{ '{python}' "$@"; }}
nvidia-smi() {{ printf 'GPU-fixture,100,50\\n'; }}
timeout() {{ shift; "$@"; }}
{sampler}
sleep 0.2
{termination}
''', encoding='utf-8')
    process = subprocess.run([bash, str(harness)], capture_output=True, text=True, timeout=20)
    assert process.returncode == expected, process.stderr
    session = json.loads(next((tmp_path / 'logs').glob('sweep-session-*.json')).read_text())
    assert session['ended_at'] >= session['started_at']
    assert session['gpu_count'] == 1
    with next((tmp_path / 'logs').glob('gpu-metrics-*.csv')).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) >= 2
    assert all(row['gpu_uuid'] == 'GPU-fixture' for row in rows)


def test_slurm_retry_exports_its_reduced_worker_limit(tmp_path):
    bash = os.getenv('KW_TEST_BASH') or (shutil.which('bash') if os.name != 'nt' else None)
    if not bash:
        pytest.skip('Set KW_TEST_BASH to a real Bash executable for the shell fixture.')
    source = (Path(__file__).resolve().parents[1] / 'scripts/slurm-sweep.sh').read_text(encoding='utf-8')
    retry = 'run_kw() {' + source.split('run_kw() {', 1)[1].split('stop_if_down()', 1)[0]
    log = tmp_path.as_posix()
    harness = tmp_path / 'retry-fixture.sh'
    harness.write_text(f'''#!/usr/bin/env bash
set -uo pipefail
LOG='{log}'
WORKERS=8
RETRIES=1
PARALLEL_DOMAINS=1
PY=(fake_python)
healthy() {{ return 0; }}
sleep() {{ :; }}
fake_python() {{
    printf '%s\\n' "$KW_VLLM_WORKERS" >> "$LOG/observed-workers.txt"
    if [ ! -e "$LOG/first-attempt" ]; then touch "$LOG/first-attempt"; echo APIConnectionError; return 1; fi
    return 0
}}
{retry}
run_kw fixture all --run-id fixture --workers 8
''', encoding='utf-8')
    process = subprocess.run([bash, str(harness)], capture_output=True, text=True, timeout=20)
    assert process.returncode == 0, process.stderr
    assert (tmp_path / 'observed-workers.txt').read_text().splitlines() == ['8', '4']
