# GNL Process - Project Steering

## Project Overview
Automated workflow for processing content sources into NotebookLM podcasts with database tracking, audio processing, and n8n orchestration.

## Tech Stack
- **Language**: Python 3.13
- **Browser Automation**: Nova Act (Amazon)
- **Database**: SQLite (gnl.db)
- **Audio Processing**: ffmpeg, pydub
- **Orchestration**: n8n workflows
- **CLI Framework**: python-fire
- **Environment**: python-dotenv
- **PDF Processing**: PyPDF2, PyMuPDF (fitz)
- **Web Crawling**: requests, beautifulsoup4

## Architecture
- Two-table SQLite schema: `parent_configuration` (parent metadata) + `podcast_download` (individual file states)
- Scripts are invoked by n8n workflow nodes via Execute Command
- Nova Act drives Chrome browser for NotebookLM interactions (generation, download, cleanup)
- PDF splitting → DB insertion → generation → download → conversion → combination

## Key Conventions
- All scripts use `python-fire` for CLI interface
- Environment config via `.env` file (never commit secrets)
- Database queries use JOIN between parent_configuration and podcast_download
- File naming: `p{n}.pdf` for page splits, `q{n}.pdf` for question splits
- Podcast naming: `{prefix}-{parent_name}` pattern
- States are integers: 0 = pending, 1 = done
- `gnl.db` is gitignored (local only)
- Branch strategy: `main` + feature branches (no develop)

## Workflow Pipeline
1. `split_pdf.py` → splits source PDF into chunks
2. `CollectAndSave.py` → inserts records into DB
3. `nllm-aws-asl-add-generate-gnl_v2.py` → uploads to NotebookLM + triggers audio generation
4. `nllm-aws-asl-download-rename-gnl_v2.py` → downloads generated audio
5. `batch_convert_to_mp3_v2.py` → converts m4a to mp3
6. `combine_mp3_v2.py` → concatenates mp3 files into final podcast

## Important Notes
- Nova Act uses a cloned Chrome profile with persistent Google session
- NotebookLM consumer version has no API — browser automation is required
- Daily quota system limits generation to 20/day per configuration
- PDF parts must be sorted numerically (not lexicographically) in DB queries
- n8n workflow JSON is stored in `GNL.json`
