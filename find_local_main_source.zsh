#!/usr/bin/env zsh

if [ -z "$1" ]; then
    # Output error as JSON to stderr or exit silently
    exit 1
fi

LOCAL_STORAGE_PATH=$(grep "^GNL_PROCESSING_PATH=" /home/nizar/workspace/gnl-process/.env | cut -d'=' -f2)
SEARCH_PATH="$LOCAL_STORAGE_PATH/../../courses:$LOCAL_STORAGE_PATH/../../exam"

FILE_PATH=$(find ${(s.:.)SEARCH_PATH} -name "$1" -type f 2>/dev/null | head -1)

if [ -n "$FILE_PATH" ]; then
    PARENT_DIR=$(dirname "$FILE_PATH")
    PARENT_NAME=$(basename "$PARENT_DIR")
    FILE_NAME=$(basename "$FILE_PATH")
    # Output only JSON, nothing else
    printf '{"absolute_path":"%s","file_name":"%s","parent_folder":"%s"}' "$FILE_PATH" "$FILE_NAME" "$PARENT_NAME"
else
    printf '{"absolute_path":null,"file_name":null,"parent_folder":null}'
fi