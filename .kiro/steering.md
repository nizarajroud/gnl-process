# GNL Process - Project Steering

## Project Overview
Automated workflow for processing content sources into NotebookLM podcasts with database tracking, audio processing, and n8n orchestration.

## Tech Stack
- **Language**: Python 3.13
- **Browser Automation**: Nova Act (Amazon) — free version with API key
- **Database**: SQLite (gnl.db)
- **Audio Processing**: ffmpeg, pydub
- **Orchestration**: n8n workflows (localhost:5678 on WSL)
- **CLI Framework**: python-fire
- **Environment**: python-dotenv, managed via Bitwarden
- **PDF Processing**: PyPDF2, PyMuPDF (fitz)
- **Web Crawling**: requests, beautifulsoup4

## Architecture
- Two-table SQLite schema: `parent_configuration` (parent metadata) + `podcast_download` (individual file states)
- Scripts are invoked by n8n workflow nodes via Execute Command
- Nova Act drives Playwright Chromium for NotebookLM interactions (generation, download, cleanup)
- Chrome profile at `/home/nizar/Clone-Chrome-profile/User Data` with persistent Google session
- PDF splitting → DB insertion → title generation → podcast generation → download → validation → conversion → combination

## Key Conventions
- All scripts use `python-fire` for CLI interface
- Environment config via `.env` file (managed by Bitwarden, never committed — `.env.example` provided)
- Database queries use JOIN between parent_configuration and podcast_download
- File naming: `p{n}.pdf` for page splits, `q{n}.pdf` for question splits
- Podcast naming: `{prefix}-{parent_name}` pattern
- States are integers: 0 = pending, 1 = done
- `gnl.db` is gitignored (local only, never tracked)
- `.env` is gitignored (secrets managed via Bitwarden)
- Branch strategy: `main` + feature branches (no develop)
- DB queries must sort by numeric extraction: `ORDER BY CAST(REPLACE(...) AS INTEGER) ASC`
- Scripts auto-clean `SingletonLock` before launching Nova Act to prevent "profile in use" errors
- Audio generation prompts are externalized in `prompts/` directory (per-subfolder or default.txt)
- All n8n command parameters are double-quoted to handle apostrophes (e.g. "What's New")
- `generation_state` is updated immediately after audio generation starts (not at end of process)
- `CollectAndSave.py` deduplicates: same parent_file + podcast_subtheme replaces existing records
- `process_all_records_for_generation.py` continues to next record on failure instead of stopping

## Workflow Pipeline
1. `split_pdf.py` → splits source PDF into chunks
2. `CollectAndSave.py` → inserts/replaces records into DB (deduplicates by parent_file + subtheme)
3. `get_title_v2.py` → generates podcast names
4. `nllm-aws-asl-add-generate-gnl_v2.py` → uploads to NotebookLM + triggers audio generation
5. `nllm-aws-asl-download-rename-gnl_v2.py` → downloads generated audio
6. `validate_states.py` → checks all generation_state and download_state = 1
7. **Wait for Approval** → manual approval in n8n before convert
8. `batch_convert_to_mp3_v2.py` → converts m4a to mp3
9. `combine_mp3_v2.py` → concatenates mp3 files into final podcast

## n8n Entry Points
- **MainForm**: Main workflow (Type, Theme, Generation Mode) → split → generate → download → convert → combine
- **What's New Form**: Independent trigger for What's New reports (month + subtheme)

## Shell Aliases (in .zshrc)
- `gnl-stop` — kills all GNL processes (Chrome clone, scripts, Nova Act) + removes SingletonLock
- `gnl-clean` — deletes all records from all DB tables

## Important Notes
- Nova Act uses a cloned Chrome profile with persistent Google session
- NotebookLM consumer version has no API — browser automation is required
- NotebookLM cannot access localhost URLs — file upload must use the hidden file input method via agentType
- Daily quota system limits generation to 20/day per configuration
- Google blocks Playwright MCP from authenticating (anti-bot detection) — must use Nova Act with Chrome profile
- Nova Act free version has daily limits; AWS Service version requires Workflow construct ($4.75/agent hour)
- WSL memory constraints (~16GB RAM) can cause Chrome crashes — kill unused processes before generation
- n8n workflow JSON (`GNL.json`) must be reimported after changes; Python script changes take effect immediately
