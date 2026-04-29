# Technology & Architecture

## System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   n8n        │────▶│ Python Scripts│────▶│  NotebookLM     │
│  Workflow    │     │  (CLI/fire)  │     │  (via Nova Act) │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐
                    │   SQLite DB   │
                    │   (gnl.db)    │
                    └──────────────┘
```

## Database Schema

### parent_configuration
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| parent_file | TEXT | Original file name |
| source_path | TEXT | Directory path |
| source_type | TEXT | GoogleDrive/WebAndYoutube/LocalStorage |
| podcast_theme | TEXT | Top-level category (AWS, AIP) |
| podcast_subtheme | TEXT | Sub-category (exam, nllm-disc, aws-data) |
| split_configuration | TEXT | e.g. "14ck-3p" (14 chunks, 3 pages each) |
| generation_mode | TEXT | single/bulk |
| combination_state | INTEGER | 0=pending, 1=done |
| daily_quota_remaining | INTEGER | Remaining daily quota |
| quota_date | TEXT | Date of last quota reset |

### podcast_download
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| parent_configuration_id | INTEGER FK | Links to parent |
| source_id | TEXT | Filename (p1.pdf, q3.pdf) |
| podcast_name | TEXT | Generated podcast name |
| generation_state | INTEGER | 0=pending, 1=done |
| download_state | INTEGER | 0=pending, 1=done |
| conversion_state | INTEGER | 0=pending, 1=done |
| date | TEXT | Processing date |

### crawl_source / crawl_item
Used for web crawling (What's New pages). Tracks URLs, post dates, and processing state.

## File Organization

```
GNL-PROCESS/
├── Main-docs/          # Source PDFs
├── PDF-Parts/          # Split PDF chunks
│   └── {subtheme}/
│       └── {name}/     # p1.pdf, p2.pdf, ...
└── Audio-Parts/        # Downloaded audio before combination

GNL-BACKLOG/ (Google Drive)
├── {theme}/
│   └── {subtheme}/
│       ├── podcast1.mp3
│       └── combined-output.mp3
```

## Key Dependencies
- `nova_act` — Browser automation for NotebookLM
- `fire` — CLI argument parsing
- `PyPDF2` + `fitz` (PyMuPDF) — PDF splitting
- `ffmpeg` — Audio conversion (m4a→mp3) and concatenation
- `sqlite3` — Database (stdlib)
- `python-dotenv` — Environment configuration
- `requests` + `beautifulsoup4` — Web crawling

## Environment Variables
| Variable | Purpose |
|----------|---------|
| NOVA_ACT_API_KEY | Nova Act authentication |
| USER_DATA_DIR | Chrome profile path |
| HEADLESS | Browser visibility (0/1) |
| GNL_BACKLOG | Final audio output path (Google Drive) |
| GNL_PROCESSING_PATH | Source documents path |
| PDF_PARTS_FOLDER | Split PDF output path |
| AUDIO_PARTS_FOLDER | Downloaded audio path |
| AWS_REGION | For Bedrock/Claude calls |
| MOEDL_INFERENCE_ID | Claude model ID for text generation |
| NOTION_PAGE_ID | Notion integration target |
