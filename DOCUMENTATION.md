# GNL Process - NotebookLM Automation

Automated workflow for processing content sources and generating NotebookLM podcasts with database tracking and audio processing.

## Overview

This project automates:
- Adding sources to NotebookLM (Web, YouTube, Google Drive, Local files)
- Generating AI podcasts from sources
- Downloading and organizing generated audio
- Converting and combining audio files
- Tracking podcast generation state in SQLite database

## Prerequisites

- Python 3.x
- Chrome browser with user data directory
- ffmpeg (for audio conversion)
- NovaAct API key

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file
4. Initialize database: `python setup_database.py`
5. Setup Chrome profile: `python setup_chrome_user_data_dir.py`

## Core Scripts

### `nllm-aws-asl-add-generate-gnl.py`
Adds source to NotebookLM and generates podcast.
```bash
python nllm-aws-asl-add-generate-gnl.py <sourceIdentifier> <title> <content_type> [user_data_dir] [--headless]
```
**Content types**: `GoogleDrive`, `WebAndYoutube`, `LocalStorage`
**Features**:
- Validates content type against `.env` config
- Supports multiple source types
- Auto-renames notebook with custom title
- Saves generation state to database
- Interactive/headless browser modes

### `nllm-aws-asl-download-rename-gnl.py`
Downloads generated podcast and saves with custom name.
```bash
python nllm-aws-asl-download-rename-gnl.py <title> [user_data_dir] [suffix] [subsuffix] [--headless]
```
**Features**:
- Waits for download completion (5 min timeout)
- Copies from playwright temp folder
- Organizes by suffix/subsuffix folders
- Saves as `.m4a` format

### `nllm-aws-asl-clean-gnls.py`
Bulk deletes NotebookLM notebooks (up to 200).
```bash
python nllm-aws-asl-clean-gnls.py [user_data_dir] [--headless]
```

## Database Management

### `setup_database.py`
Creates `gnl.db` with `podcast_download` table.
```bash
python setup_database.py
```
**Schema**:
- `id` (PRIMARY KEY)
- `source_id`, `source_type`, `source_path`, `source_parent`
- `generation_mode` (single/bulk)
- `podcast_name`, `podcast_theme`, `podcast_subfolder`
- `download_state` (0/1)

### `CollectAndSave.py`
Saves podcast metadata to database from JSON input.
```bash
python CollectAndSave.py <json_file>
echo '<json>' | python CollectAndSave.py
```
**Modes**: `single` (one file) or `bulk` (multiple files)

### `delete_all_records.py`
Clears all database records.
```bash
python delete_all_records.py
```

## Audio Processing

### `batch_convert_to_mp3.py`
Converts M4A to MP3 and deletes original.
```bash
python batch_convert_to_mp3.py <filename> <suffix> <subsuffix>
```
**Requirements**: ffmpeg, `GNL_BACKLOG` env var

### `combine_mp3.py`
Concatenates multiple MP3 files into one.
```bash
python combine_mp3.py <subdirectory> <output.mp3>
```
**Features**:
- Uses ffmpeg concat (memory efficient)
- Moves source files to `zz/` subfolder
- Reads from `GNL_BACKLOG` path

## Utility Scripts

### `get_title.py`
Generates standardized titles from source identifiers.
```bash
python get_title.py <sourceIdentifier> [type] [subsuffix]
```
**Types**: `WebAndYoutube` (adds date prefix), `GoogleDrive`, `LocalStorage`

### `find_local_source.zsh`
Searches local storage and generates JSON for database.
```bash
./find_local_source.zsh <filename> [generation_mode] [source_type] [podcast_theme] [podcast_subfolder]
```
**Modes**: `single` or `bulk`
**Output**: JSON with file paths and metadata

### `collect_and_save.sh`
Pipes JSON to CollectAndSave.py.
```bash
./collect_and_save.sh '<json_string>'
```

## Configuration

### Environment Variables (.env)
```bash
# NovaAct Configuration
NOVA_ACT_API_KEY=your-api-key
NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL=1
USER_DATA_DIR=/path/to/chrome/User Data
HEADLESS=1  # 0 for visible, 1 for headless

# Paths
GNL_BACKLOG=/path/to/audio/storage
LOCAL_STORAGE_PATH=/path/to/local/files

# Content Types
VALID_CONTENT_TYPES=GoogleDrive,WebAndYoutube,LocalStorage
NOTEBOOKLM_URL=http://notebooklm.google.com/
```

## Workflow Examples

### Complete Single File Workflow
```bash
# 1. Setup database
python setup_database.py

# 2. Add source and generate podcast
python nllm-aws-asl-add-generate-gnl.py \
  "https://example.com/article" \
  "my-podcast-title" \
  "WebAndYoutube"

# 3. Wait 10 minutes for generation

# 4. Download podcast
python nllm-aws-asl-download-rename-gnl.py \
  "my-podcast-title" \
  --suffix "aws" \
  --subsuffix "solutions"

# 5. Convert to MP3
python batch_convert_to_mp3.py "my-podcast-title" "aws" "solutions"
```

### Bulk Local Files Processing
```bash
# 1. Find files and generate JSON
./find_local_source.zsh "document.pdf" "bulk" "LocalStorage" "tech" "ai"

# 2. Save to database
./find_local_source.zsh "document.pdf" "bulk" | ./collect_and_save.sh

# 3. Process each file (repeat for each)
python nllm-aws-asl-add-generate-gnl.py \
  "document.pdf" \
  "$(python get_title.py document.pdf LocalStorage)" \
  "LocalStorage"
```

### Combine Multiple Podcasts
```bash
# Combine all MP3s in a folder
python combine_mp3.py "aws/solutions" "combined-output.mp3"
```

## N8N Integration

The project includes n8n workflow templates (`GNL.json`, `GNL-parametrized.json`) for automation:
- Webhook trigger for podcast generation
- 10-minute wait for processing
- Automatic download and organization

## Project Structure

```
gnl-process/
├── .env                                    # Environment config
├── gnl.db                                  # SQLite database
├── setup_database.py                       # DB initialization
├── CollectAndSave.py                       # Save metadata to DB
├── delete_all_records.py                   # Clear DB records
├── nllm-aws-asl-add-generate-gnl.py       # Add source + generate
├── nllm-aws-asl-download-rename-gnl.py    # Download podcast
├── nllm-aws-asl-clean-gnls.py             # Bulk delete notebooks
├── batch_convert_to_mp3.py                # M4A to MP3 conversion
├── combine_mp3.py                          # Concatenate MP3s
├── get_title.py                            # Title generation
├── find_local_source.zsh                   # Local file search
├── collect_and_save.sh                     # JSON to DB helper
├── setup_chrome_user_data_dir.py          # Chrome setup
├── GNL.json                                # n8n workflow
└── GNL-parametrized.json                   # n8n workflow (params)
```

## Dependencies

```
fire                # CLI interface
requests            # HTTP requests
beautifulsoup4      # HTML parsing
python-dotenv       # Environment management
pyfzf               # Fuzzy finding
nova_act            # Browser automation
pydub               # Audio processing
```

## Troubleshooting

**Database locked**: Close other connections to `gnl.db`
**Download timeout**: Increase timeout in download script (default 300s)
**ffmpeg not found**: Install with `apt install ffmpeg` or `brew install ffmpeg`
**NovaAct errors**: Verify API key and Chrome profile path
**File upload fails**: Check `LOCAL_STORAGE_PATH` and security options




python formatPdfFromUdemy.py Dojo-Timed-Mode-Diagnostic-Test dojo
python formatPdfFromUdemy.py Dojo-Timed-Mode-Diagnostic-Test udemy

 python generate_ankycards.py Vladimir-Raykov-udemy-4 udemy 
python generate_ankycards.py Dojo-Timed-Mode-Diagnostic-Test dojo

 python GenerateCompactExamVersion.py Vladimir-Raykov-udemy-4 udemy
 python GenerateCompactExamVersion.py Dojo-Timed-Mode-Diagnostic-Test dojo

1. Open Anki
2. File → Import
3. Select the generated .txt file
4. Set:
   - Type: "Basique+"
   - Fields separated by: Tab
   - Allow HTML in fields: Yes
5. Import

python convert_and_combine_with_speed.py 'D:\DAILY_TASKS\JANVIER\test\wv'

python extract_keywords.py Vladimir-Raykov-udemy-4 
