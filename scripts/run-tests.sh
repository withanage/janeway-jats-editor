#!/usr/bin/env bash
# Run the plugin test-suite inside a Janeway checkout.
# Usage: JANEWAY_SRC=/path/to/janeway/src scripts/run-tests.sh [extra manage.py test args]
set -euo pipefail
JANEWAY_SRC="${JANEWAY_SRC:-$HOME/projects/janeway/src}"
cd "$JANEWAY_SRC"
if [ -f ../.venv/bin/activate ]; then . ../.venv/bin/activate; fi
export JANEWAY_SETTINGS_MODULE="${JANEWAY_SETTINGS_MODULE:-core.dev_settings}"
# A dotted label fails because src/plugins is a namespace package, so use a path.
exec python manage.py test plugins/jats_editor/tests --top-level-directory . "$@"
