#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [ -d ".venv" ]; then
  exec .venv/bin/python -m canvas_mcp
fi
exec python -m canvas_mcp
