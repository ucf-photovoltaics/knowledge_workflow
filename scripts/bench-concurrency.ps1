# Author: Brent Thompson <brent.thompson@ucf.edu>
# Summary: bench-concurrency support for Knowledge Workflow; retain the existing operational notes below.
<# Finds how many model requests at once this GPU handles best with Ollama.

For each slot count it restarts Ollama with that many request slots, reruns the enrich stage of a copy of a
finished run with every model answer asked fresh (KW_FRESH=1, so caches do not hide the work), and records wall
time, calls per minute, output tokens per second, failures, step-downs, peak VRAM and whether Ollama had to put part
of the model on the CPU (ollama ps). It stops at the first level that fails, steps down or spills to the CPU, or
gains less than MinGain over the best so far. Copies are deleted afterwards; results go to outputs\bench\.

  .\scripts\bench-concurrency.ps1 -FromRun tea-n5-20261014-154503
  .\scripts\bench-concurrency.ps1 -FromRun tea-n10-20261014-154503 -Slots 2,4,8,16
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FromRun,
    [int[]]$Slots = @(1, 2, 4, 6, 8, 12),
    [double]$MinGain = 0.10
)

$ErrorActionPreference = 'Continue'   # native stderr must not stop the script in Windows PowerShell 5.1
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if ((Get-ScheduledTask kw-sweep -ErrorAction SilentlyContinue).State -eq 'Running') {
    throw 'The kw-sweep task is running and shares Ollama; pause it first (Disable-ScheduledTask, Stop-ScheduledTask).'
}
if (-not (Test-Path "outputs\$FromRun\run.json")) { throw "No finished run outputs\$FromRun" }
$uvExe = (Get-Command uv -CommandType Application -ErrorAction Stop).Source
$ollamaExe = (Get-Command ollama -CommandType Application -ErrorAction Stop).Source
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'
$env:LLM_PROFILE = 'ollama'
$env:KW_FRESH = '1'     # ask the model for every answer
$env:KW_SCRATCH = '1'   # keep these runs out of eval_runs.csv, the figures and integration
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$benchDir = Join-Path $root 'outputs\bench'
New-Item -ItemType Directory -Force -Path $benchDir | Out-Null
$csv = Join-Path $benchDir "concurrency-$stamp.csv"
$results = [System.Collections.Generic.List[object]]::new()

$ledgerReader = @'
import json, sys
start = float(sys.argv[2]); calls = fails = out = 0
for line in open(sys.argv[1], encoding='utf-8'):
    r = json.loads(line)
    if r['ts'] < start or r.get('cache_hit'):
        continue
    calls += 1; out += r.get('output_tokens') or 0; fails += not r.get('ok')
print(json.dumps({'calls': calls, 'output_tokens': out, 'failed': fails}))
'@
$warm = "from src.tools import llm; from src.config import LLM; llm.chat('Return ONLY JSON.', 'Reply with an empty JSON object.', LLM['model'], profile=LLM)"

function Start-Ollama($n) {
    Stop-Process -Name 'ollama app', 'ollama' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $env:OLLAMA_NUM_PARALLEL = "$n"
    Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    foreach ($i in 1..60) {
        try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null; return } catch { Start-Sleep -Seconds 1 }
    }
    throw 'Ollama did not start'
}

$best = 0.0
foreach ($n in $Slots) {
    Write-Host "== $n slot(s)" -ForegroundColor Cyan
    Start-Ollama $n
    & $uvExe run -q --with-requirements requirements.txt python -c $warm | Out-Null   # load the model before timing
    $id = "bench-$stamp-s$n"
    Copy-Item "outputs\$FromRun" "outputs\$id" -Recurse
    $gpuLog = Join-Path $benchDir "$id-gpu.csv"
    $sampler = Start-Job -ArgumentList $gpuLog -ScriptBlock {
        param($f)
        while ($true) {
            nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | Add-Content $f
            Start-Sleep -Seconds 2
        }
    }
    $start = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    $t0 = Get-Date
    & $uvExe run -q --with-requirements requirements.txt python -m src.run enrich --run-id $id --workers $n --no-figures 2>&1 |
        Out-File -Encoding utf8 (Join-Path $benchDir "$id.log")
    $code = $LASTEXITCODE
    $wall = ((Get-Date) - $t0).TotalSeconds
    $processor = (& $ollamaExe ps | Select-Object -Skip 1 | Out-String).Trim()
    Stop-Job $sampler; Remove-Job $sampler -Force
    $s = & $uvExe run -q python -c $ledgerReader "outputs\$id\ledger.jsonl" $start | ConvertFrom-Json
    $samples = @(Get-Content $gpuLog -ErrorAction SilentlyContinue | ForEach-Object { , ($_ -split ',\s*' | ForEach-Object { [double]$_ }) })
    $steppedDown = [bool](Select-String -Path (Join-Path $benchDir "$id.log") -Pattern 'reducing model concurrency' -Quiet)
    $row = [pscustomobject]@{
        slots = $n; wall_s = [math]::Round($wall, 1); exit = $code; calls = $s.calls; failed = $s.failed
        calls_per_min = [math]::Round($s.calls / $wall * 60, 1)
        output_tokens_per_s = [math]::Round($s.output_tokens / $wall, 1)
        peak_vram_mb = ($samples | ForEach-Object { $_[0] } | Measure-Object -Maximum).Maximum
        mean_gpu_util = [math]::Round((($samples | ForEach-Object { $_[1] } | Measure-Object -Average).Average), 0)
        cpu_spill = $processor -match 'CPU'; stepped_down = $steppedDown; ollama_ps = ($processor -replace '\s+', ' ')
    }
    $results.Add($row)
    $results | Export-Csv $csv -NoTypeInformation -Encoding UTF8
    $row | Format-List | Out-Host
    Remove-Item "outputs\$id" -Recurse -Force
    if ($code -ne 0 -or $row.failed -gt 0 -or $row.cpu_spill -or $row.stepped_down) {
        Write-Host "$n slots is past this GPU's limit (exit $code, $($row.failed) failed calls, CPU spill $($row.cpu_spill), step-down $steppedDown)." -ForegroundColor Yellow
        break
    }
    if ($row.output_tokens_per_s -lt $best * (1 + $MinGain)) {
        Write-Host "Less than $([int]($MinGain * 100))% faster than the best so far; stopping." -ForegroundColor Yellow
        break
    }
    $best = [math]::Max($best, $row.output_tokens_per_s)
}
Stop-Process -Name 'ollama' -Force -ErrorAction SilentlyContinue
$clean = @($results | Where-Object { $_.exit -eq 0 -and $_.failed -eq 0 -and -not $_.cpu_spill -and -not $_.stepped_down })
if ($clean) {
    $top = ($clean | Measure-Object output_tokens_per_s -Maximum).Maximum
    $pick = $clean | Where-Object { $_.output_tokens_per_s -ge 0.95 * $top } | Sort-Object slots | Select-Object -First 1
    Write-Host "Recommended: -Workers $($pick.slots) ($($pick.output_tokens_per_s) output tokens/s, peak VRAM $($pick.peak_vram_mb) MB)." -ForegroundColor Green
}
Write-Host "Results: $csv"
