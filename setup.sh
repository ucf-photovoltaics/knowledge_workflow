#!/usr/bin/env bash
# setup.sh — one-shot environment setup for the Knowledge Workflow (macOS / Linux).
#
#   ./setup.sh           core install (uv + dependencies + .env scaffold)
#   ./setup.sh --full    also install the optional REBEL + LoRA dependencies
#
set -euo pipefail
cd "$(dirname "$0")"

FULL=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --full or --help)"; exit 1 ;;
  esac
done

echo "==> Knowledge Workflow setup (macOS/Linux)"

# 1. uv ----------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "==> uv not found — installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # make uv available in this shell for the rest of the script
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
echo "==> uv: $(uv --version)"

# 2. dependencies ------------------------------------------------------------
echo "==> Installing core dependencies (uv sync)..."
uv sync

if [ "$FULL" -eq 1 ]; then
  echo "==> Installing optional REBEL + LoRA dependencies..."
  uv pip install transformers torch peft datasets accelerate
fi

# 3. .env --------------------------------------------------------------------
if [ ! -f .env ]; then
  if [ -f env.example.txt ]; then
    cp env.example.txt .env
    echo "==> Created .env from env.example.txt — edit it to add your Zotero key + LLM endpoint."
  else
    echo "==> WARNING: env.example.txt not found; create .env manually."
  fi
else
  echo "==> .env already exists — leaving it untouched."
fi

# 4. next steps --------------------------------------------------------------
cat <<'EOF'

==> Done.
Next:
  1. Edit .env (Zotero API key, LLM endpoint/model).
  2. uv run python -m kw --list-collections
  3. uv run python -m kw run -c <collection_id>
EOF
