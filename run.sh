#!/usr/bin/env bash
# Single entry point. Usage: ./run.sh serve | index | import-gramps [--tree NAME] [--apply] | merge KEEP_ID DROP_ID | export-way | test
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ "${1:-serve}" = "test" ]; then exec python3 -m unittest discover -s tests -p "test_*.py"; fi
exec python3 -u server.py "$@"
