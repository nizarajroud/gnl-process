# Technology & Architecture

## System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   n8n        │────▶│ Python Scripts│────▶│  NotebookLM     │
│  Workflow    │     │  (CLI/fire)  │     │  (via Nova Act) │
│ localhost:5678│     └──────┬───────┘     └─────────────────┘
└─────────────┘            │
                    ┌──────▼───────┐
                    │   SQLite DB   │
                    │   (gnl.db)    │
                    └──────────────┘
```

## n8n Workflow Flow (GNL.json)

```
MainForm (Generate/All Phases) → Switch
  ├── Generate:    LocalStorage1 → split → CollectAndSave → titles → Generate Bulk → STOP
  └── All Phases:  LocalStorage1 → split → CollectAndSave → titles → Generate Bulk → Download → Validate → Wait → Convert → Combine

Deliver Form (Parent ID) → Download → Validate → Wait → Convert → Combine

What's New Form (independent) → Generate What's New Report

Emergency Stop (gnl-stop alias) → kills all processes
Clean Database (gnl-clean alias) → deletes all records
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

prompts/                # Audio generation prompts
├── default.txt         # Fallback prompt
└── {subfolder}.txt     # Per-subtheme prompt (e.g. aws-whats-new.txt)
```

## Key Dependencies
- `nova_act` — Browser automation for NotebookLM (v3.x+)
- `fire` — CLI argument parsing
- `PyPDF2` + `fitz` (PyMuPDF) — PDF splitting
- `ffmpeg` — Audio conversion (m4a→mp3) and concatenation
- `sqlite3` — Database (stdlib)
- `python-dotenv` — Environment configuration
- `requests` + `beautifulsoup4` — Web crawling

## Environment Variables
| Variable | Purpose |
|----------|---------|
| NOVA_ACT_API_KEY | Nova Act free version authentication |
| USER_DATA_DIR | Chrome profile path (/home/nizar/Clone-Chrome-profile/User Data) |
| HEADLESS | Browser visibility (0=visible, 1=headless) |
| GNL_BACKLOG | Final audio output path (Google Drive) |
| GNL_PROCESSING_PATH | Source documents path |
| PDF_PARTS_FOLDER | Split PDF output path |
| AUDIO_PARTS_FOLDER | Downloaded audio path |
| DEFAULT_SPEED | Audio playback speed multiplier |
| AWS_REGION | For Bedrock/Claude calls |
| MOEDL_INFERENCE_ID | Claude model ID for text generation |
| NOTION_API_KEY | Notion integration |
| NOTION_PAGE_ID | Notion target page |

## Known Limitations
- Nova Act free version has daily rate limits
- Only one Nova Act instance can use the Chrome profile at a time (SingletonLock)
- NotebookLM cannot access localhost URLs (cloud service)
- Google blocks Playwright/automated browsers from OAuth login
- File upload via hidden input (agentType) works but depends on NotebookLM UI stability
- generation_state may not update if script crashes after generation but before DB write (mitigated by updating immediately after audio generation starts)
