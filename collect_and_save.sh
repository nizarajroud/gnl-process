#!/bin/bash
echo "$1" | python3 "$(dirname "$0")/CollectAndSave.py"
