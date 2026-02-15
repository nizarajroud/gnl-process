#!/bin/bash
# Extract only the JSON part (starts with { and ends with })
json_only=$(echo "$1" | grep -o '{.*}')
echo "$json_only" | python3 "$(dirname "$0")/CollectAndSave.py"
