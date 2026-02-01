#!/usr/bin/env zsh

if [ -z "$1" ]; then
    echo "Usage: $0 <filename> [generation_mode] [source_type] [podcast_theme] [podcast_subfolder]"
    echo "generation_mode: single (default) or bulk"
    exit 1
fi

LOCAL_STORAGE_PATH=$(grep "^LOCAL_STORAGE_PATH=" /home/nizar/workspace/gnl-process/.env | cut -d'=' -f2)
GENERATION_MODE=${2:-single}
GENERATION_MODE=$(echo "$GENERATION_MODE" | tr '[:upper:]' '[:lower:]')
SOURCE_TYPE=${3:-""}
PODCAST_THEME=${4:-""}
PODCAST_SUBFOLDER=${5:-""}

SEARCH_PATH="$LOCAL_STORAGE_PATH/$PODCAST_SUBFOLDER"

if [ "$GENERATION_MODE" = "single" ]; then
    FILE_PATH=$(find "$SEARCH_PATH" -maxdepth 1 -name "$1" -type f 2>/dev/null)
    if [ -n "$FILE_PATH" ]; then
        PARENT_DIR=$(dirname "$FILE_PATH")
        PARENT_NAME=$(basename "$PARENT_DIR")
        FILE_NAME=$(basename "$FILE_PATH")
        echo "{\"mode\":\"single\",\"fullPath\":\"$FILE_PATH\",\"parentDir\":\"$PARENT_NAME\",\"fileName\":\"$FILE_NAME\",\"downloadState\":false,\"sourceType\":\"$SOURCE_TYPE\",\"podcastTheme\":\"$PODCAST_THEME\",\"podcastSubfolder\":\"$PODCAST_SUBFOLDER\"}"
    else
        echo "{\"mode\":\"single\",\"fullPath\":null,\"parentDir\":null,\"fileName\":null,\"downloadState\":false,\"sourceType\":\"$SOURCE_TYPE\",\"podcastTheme\":\"$PODCAST_THEME\",\"podcastSubfolder\":\"$PODCAST_SUBFOLDER\"}"
    fi
elif [ "$GENERATION_MODE" = "bulk" ]; then
    FILE_PATH=$(find "$SEARCH_PATH" -maxdepth 1 -name "$1" -type f 2>/dev/null | head -1)
    if [ -n "$FILE_PATH" ]; then
        PARENT_DIR=$(dirname "$FILE_PATH")
        PARENT_NAME=$(basename "$PARENT_DIR")
        FILES_JSON=$(find "$PARENT_DIR" -maxdepth 1 -type f 2>/dev/null | while read file; do
            FILE_NAME=$(basename "$file")
            echo "{\"fullPath\":\"$file\",\"parentDir\":\"$PARENT_NAME\",\"fileName\":\"$FILE_NAME\",\"downloadState\":false,\"sourceType\":\"$SOURCE_TYPE\",\"podcastTheme\":\"$PODCAST_THEME\",\"podcastSubfolder\":\"$PODCAST_SUBFOLDER\"}"
        done | paste -sd,)
        echo "{\"mode\":\"bulk\",\"files\":[$FILES_JSON]}"
    else
        echo "{\"mode\":\"bulk\",\"files\":[]}"
    fi
else
    echo "{\"error\":\"generation_mode must be 'single' or 'bulk'\"}"
    exit 1
fi
