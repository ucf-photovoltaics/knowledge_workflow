# Author: Brent Thompson <brent.thompson@ucf.edu>
# Summary: stop-sweep support for Knowledge Workflow; retain the existing operational notes below.
<# Stops the kw-sweep task safely. With -Restart, checks the GPU is free and resumes the same sweep on it.
   Administrator PowerShell, in the repo folder:
     .\scripts\stop-sweep.ps1             # stop and leave it stopped (a reboot won't restart it)
     .\scripts\stop-sweep.ps1 -Restart    # stop, free the GPU, resume, confirm the model loads 100% on GPU
   A resume skips finished stages; the interrupted stage reruns, with its finished calls coming from the cache.
   Each resume uses one of auto-sweep's attempts (auto-attempts.txt). #>
#Requires -RunAsAdministrator
param(
    [switch]$Restart,
    [string]$TaskName = 'kw-sweep',
    [int]$MaxIdleVramMiB = 1024,   # VRAM in use with Ollama stopped above this = another app is holding the GPU
    [int]$LoadTimeoutMin = 10
)

$root = Split-Path $PSScriptRoot -Parent
$task = Get-ScheduledTask $TaskName -ErrorAction Stop
$taskArgs = $task.Actions[0].Arguments
if ($taskArgs -notmatch '-SweepId\s+(\S+)') { throw "Task $TaskName has no -SweepId" }
$sweepId = $Matches[1]
$ollama = if ($taskArgs -match '-OllamaExe\s+"([^"]+)"') { $Matches[1] } else { (Get-Command ollama).Source }

# 1. Stop: disable first so the boot trigger and retry loop can't restart it, then kill the whole process tree.
Disable-ScheduledTask $TaskName | Out-Null
$procs = @(Get-CimInstance Win32_Process)
$kill = @{}
function Add-Tree($p) {
    if ($p.ProcessId -eq $PID -or $kill.ContainsKey($p.ProcessId)) { return }
    $kill[$p.ProcessId] = $p.Name
    $procs | Where-Object ParentProcessId -eq $p.ProcessId | ForEach-Object { Add-Tree $_ }
}
$procs | Where-Object {
    $_.CommandLine -match 'auto-sweep\.ps1|run-sweep\.ps1' -or
    ($_.Name -match '^(python|uv)\.exe$' -and $_.CommandLine -match 'knowledge_workflow')
} | ForEach-Object { Add-Tree $_ }
Stop-ScheduledTask $TaskName
foreach ($id in $kill.Keys) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
Stop-Process -Name 'ollama app', 'ollama', 'ollama_llama_server' -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-Host "Stopped sweep $sweepId ($($kill.Count) processes)."

# 2. A kill can land mid-write; drop any half-written last line so the resume can read each ledger.
Get-ChildItem "$root\outputs" -Directory -Filter "*-$sweepId" |
    ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter ledger.jsonl } | ForEach-Object {
        $bytes = [IO.File]::ReadAllBytes($_.FullName)
        if ($bytes.Length -and $bytes[-1] -ne 10) {
            $fs = [IO.File]::Open($_.FullName, 'Open', 'Write')
            $fs.SetLength([Array]::LastIndexOf($bytes, [byte]10) + 1); $fs.Close()
            Write-Host "Trimmed a half-written line from $($_.FullName)"
        }
    }

$attempts = Get-Content "$root\outputs\sweep-$sweepId\auto-attempts.txt" -ErrorAction SilentlyContinue
if (-not $Restart) {
    Write-Host "Attempts used: $attempts. Resume with: .\scripts\stop-sweep.ps1 -Restart"
    exit 0
}

# 3. With Ollama gone, VRAM should be nearly empty. If not, something else would push the model onto the CPU.
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $name, $used, $total, $temp = (nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu `
        --format=csv,noheader,nounits | Select-Object -First 1) -split ',\s*'
    Write-Host "GPU: $name, $used / $total MiB in use, $temp C"
    if ([int]$temp -gt 85) { Write-Warning "GPU is hot and may throttle; check airflow." }
    if ([int]$used -gt $MaxIdleVramMiB) {
        nvidia-smi
        Read-Host "Close the apps listed above using the GPU, then press Enter to resume (Ctrl+C leaves it stopped)"
    }
} else { Write-Warning 'nvidia-smi not found; skipping the VRAM check.' }

# 4. Resume. auto-sweep starts Ollama itself; wait for the model to load and check where it landed.
Enable-ScheduledTask $TaskName | Out-Null
Start-ScheduledTask $TaskName
Write-Host "Resumed sweep $sweepId (attempts used before this one: $attempts). Waiting for the model to load..."
$deadline = (Get-Date).AddMinutes($LoadTimeoutMin)
do {
    Start-Sleep -Seconds 15
    $loaded = @(& $ollama ps 2>$null) | Select-Object -Skip 1 | Where-Object { "$_".Trim() }
} until ($loaded -or (Get-Date) -gt $deadline)

if (-not $loaded) {
    Write-Warning "No model loaded after $LoadTimeoutMin min. Check outputs\sweep-$sweepId\auto-sweep.log."
} elseif (-not ($loaded | Where-Object { $_ -notmatch '100% GPU' })) {
    Write-Host "On the GPU:`n$($loaded -join "`n")"
} else {
    Write-Warning "Model is partly on the CPU:`n$($loaded -join "`n")`nSomething still holds VRAM; run nvidia-smi, close it, and rerun with -Restart."
}
