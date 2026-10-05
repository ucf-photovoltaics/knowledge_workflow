"""Exercise the actual PowerShell driver with a fake CLI, never remote services."""
import csv
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('extended,last_limit', [(False, 25), (True, 50)])
def test_sweep_retries_skips_and_continues(tmp_path, extended, last_limit):
    shell = shutil.which('powershell') or shutil.which('pwsh')
    if not shell:
        pytest.skip('PowerShell unavailable')
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copyfile(Path(__file__).parents[1] / 'scripts' / 'run-sweep.ps1', scripts / 'run-sweep.ps1')
    harness = tmp_path / 'harness.ps1'
    harness.write_text(r'''
$global:attempts = @{}
function global:Start-Sleep { param($Seconds) }
function global:uv {
    $tokens = @($args)
    $id = $tokens[[Array]::IndexOf($tokens, '--run-id') + 1]
    $count = 1
    if ($global:attempts.ContainsKey($id)) { $count = $global:attempts[$id] + 1 }
    $global:attempts[$id] = $count
    $global:LASTEXITCODE = 0
    if ($id -like 'tea-n5-*' -and $count -eq 1) {
        'APIConnectionError: transient'; $global:LASTEXITCODE = 1; return
    }
    if ($id -like 'tea-n5-*' -and $tokens[[Array]::IndexOf($tokens, '--workers') + 1] -ne '1') {
        throw 'Retry failed to use one worker'
    }
    if ($id -like 'reliability-n5-*' -or $id -like 'integration-n15-*') {
        'ValueError: terminal fixture error'; $global:LASTEXITCODE = 1; return
    }
    $dir = Join-Path $PWD "outputs\$id"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if ($id -like 'integration-*') {
        '{"valid":true}' | Set-Content (Join-Path $dir 'validation.json')
        $inputs = $tokens[([Array]::IndexOf($tokens, '--runs') + 1)..($tokens.Count - 1)]
        $inputs -join ',' | Set-Content (Join-Path $dir 'inputs.txt')
    } else {
        $n = [int]$tokens[[Array]::IndexOf($tokens, '--limit') + 1]
        $failed = @()
        if ($id -like 'si-topcon-n10-*') { $failed = @(@{ key='failed-paper' }) }
        @{ stages=@{interop=@{valid=$true}}; corpus=@{processed=$n;failed=$failed} } |
            ConvertTo-Json -Depth 6 | Set-Content (Join-Path $dir 'run.json')
    }
    "completed $id"
}
& "$PSScriptRoot\scripts\run-sweep.ps1" -SweepId fixture EXTENDED
exit $LASTEXITCODE
'''.replace('EXTENDED', '-ContinueTo50' if extended else ''), encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    rows = list(csv.DictReader((tmp_path / 'outputs' / 'sweep-fixture' / 'summary.csv').open(encoding='utf-8-sig')))
    by_id = {r['run_id']: r for r in rows}
    assert by_id['tea-n5-fixture']['status'] == 'completed'
    assert by_id['reliability-n5-fixture']['status'] == 'failed'
    assert by_id['si-topcon-n10-fixture']['status'] == 'partial'
    assert by_id['integration-n15-fixture']['status'] == 'failed'
    assert by_id[f'integration-n{last_limit}-fixture']['status'] == 'completed'
    inputs = (tmp_path / 'outputs' / 'integration-n5-fixture' / 'inputs.txt').read_text()
    assert 'reliability' not in inputs
    assert 'tea-n5-fixture' in inputs and 'si-topcon-n5-fixture' in inputs
    assert (tmp_path / 'outputs' / 'sweep-fixture' / 'tea-n5-fixture-attempt1.log').exists()
