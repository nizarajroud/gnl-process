#!/bin/bash
# Kill all GNL processes and clean database
pkill -9 -f 'generate_via_mcp' 2>/dev/null
pkill -9 -f 'download_via_mcp' 2>/dev/null
pkill -9 -f 'clean_notebooks_mcp' 2>/dev/null
echo "⛔ All processes stopped"

# Clean database
python /home/nizar/workspace/gnl-process/delete_all_records.py
rm -Rf logs/*
