# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [v2.0.0] - 2026-05-09

### Added
- `gnl_core/` library (db, generate, download, convert, combine, clean, split, collect, titles)
- Unified CLI: `gnl serve`, `gnl status`, `gnl deliver`, `gnl prepare`, `gnl clean`
- FastAPI + HTMX web dashboard with real-time WebSocket updates
- Timeline progress bars (proportional, per-step)
- Quota tracking (20/day, reset at midnight PT, displayed in UI)
- APScheduler for daily auto-deliver
- TEST_MODE toggle (no API calls during development)
- Series catalog table with dropdown in form
- Stop button to abort running operations
- Auto-retry on generation failure (max 3 retries, #14)
- Combine removes partial files before writing full version
- DB schema versioning with migrations (v1→v2→v3)

### Changed
- Replaced Nova Act browser automation with `notebooklm_tools` Python library
- Replaced n8n workflow with standalone web app
- Download polls until all done (3h timeout + stale detection)
- Generation confirms via `studio_status` polling before marking DB
- Failed generations trigger automatic notebook cleanup

### Removed
- Nova Act scripts (`nllm-aws-asl-*.py`)
- Chrome/browser dependencies
- n8n workflow (`GNL.json`)
- `setup_chrome_user_data_dir.py`

## [v1.0.0] - 2025-11-14

### Added
- Initial version with Nova Act browser automation
- n8n workflow orchestration
- Chrome profile session management
- PDF splitting, title generation, audio download
- M4A→MP3 conversion and combination
