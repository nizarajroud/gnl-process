#!/bin/bash
# GNL Full Reset: kill processes + clean DB + delete all notebooks
# Requires user confirmation before executing

echo "⚠️  WARNING: This will:"
echo "   1. Kill all running GNL processes"
echo "   2. Delete ALL records from the database"
echo "   3. Delete ALL notebooks from NotebookLM"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted."
    exit 1
fi

# 1. Kill processes
pkill -9 -f 'generate_via_mcp' 2>/dev/null
pkill -9 -f 'download_via_mcp' 2>/dev/null
pkill -9 -f 'clean_notebooks_mcp' 2>/dev/null
pkill -9 -f 'generate_and_deliver' 2>/dev/null
echo "⛔ All processes stopped"

# 2. Clean database
python /home/nizar/workspace/gnl-process/delete_all_records.py
rm -Rf logs/*
echo "🗑️  Database cleaned"

# 3. Delete all notebooks from NotebookLM
python /home/nizar/workspace/gnl-process/clean_notebooks_mcp.py --target=all --confirm
echo "🗑️  All notebooks deleted"

echo ""
echo "✅ Full reset complete."
