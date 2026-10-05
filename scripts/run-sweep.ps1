<# Cumulative collection runs, with isolated failures and explicit integration inputs. #>
[CmdletBinding()]
param(
    [ValidateRange(1, 32)][int]$Workers = 2,
    [string[]]$Collections = @('tea', 'reliability', 'si-topcon'),
    [switch]$ContinueTo50,
    [ValidateRange(0, 5)][int]$Retries = 1,
    [string]$SweepId = (Get-Date -Format 'yyyyMMdd-HHmmss')
)

$ErrorActionPreference = 'Stop'
# Native failures are classified below rather than terminating the whole sweep.
$PSNativeCommandUseErrorActionPreference = $false
if ($SweepId -notmatch '^[A-Za-z0-9_-]+$') { throw 'SweepId must contain only letters, numbers, underscores or hyphens.' }
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'
$env:LLM_PROFILE = 'ollama'
$logDir = Join-Path $root "outputs\sweep-$SweepId"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$summary = [System.Collections.Generic.List[object]]::new()

function Save-Result($Kind, $Limit, $Id, $Status, $Detail) {
    $summary.Add([pscustomobject]@{
        kind = $Kind; limit = $Limit; run_id = $Id; status = $Status; detail = $Detail
    })
    $summary | Export-Csv (Join-Path $logDir 'summary.csv') -NoTypeInformation -Encoding UTF8
}

function Read-WorkflowStatus([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Workflow status file missing: $Path"
    }
    # Project with Python: full manifests can contain empty JSON keys, which
    # ConvertFrom-Json rejects in Windows PowerShell 5.1 and without -AsHashtable.
    $reader = @'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
corpus = data.get('corpus', {})
valid = data.get('valid', data.get('stages', {}).get('interop', {}).get('valid', False))
print(json.dumps({'valid': valid is True, 'processed': corpus.get('processed', 0),
                  'failed_count': len(corpus.get('failed', []))}))
'@
    $status = & uv run python -c $reader $Path
    if ($LASTEXITCODE -ne 0) { throw "Could not read workflow status: $Path (exit $LASTEXITCODE)" }
    return ($status | ConvertFrom-Json)
}

function Invoke-Workflow([string[]]$WorkflowArgs, [string]$Id) {
    for ($attempt = 0; $attempt -le $Retries; $attempt++) {
        $logPath = Join-Path $logDir "$Id-attempt$attempt.log"
        try {
            # Continue permits native stderr to reach the log in Windows PowerShell 5.1.
            $ErrorActionPreference = 'Continue'
            & uv run --with-requirements requirements.txt python -m src.run @WorkflowArgs 2>&1 |
                Tee-Object -FilePath $logPath | Out-Host
            $code = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = 'Stop'
        }
        if ($code -eq 0) { return $true }
        $text = if (Test-Path $logPath) { Get-Content $logPath -Raw } else { '' }
        $transient = $text -match 'APIConnectionError|APITimeoutError|InternalServerError|RateLimitError|HTTP (429|502|503|504)|ConnectionError|ConnectTimeout|ReadTimeout|database is locked|WinError 32|WinError 10061|out of memory|overloaded'
        if (-not $transient -or $attempt -eq $Retries) {
            Write-Warning "$Id stopped (exit $code). Continuing the sweep; inspect $logPath"
            return $false
        }
        Write-Warning "$Id encountered a transient error; resuming with one worker in 10 seconds."
        # Keep the same run id; completed stages are skipped.
        $workerIndex = [Array]::IndexOf($WorkflowArgs, '--workers')
        if ($workerIndex -ge 0) { $WorkflowArgs[$workerIndex + 1] = '1' }
        Start-Sleep -Seconds 10
    }
    return $false
}

$limits = @(5, 10, 15, 20, 25)
if ($ContinueTo50) { $limits += @(30, 35, 40, 45, 50) }
foreach ($n in $limits) {
    $completed = @()
    foreach ($collection in $Collections) {
        $id = "$collection-n$n-$SweepId"
        try {
            $ok = Invoke-Workflow -Id $id -WorkflowArgs @(
                'all', '--collection', $collection, '--limit', "$n", '--run-id', $id, '--workers', "$Workers"
            )
            if (-not $ok) {
                Save-Result 'domain' $n $id 'failed' 'Command failed; see attempt log.'
                continue
            }
            $manifest = Read-WorkflowStatus "outputs\$id\run.json"
            if ($manifest.valid -ne $true -or $manifest.processed -lt 1) {
                Save-Result 'domain' $n $id 'invalid' 'Incomplete or structurally invalid; excluded from integration.'
                continue
            }
            if ($manifest.failed_count -gt 0) {
                Save-Result 'domain' $n $id 'partial' 'Failed papers; excluded from integration. Other runs continue.'
                continue
            }
            $completed += $id
            $detail = "$($manifest.processed) papers processed; requested $n."
            Save-Result 'domain' $n $id 'completed' $detail
        } catch {
            Write-Warning "$id : $($_.Exception.Message); continuing."
            Save-Result 'domain' $n $id 'failed' $_.Exception.Message
        }
    }
    $integrationId = "integration-n$n-$SweepId"
    if ($completed.Count -lt 2) {
        Save-Result 'integration' $n $integrationId 'skipped' 'Fewer than two successful domains at this size.'
        continue
    }
    try {
        $ok = Invoke-Workflow -Id $integrationId -WorkflowArgs (
            @('integrate', '--run-id', $integrationId, '--workers', "$Workers", '--runs') + $completed
        )
        if (-not $ok) {
            Save-Result 'integration' $n $integrationId 'failed' 'Command failed; see attempt log.'
            continue
        }
        $validation = Read-WorkflowStatus "outputs\$integrationId\validation.json"
        if ($validation.valid -eq $true) {
            Save-Result 'integration' $n $integrationId 'completed' ($completed -join ', ')
        } else {
            Save-Result 'integration' $n $integrationId 'invalid' 'Structural validation failed.'
        }
    } catch {
        Write-Warning "$integrationId : $($_.Exception.Message); continuing."
        Save-Result 'integration' $n $integrationId 'failed' $_.Exception.Message
    }
}
try {
    Write-Host 'Writing the final sweep report...'
    $reportLog = Join-Path $logDir 'report.log'
    $ErrorActionPreference = 'Continue'
    & uv run --with-requirements requirements.txt python -m src.figures `
        --sweep-summary (Join-Path $logDir 'summary.csv') `
        --out (Join-Path $logDir 'report') --title "Paper sweep $SweepId" 2>&1 |
        Tee-Object -FilePath $reportLog | Out-Host
    $reportCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($reportCode -ne 0) { throw "Report generation failed (exit $reportCode); inspect $reportLog" }
    Write-Host "Report: $(Join-Path $logDir 'report\report.html')"
} catch {
    $ErrorActionPreference = 'Stop'
    Write-Warning $_.Exception.Message
    Save-Result 'report' '' "sweep-$SweepId-report" 'failed' $_.Exception.Message
}
$summary | Format-Table -AutoSize | Out-Host
Write-Host "Logs and summary: $logDir"
if (@($summary | Where-Object { $_.status -ne 'completed' }).Count -gt 0) { exit 1 }
exit 0
