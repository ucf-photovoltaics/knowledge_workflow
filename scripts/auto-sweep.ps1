# Runs a paper sweep to completion, resuming after crashes and failed runs (up to MaxAttempts starts).
# Meant to be started by the kw-sweep scheduled task at boot; safe to run by hand too (one copy at a time).
# Each attempt reruns scripts\run-sweep.ps1 with the same sweep ID, so completed stages are skipped.
# Writes DONE in outputs\sweep-<id> when the sweep succeeds; later starts then exit at once.
#
# Scheduled task (administrator PowerShell, in the repo folder):
#   $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\scripts\auto-sweep.ps1`" -SweepId <id> -Workers 2 " +
#          "-UvExe `"$((Get-Command uv).Source)`" -OllamaExe `"$((Get-Command ollama).Source)`""
#   Register-ScheduledTask -TaskName kw-sweep -Force -Trigger (New-ScheduledTaskTrigger -AtStartup) `
#       -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument $arg -WorkingDirectory $PWD) `
#       -Principal (New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U) `
#       -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
#                  -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew)
#   Start-ScheduledTask kw-sweep          # pause: Disable-ScheduledTask kw-sweep; Stop-ScheduledTask kw-sweep
param(
    [Parameter(Mandatory)][string]$SweepId,
    [string]$UvExe = (Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source,
    [string]$OllamaExe = (Get-Command ollama -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source,
    [int]$MaxAttempts = 10,
    [ValidateRange(1, 32)][int]$Workers = 2   # model requests at once; scripts\bench-concurrency.ps1 finds your GPU's limit
)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$logDir = Join-Path $root "outputs\sweep-$SweepId"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$doneFile = Join-Path $logDir 'DONE'
$countFile = Join-Path $logDir 'auto-attempts.txt'
if (Test-Path $doneFile) { exit 0 }

# One copy at a time, across sessions (the boot task and a hand-started copy).
$mutex = [System.Threading.Mutex]::new($false, 'Global\kw-sweep')
try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
if (-not $owned) { exit 0 }

Start-Transcript -Append -Path (Join-Path $logDir 'auto-sweep.log') | Out-Null
if (-not $UvExe -or -not $OllamaExe) { Write-Host "uv or ollama not found (uv: '$UvExe', ollama: '$OllamaExe')"; exit 1 }

$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'
$env:LLM_PROFILE = 'ollama'
$control = @{ Slots = 0; Server = $null }

function Start-Ollama($Slots) {
    Stop-Process -Name 'ollama app','ollama' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $env:OLLAMA_NUM_PARALLEL = "$Slots"
    $control.Server = Start-Process -FilePath $OllamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru
    $control.Slots = $Slots
    Start-Sleep -Seconds 3
}

# Each run starts with $Workers Ollama slots; when the pipeline halves its request limit after an overload,
# Ollama is restarted with that many slots (requests in flight are retried by the pipeline).
function uv {
    if ($control.Slots -ne $Workers) { Start-Ollama $Workers }
    & $UvExe @args 2>&1 | ForEach-Object {
        $line = $_
        if ("$line" -match 'reducing model concurrency to (\d+)' -and [int]$Matches[1] -lt $control.Slots) {
            Write-Host "Restarting Ollama with $($Matches[1]) request slot(s)."
            Start-Ollama ([int]$Matches[1])
        }
        $line
    }
    $global:LASTEXITCODE = $LASTEXITCODE
}

$attempt = [int](Get-Content $countFile -ErrorAction SilentlyContinue | Select-Object -First 1)
while ($attempt -lt $MaxAttempts) {
    $attempt++
    Set-Content $countFile $attempt
    Write-Host "$(Get-Date -Format s) sweep $SweepId, attempt $attempt of $MaxAttempts"
    & .\scripts\run-sweep.ps1 -Workers $Workers -ContinueTo50 -SweepId $SweepId
    $code = $LASTEXITCODE
    Write-Host "$(Get-Date -Format s) run-sweep exit code $code"
    if ($code -eq 0) {
        Set-Content $doneFile (Get-Date -Format s)
        Write-Host "Done. Report: $logDir\report\report.html"
        break
    }
    Start-Sleep -Seconds 60
}
if (-not (Test-Path $doneFile)) { Write-Host "Stopped after $MaxAttempts attempts; see summary.csv and the attempt logs." }
Stop-Transcript | Out-Null
