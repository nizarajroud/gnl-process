# GNL Process - Project Steering

## Project Overview
Automated workflow for processing content sources into NotebookLM podcasts with database tracking, audio processing, and n8n orchestration.

## Tech Stack
- **Language**: Python 3.13
- **NotebookLM Integration**: `notebooklm_tools` Python library (direct API, no browser)
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
- NotebookLM interactions via `notebooklm_tools` library (create notebook, upload PDF, generate audio, download)
- Auth managed by `nlm login` CLI (cached tokens, no browser needed at runtime)
- PDF splitting → DB insertion → title generation → podcast generation → download → conversion → combination

## Terminology
- **Édition**: A batch of episodes from one PDF (e.g., "whatsnew-mars-2026") = one parent_configuration
- **Épisode**: A single audio file generated from one PDF chunk
- **Série**: The overarching theme (e.g., "AWS What's New")

## Version Roadmap
- **v1.0** — Legacy (Nova Act + n8n + Chrome)
- **v2.0** — MVP: Web UI + MCP library + CLI (current prod)
- **v3.0** — Full Parameterized: Admin profile with all configuration via web UI (no .env editing)
- **v4.0** — Go to Cloud: Deploy on AWS, CI/CD via GitHub Actions, 24/7 availability

## Environments (Git Worktrees)
- **prod**: `/workspace/gnl-prod` — tag v2.0.0, port 8000
- **dev**: `/workspace/gnl-dev` — branch feat/v3-admin, port 8001
- **main repo**: `/workspace/gnl-process` — main branch (source of truth)
- Registry: `deployments.json` maps version → environment → path/port
- Each worktree has its own `gnl.db` (gitignored, independent)

## Cherry-pick to Production Procedure
1. Commit the specific fix on dev branch (only the relevant file(s))
2. Note the commit SHA
3. In `gnl-process` (main): `git cherry-pick <SHA>` → `git push`
4. Override tag: `git tag -d v2.0.0 && git push origin :refs/tags/v2.0.0 && git tag -a v2.0.0 -m "..." && git push origin v2.0.0`
5. Update prod worktree: `cd gnl-prod && git fetch origin && git checkout v2.0.0`

## Environments (Git Worktrees)
- **prod**: `/workspace/gnl-prod` — tag v2.0.0, port 8000 (`gnl serve --port 8000`)
- **dev**: `/workspace/gnl-dev` — branch feat/v3-admin, port 8001 (`gnl serve --port 8001`)
- **main repo**: `/workspace/gnl-process` — main branch (source of truth)
- Registry: `deployments.json` maps version → environment → path/port
- Each worktree has its own `gnl.db` (gitignored, independent)
- To apply a fix to both: commit on main, cherry-pick to dev (or vice versa)

## Key Conventions
- All scripts use `python-fire` for CLI interface
- Environment config via `.env` file (managed by Bitwarden, never committed — `.env.example` provided)
- Database queries use JOIN between parent_configuration and podcast_download
- File naming: `p{n}.pdf` for page splits, `q{n}.pdf` for question splits
- Podcast naming: `{prefix}-{parent_name}` pattern
- States are integers: 0 = pending, 1 = done
- `gnl.db` is gitignored (local only, never tracked)
- `.env` is gitignored (secrets managed via Bitwarden)
- Branch strategy: `main` (legacy) + `main-modernized` (MCP-based) + feature branches
- DB queries must sort by numeric extraction: `ORDER BY CAST(REPLACE(...) AS INTEGER) ASC`
- Audio generation prompts are externalized in `prompts/` directory (per-subfolder or default.txt)
- All n8n command parameters are double-quoted to handle apostrophes (e.g. "What's New")
- `generation_state` is updated only after `studio_status` confirms `in_progress` or `completed`
- `CollectAndSave.py` deduplicates: same parent_file + podcast_subtheme replaces existing records
- Scripts continue to next record on failure instead of stopping

## Workflow Pipeline
1. `split_pdf.py` → splits source PDF into chunks
2. `CollectAndSave.py` → inserts/replaces records into DB (deduplicates by parent_file + subtheme)
3. `get_title_v2.py` → generates podcast names
4. `generate_via_mcp.py` → creates notebook + uploads PDF + triggers audio generation (confirms via poll)
5. `download_via_mcp.py` → polls for completed audio + downloads (with configurable timeout)
6. `batch_convert_to_mp3_v2.py` → converts m4a to mp3
7. `combine_mp3_v2.py` → concatenates mp3 files into final podcast

## Orchestrator
- `generate_and_deliver.py` — unified script that chains: generate → download → convert → combine
- Modes: `--parent_id=N` (single parent) or `--all` (all active parents)
- Idempotent: reads DB state, only processes pending work
- Quota-aware: stops generation gracefully when daily limit reached, downloads what's ready
- Convert/combine only runs when ALL records of a parent are downloaded
- Safe to re-run daily via cron or n8n schedule

## n8n Entry Points
- **MainForm**: Main workflow (Type, Theme, Generation Mode) → split → generate → download → convert → combine
- **What's New Form**: Independent trigger for What's New reports (month + subtheme)
- **Download Form**: Manual download trigger with parent_id
- **Clean Form**: Delete notebooks (target: "all" or parent_id number)
- **Daily GNL Schedule**: Automatic daily trigger → `generate_and_deliver.py --all`

## Utility Scripts
- `clean_notebooks_mcp.py` — delete notebooks by parent_id or all
- `gnl_reset.sh` — kill processes + clean DB + delete all notebooks
- `validate_states.py` — check state consistency
- `delete_all_records.py` — wipe all DB tables

## CLI (gnl command)
Installed via `pip install -e .` — unified interface:
```bash
gnl status                    # show all parents with state
gnl generate --parent_id=1    # generate podcasts
gnl download --parent_id=1    # download audio
gnl convert --parent_id=1     # m4a → mp3
gnl combine --parent_id=1 --output=file.mp3
gnl deliver --parent_id=1     # full pipeline
gnl deliver --all             # all active parents
gnl clean --target=1 --confirm
```

## Important Notes
- NotebookLM quota: 20 audio overviews/day (Google AI Pro plan)
- Multi-day strategy: orchestrator handles partial generation across days automatically
- Auth via `nlm login` — tokens cached locally, no browser at runtime
- Download uses async streaming (`download_async`) for audio files
- Generation confirms status via polling before marking DB (prevents false positives)
- Failed generations trigger notebook cleanup (no orphan notebooks)
- `MCP_DOWNLOAD_TIMEOUT` env var controls download polling timeout (default 2700s = 45min)

## Workflow with User
1. **Plan first**: When asked to implement something, think step by step and propose a plan. Do NOT execute anything yet.
2. **Wait for confirmation**: Only execute the plan after the user explicitly confirms.
3. **No auto-commit/push**: After implementing, do NOT commit or push. Wait for the user to test and explicitly ask for commit/push.
4. **Never commit/push without clear user confirmation.**
5. **GitHub issue tracking**: When implementing a story from the GitHub backlog, update the issue status (close it or check off acceptance criteria) once done.
6. **No duplicate stories**: Before creating a new GitHub issue, check existing issues for duplicates. If the idea already exists, inform the user instead of creating a duplicate.

## Testing Requirements
Every story must include:
- **Unit tests**: Test each gnl_core module function in isolation (mocked dependencies)
- **Integration tests**: Test end-to-end flows with real DB (test fixture) and mocked NotebookLM API
- Framework: pytest
- Location: `tests/` directory (unit/ and integration/ subdirectories)
- Run: `pytest` before any merge to main

## Test Mode (Quota Protection)
- `TEST_MODE=1` in .env → no NotebookLM API calls, no quota consumed
- Generate: marks records as generated immediately (no notebook creation)
- Download: waits `TEST_GENERATION_DELAY` seconds then creates dummy .m4a files
- Use TEST_MODE for all UI/flow development. Only disable for real production runs.
- **Rule**: Never test with real API during development. Always use TEST_MODE=1.
