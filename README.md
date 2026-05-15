# 🎙️ GNL Process

Automated podcast pipeline that converts PDF documents into audio podcasts using Google NotebookLM.

## Features

- **Web Dashboard** — FastAPI + HTMX with real-time progress tracking
- **One-click pipeline** — Upload PDF → Split → Generate → Download → Convert → Combine
- **Quota management** — 20 audio/day tracking with multi-day auto-resume
- **Semantic chunking** — AI-powered PDF splitting via Amazon Bedrock (Claude)
- **Auto-retry** — Failed generations automatically retry (max 3 attempts)
- **Scheduler** — Daily auto-deliver at configurable time
- **Configuration UI** — All settings editable via web interface (no .env editing)
- **Export/Import** — Backup and restore configuration as JSON

## Quick Start

```bash
# Install
pip install -e .

# Initialize database
python setup_database.py

# Authenticate with NotebookLM
nlm login

# Start the web UI
gnl serve
```

Open `http://<your-ip>:8000` in your browser.

## CLI Commands

```bash
gnl serve                          # Start web dashboard
gnl status                         # Show all editions
gnl prepare --pdf=file.pdf --pages=3 --name=edition --theme=aws --subtheme=aws-whats-new
gnl prepare --pdf=file.pdf --mode=semantic --name=edition --theme=aws --subtheme=aws-papers
gnl deliver --parent_id=1          # Full pipeline for one edition
gnl deliver --all                  # All active editions
gnl clean --target=1 --confirm     # Delete an edition
```

## Web UI Tabs

| Tab | Description |
|-----|-------------|
| 📻 Production | Active editions with timeline, actions, logs |
| 📜 Historique | Completed and deleted editions |
| ⚙️ Configuration | Settings, prompts, catalog management |
| 📋 Changelog | Version history |

## Pipeline Steps

```
PDF → Split (pages or semantic) → Generate (NotebookLM) → Download → Convert (MP3) → Combine → Cloud
```

Each step is tracked in the timeline:
- **Préparé** — PDF split into episodes
- **Généré** — Audio generation launched on NotebookLM
- **Téléchargé** — Audio files downloaded
- **Converti** — M4A converted to MP3
- **Combiné** — All episodes merged into final file

## Configuration

All settings in `gnl-config.json` (editable via web UI):

| Key | Description | Default |
|-----|-------------|---------|
| AUDIO_PARTS_FOLDER | Downloaded audio storage | required |
| GNL_BACKLOG | Final output folder (cloud) | required |
| PDF_PARTS_FOLDER | Split PDF storage | required |
| NOTEBOOKLM_LANGUAGE | Audio language (BCP-47) | ar-EG |
| DEFAULT_SPEED | Playback speed multiplier | 1.37 |
| MCP_DOWNLOAD_TIMEOUT | Download polling timeout (s) | 10800 |
| MAX_GENERATION_RETRIES | Max retry on failure | 3 |
| GNL_SCHEDULE_TIME | Daily auto-deliver time | 08:00 |
| BEDROCK_MODEL_ID | Model for semantic chunking | us.anthropic.claude-sonnet-4-20250514-v1:0 |

## Prerequisites

- Python 3.11+
- `notebooklm_tools` (NotebookLM MCP library)
- `ffmpeg` (audio conversion)
- AWS credentials (for Bedrock semantic chunking)
- Google account with NotebookLM access (Google AI Pro for 20 audio/day)

## Project Structure

```
gnl_core/
├── __init__.py
├── cli.py          # Click CLI
├── config.py       # JSON config management
├── db.py           # SQLite access layer
├── split.py        # PDF splitting (pages + semantic)
├── collect.py      # DB insertion
├── titles.py       # Podcast name generation
├── generate.py     # NotebookLM audio generation
├── download.py     # Audio download with polling
├── convert.py      # M4A → MP3
├── combine.py      # MP3 concatenation
├── clean.py        # Notebook cleanup
└── web/
    ├── app.py      # FastAPI application
    └── templates/
        └── dashboard.html
```

## Versions

- **v1.0** — Nova Act + Chrome + n8n (legacy)
- **v2.0** — MCP library + CLI + Web UI (MVP)
- **v3.0** — Full parameterized + semantic chunking + admin UI (current)
- **v4.0** — Cloud deployment on AWS (planned)

## License

Private project.
