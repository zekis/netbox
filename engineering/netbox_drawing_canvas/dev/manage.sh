#!/bin/sh
# Always uses the isolated local configuration; never inherits a production configuration.
set -eu
DRAWING_PLUGIN_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${NETBOX_SRC:?Set NETBOX_SRC to a disposable NetBox source checkout}"
: "${DRAWING_PYTHON:?Set DRAWING_PYTHON to the isolated virtualenv python}"
export NETBOX_CONFIGURATION=drawing_dev
export PYTHONPATH="$DRAWING_PLUGIN_ROOT/dev:$DRAWING_PLUGIN_ROOT:$NETBOX_SRC/netbox"
cd "$NETBOX_SRC/netbox"
exec "$DRAWING_PYTHON" manage.py "$@"
