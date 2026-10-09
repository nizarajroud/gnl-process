# Changelog

## v4.36.0 — 2026-10-09
- **Tests à blanc (health-check dry-run) désactivés par défaut** : plus de notifications Telegram
  automatiques à 18h/5h30. Le défaut code passe à `enabled=False` (opt-in via SCHEDULER.health_check.enabled=true).


## v4.35.0 — 2026-10-09
- Nouvel examen **AB1-C01** (AWS Certified AI Business Strategist, beta) ajouté à GNL.
- Migration DB v8 : entrée catalogue `('exams','ab1-c01')` (fresh-install + upgrade idempotent).
- Arborescence `exams/ab1-c01/assets/...` créée (identique à saa-c03).


## v4.34.0 — 2026-10-09
- **Revert** de la fonction « Copier vers fichier partagé » (v4.32.0) : le bouton Copier redevient
  **presse-papier classique uniquement**, sur les cartes d'examen ET les decks vidéo.
- Retiré : endpoint `/api/share`, middleware CORS, `SHARE_URL`/`SHARE_FILE`, et le `fetch` vers le serveur local.
- Conservé : prompt voice, explication embarquée, badges « Choisis N », examen SAA-C03, migration DB v7.


## v4.33.0 — 2026-10-09
- Nouvel examen **SAA-C03** (AWS Solutions Architect Associate) ajouté à GNL.
- `build_slider_deck.py` généralisé : nouvel argument `--subtheme=<slug>` (défaut `sap-c02`) pour
  générer des decks vidéo de n'importe quel examen (BASE + markdown dérivés du subtheme).
- Migration DB v7 : entrée catalogue `('exams','saa-c03')` (fresh-install + upgrade idempotent).
- Arborescence `exams/saa-c03/assets/...` créée (full-markdown, Anki-generation, video-assets, etc.).


## v4.32.0 — 2026-10-07
- Anki « Copier » (cartes classiques + deck vidéo slider) écrit maintenant aussi le fichier iCloud SHARE.txt
  via un nouvel endpoint local GNL `POST /api/share` (Anki Desktop). Le bouton copie dans le presse-papier
  ET envoie la question courante au fichier `META-AI/SHARE.txt` (écrasé à chaque copie), synchronisé par iCloud.
- CORS activé pour permettre le fetch cross-origin depuis la webview Anki.
- Chemin configurable via `SHARE_FILE`; URL configurable via `SHARE_URL` (défaut http://127.0.0.1:8000/api/share).

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
