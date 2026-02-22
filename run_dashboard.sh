#!/usr/bin/env bash
# run_dashboard.sh — Launch the sweep dashboard web server
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
# Uses the project-local .venv; create with: uv venv && uv pip install -e ".[dev]"
source "${SCRIPT_DIR}/.venv/bin/activate"

# Ensure scripts directory exists
mkdir -p scripts

echo "Starting Sweep Dashboard..."
echo "  URL: http://0.0.0.0:8050"
echo "  Press Ctrl+C to stop"
echo ""

uvicorn sweep_dashboard.app:app --host 0.0.0.0 --port 8050 --reload
