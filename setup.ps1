<#
.SYNOPSIS
  One-shot environment setup for the Knowledge Workflow (Windows PowerShell).
.DESCRIPTION
  Installs uv if missing, installs dependencies via `uv sync`, and creates a
  .env from env.example.txt. Use -Full to also install the optional REBEL + LoRA
  dependencies (transformers, torch, peft, datasets, accelerate).
.EXAMPLE
  .\setup.ps1
.EXAMPLE
  .\setup.ps1 -Full
#>
param(
  [switch]$Full
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

Write-Host "==> Knowledge Workflow setup (Windows)" -ForegroundColor Cyan

# 1. uv ----------------------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "==> uv not found - installing..."
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  # make uv available in this session for the rest of the script
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
Write-Host "==> uv: $(uv --version)"

# 2. dependencies ------------------------------------------------------------
Write-Host "==> Installing core dependencies (uv sync)..."
uv sync

if ($Full) {
  Write-Host "==> Installing optional REBEL + LoRA dependencies..."
  uv pip install transformers torch peft datasets accelerate
}

# 3. .env --------------------------------------------------------------------
if (-not (Test-Path .env)) {
  if (Test-Path env.example.txt) {
    Copy-Item env.example.txt .env
    Write-Host "==> Created .env from env.example.txt - edit it to add your Zotero key + LLM endpoint."
  } else {
    Write-Host "==> WARNING: env.example.txt not found; create .env manually." -ForegroundColor Yellow
  }
} else {
  Write-Host "==> .env already exists - leaving it untouched."
}

# 4. next steps --------------------------------------------------------------
Write-Host ""
Write-Host "==> Done." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Edit .env (Zotero API key, LLM endpoint/model)."
Write-Host "  2. uv run python -m kw --list-collections"
Write-Host "  3. uv run python -m kw run -c <collection_id>"
