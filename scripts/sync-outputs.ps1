# Author: Brent Thompson <brent.thompson@ucf.edu>
# Summary: Pull pipeline outputs from the Slurm cluster and push them to the dashboard's Cloud Storage bucket.
<#
.SYNOPSIS
Copies outputs/ from the cluster checkout into the bucket the Cloud Run dashboard mounts at /app/outputs.
.DESCRIPTION
Packs outputs/ on the cluster (no PDFs, caches, dashboard data, private settings or databases), downloads it
over SSH, unpacks it into a local staging folder, then uploads only new or changed files to the bucket.
Nothing in the bucket or on the cluster is deleted. Running unattended needs key-based SSH with no prompt.
.EXAMPLE
.\scripts\sync-outputs.ps1 -SshHost hpc -RemoteRepo '~/knowledge_workflow'
#>
param(
    [Parameter(Mandatory)][string]$SshHost,
    [string]$RemoteRepo = '~/knowledge_workflow',
    [string]$Bucket = 'gs://research-dpv-kw-outputs',
    [string]$Staging = (Join-Path $PSScriptRoot '..\outputs\hpc-sync')
)
$ErrorActionPreference = 'Stop'
$archive = 'kw-outputs-sync.tgz'
$local = Join-Path $env:TEMP $archive
$exclude = "--exclude='*.pdf' --exclude='outputs/cache' --exclude='outputs/dashboard' --exclude='*/private' --exclude='*.sqlite3*' --exclude='__pycache__'"

ssh -o BatchMode=yes $SshHost "tar -czf ~/$archive $exclude -C $RemoteRepo outputs"
if ($LASTEXITCODE -ne 0) { throw "Could not pack outputs on $SshHost." }
scp -o BatchMode=yes "${SshHost}:$archive" $local
if ($LASTEXITCODE -ne 0) { throw 'Could not download the outputs archive.' }
ssh -o BatchMode=yes $SshHost "rm -f ~/$archive"

New-Item -ItemType Directory -Force -Path $Staging | Out-Null
tar -xzf $local -C $Staging
if ($LASTEXITCODE -ne 0) { throw 'Could not unpack the outputs archive.' }
Remove-Item $local

gcloud storage rsync (Join-Path $Staging 'outputs') $Bucket --recursive
if ($LASTEXITCODE -ne 0) { throw "Could not upload to $Bucket." }
Write-Host "$(Get-Date -Format s) synced $SshHost`:$RemoteRepo/outputs -> $Bucket"
