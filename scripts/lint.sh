#!/usr/bin/env bash
# Lint and format-check the plugin with ruff (config in ruff.toml).
# Usage: scripts/lint.sh [--fix]
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff not found: pip install ruff (or run via 'uvx ruff')" >&2
  exit 1
fi
if [ "${1:-}" = "--fix" ]; then
  ruff check --fix .
  ruff format .
else
  ruff check .
  ruff format --check .
fi
