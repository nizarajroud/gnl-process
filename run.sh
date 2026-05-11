#!/bin/bash
cd "$(dirname "$0")"
PYTHONPATH=. python -m gnl_core.cli "$@"
