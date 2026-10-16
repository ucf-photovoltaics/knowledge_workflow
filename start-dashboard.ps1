# Author: Brent Thompson <brent.thompson@ucf.edu>
# Summary: start-dashboard support for Knowledge Workflow; retain the existing operational notes below.
<#
.SYNOPSIS
Starts the local UCF DPV dashboard wrapper in its separate environment.
.DESCRIPTION
Defaults to http://127.0.0.1:8056. Use -Port to choose another listener.
Refreshes public documentation and serves it on the dashboard's own port.
Does not stop an existing dashboard or change the pipeline environment.
#>
param([ValidateRange(1, 65535)][int]$Port = 8056)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$dashboardPython = Join-Path $PSScriptRoot 'outputs\dashboard\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $dashboardPython)) {
    uv --cache-dir outputs/dashboard/uv-cache venv --python .venv/Scripts/python.exe outputs/dashboard/.venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the separate dashboard environment.' }
    uv --cache-dir outputs/dashboard/uv-cache pip install --python $dashboardPython -r dpv_dashboard/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install dashboard dependencies.' }
}
& $dashboardPython (Join-Path $PSScriptRoot 'scripts\documentation_library.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the local documentation library.' }
Write-Host "UCF DPV Knowledge Workflow: http://127.0.0.1:$Port"
Write-Host "Documentation: http://127.0.0.1:$Port/documentation/library.html"
& $dashboardPython -m dpv_dashboard --port $Port
