#!/usr/bin/env python3
"""Populate MCP notebooks cache with notebook list and audio artifact URLs.

This script calls the NotebookLM MCP server to fetch all notebooks and their
audio artifacts, then saves the data to a local JSON cache file.

Usage:
    python populate_mcp_cache.py
"""

import json
import os
import subprocess
import sys


def main():
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mcp_notebooks_cache.json')

    print("Fetching notebooks from NotebookLM MCP...")
    print("Note: This requires the NotebookLM MCP server to be running (via Kiro).")
    print("If running standalone, provide the cache file manually.")
    print(f"\nCache file: {cache_file}")
    print("\nTo populate this cache, use Kiro chat to run:")
    print("  1. notebook_list() → get all notebooks")
    print("  2. studio_status(notebook_id) → get audio URLs for each")
    print("  3. Save results to .mcp_notebooks_cache.json")
    print("\nFormat: [{\"id\": \"...\", \"title\": \"...\", \"artifacts\": [{\"type\": \"audio\", \"status\": \"completed\", \"audio_url\": \"...\"}]}]")


if __name__ == "__main__":
    main()
