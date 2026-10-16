# Author: Brent Thompson <brent.thompson@ucf.edu>
# Summary: run-checks support for Knowledge Workflow; retain the existing operational notes below.
<# The checks behind the 2026-10-15 speedups, on the tea collection (about 3-4 hours at 2 workers).

1. Reuse across sizes: tea-n5, then tea-n10 reusing its answers, then tea-n10 twice with every answer asked fresh.
   Reused answers should agree with fresh ones as often as two fresh answers agree with each other.
2. Study stage and domain in one call: the first fresh tea-n10's interop stage is redone on two copies, once with
   separate stage and domain calls and once more in one call, so all three see identical classes.
3. First-call answer rates per pass for the new runs and, with -Baseline, a run from before the change
   (e.g. tea-n10-20261014-154503: definitions in 15s, disjointness in 12s, separate stage and domain calls).

All runs are scratch runs (kept out of eval_runs.csv, the figures and integration). Tables go to
outputs\checks\<time>\report.txt. Ollama is restarted with -Workers slots; pause the kw-sweep task first.

  .\scripts\run-checks.ps1 -Baseline tea-n10-20261014-154503
#>
[CmdletBinding()]
param(
    [string]$Collection = 'tea',
    [string]$Baseline = '',
    [ValidateRange(1, 32)][int]$Workers = 2
)

$ErrorActionPreference = 'Continue'   # native stderr must not stop the script in Windows PowerShell 5.1
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if ((Get-ScheduledTask kw-sweep -ErrorAction SilentlyContinue).State -eq 'Running') {
    throw 'The kw-sweep task is running and shares Ollama; pause it first (Disable-ScheduledTask, Stop-ScheduledTask).'
}
$uvExe = (Get-Command uv -CommandType Application -ErrorAction Stop).Source
$ollamaExe = (Get-Command ollama -CommandType Application -ErrorAction Stop).Source
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'
$env:LLM_PROFILE = 'ollama'
$env:KW_SCRATCH = '1'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dir = Join-Path $root "outputs\checks\$stamp"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$report = Join-Path $dir 'report.txt'

Stop-Process -Name 'ollama app', 'ollama' -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$env:OLLAMA_NUM_PARALLEL = "$Workers"
Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
Start-Sleep -Seconds 5

function Invoke-Run([string]$Id, [string[]]$RunArgs, [bool]$Fresh, [string]$FacetCalls = 'combined') {
    $env:KW_FRESH = if ($Fresh) { '1' } else { '' }
    $env:KW_FACET_CALLS = $FacetCalls
    Write-Host "$(Get-Date -Format T) $Id" -ForegroundColor Cyan
    & $uvExe run -q --with-requirements requirements.txt python -m src.run @RunArgs --run-id $Id --workers $Workers --no-figures 2>&1 |
        Out-File -Encoding utf8 (Join-Path $dir "$Id.log")
    if ($LASTEXITCODE -ne 0) { throw "$Id failed; see $dir\$Id.log" }
}

function Copy-Run([string]$From, [string]$To) {
    Copy-Item "outputs\$From" "outputs\$To" -Recurse
    Remove-Item "outputs\$To\rows.jsonl" -ErrorAction SilentlyContinue   # only the redone stage's rows
}

$a = "check-$stamp-$Collection-n5"
$b = "check-$stamp-$Collection-n10-reuse"
$c = "check-$stamp-$Collection-n10-fresh1"
$d = "check-$stamp-$Collection-n10-fresh2"
$s = "check-$stamp-$Collection-n10-split"
$x = "check-$stamp-$Collection-n10-combined"
Invoke-Run $a @('all', '--collection', $Collection, '--limit', '5') $false
Invoke-Run $b @('all', '--collection', $Collection, '--limit', '10') $false
Invoke-Run $c @('all', '--collection', $Collection, '--limit', '10') $true
Invoke-Run $d @('all', '--collection', $Collection, '--limit', '10') $true
Copy-Run $c $s
Invoke-Run $s @('interop') $true 'split'
Copy-Run $c $x
Invoke-Run $x @('interop') $true 'combined'

function Compare-Runs { & $uvExe run -q python scripts\compare_runs.py @args 2>&1 }
$coverage = @('coverage', $c, $d)
if ($Baseline) { $coverage += $Baseline }
@(
    "Checks $stamp ($Collection, $Workers workers)", '',
    '== 1. Answers reused across sizes', (Compare-Runs reuse $a $b $c $d), '',
    '== 2. Study stage and domain in one call', (Compare-Runs facets $c $s $x), '',
    '== 3. Rows answered on the first call', (Compare-Runs @coverage)
) | ForEach-Object { $_ } | Tee-Object -FilePath $report
Write-Host "`nReport: $report"
