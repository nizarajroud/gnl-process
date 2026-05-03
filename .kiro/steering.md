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
- **Environment**: python-dotenv
- **PDF Processing**: PyPDF2, PyMuPDF (fitz)
- **Web Crawling**: requests, beautifulsoup4

## Architecture
- Two-table SQLite schema: `parent_configuration` (parent metadata) + `podcast_download` (individual file states)
- Scripts are invoked by n8n workflow nodes via Execute Command
- Nova Act drives Playwright Chromium for NotebookLM interactions (generation, download, cleanup)
- PDF splitting → DB insertion → generation → download → validation → conversion → combination
- Chrome profile at `/home/nizar/Clone-Chrome-profile/User Data` with persistent Google session

## Key Conventions
- All scripts use `python-fire` for CLI interface
- Environment config via `.env` file (never commit secrets)
- Database queries use JOIN between parent_configuration and podcast_download
- File naming: `p{n}.pdf` for page splits, `q{n}.pdf` for question splits
- Podcast naming: `{prefix}-{parent_name}` pattern
- States are integers: 0 = pending, 1 = done
- `gnl.db` is gitignored (local only, never tracked)
- Branch strategy: `main` + feature branches (no develop)
- DB queries must sort by numeric extraction: `ORDER BY CAST(REPLACE(...) AS INTEGER) ASC`
- Scripts auto-clean `SingletonLock` before launching Nova Act to prevent "profile in use" errors
- Audio generation prompts are externalized in `prompts/` directory (per-subfolder or default.txt)

## Workflow Pipeline
1. `split_pdf.py` → splits source PDF into chunks
2. `CollectAndSave.py` → inserts records into DB (loads .env from script directory)
3. `get_title_v2.py` → generates podcast names
4. `nllm-aws-asl-add-generate-gnl_v2.py` → uploads to NotebookLM + triggers audio generation
5. **Phase checkpoint** → Generate phase stops here. User verifies on NotebookLM UI.
6. `nllm-aws-asl-download-rename-gnl_v2.py` → downloads generated audio
7. `validate_states.py` → checks all states = 1
8. **Wait for Approval** → manual approval in n8n before convert
9. `batch_convert_to_mp3_v2.py` → converts m4a to mp3
10. `combine_mp3_v2.py` → concatenates mp3 files into final podcast

## Workflow Phases (2 independent phases + All)
- **Subscribe** (steps 1-3): split → save to DB → generate titles → STOP
- **Process & Deliver** (steps 4-10): generate → download → validate → approve → convert → combine
- **All Phases**: runs Subscribe then Process & Deliver end-to-end

## Entry Points (n8n)
- **MainForm**: Subscribe, Process & Deliver, or All Phases (file upload, split config, theme)
- **What's New Form**: Independent workflow for What's New reports
- **Emergency Stop**: `gnl-stop` alias kills all processes
- **Clean Database**: `gnl-clean` alias deletes all records

## Important Notes
- Nova Act uses a cloned Chrome profile with persistent Google session
- NotebookLM consumer version has no API — browser automation is required
- NotebookLM cannot access localhost URLs — file upload must use the hidden file input method via agentType
- Daily quota system limits generation to 20/day per configuration
- `generation_state` is updated immediately after audio generation starts (not at end of full process)
- n8n workflow JSON is stored in `GNL.json`
- The n8n workflow includes a "Wait for Approval" node between download and convert steps
- Nova Act free version has daily limits; AWS Service version requires Workflow construct ($4.75/agent hour)
- Google blocks Playwright MCP from authenticating (anti-bot detection) — must use Nova Act with Chrome profile
