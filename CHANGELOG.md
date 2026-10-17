# Changelog

## v4.44.0 — 2026-10-17
- **Fix : le bouton Copier ré-inclut ton option** (« My answer(s) »). La régression venait du fix
  v4.40.0 : le verso effaçait le localStorage AVANT que le bouton Copier le lise → « not answered ».
  Désormais le nettoyage se fait uniquement au prochain affichage du recto (auto-reset), donc au verso
  le bouton Copier lit bien ton choix et le met dans le texte copié (PC et iPhone, via presse-papier).


## v4.43.0 — 2026-10-17
- **Paquet « Meta » (Phase 2 de révision)** : nouveau type de deck qui ne contient QUE les questions
  flaguées ROUGE dans Anki (ratées), en **affichage réponse direct** (recto = réponse, pas de révélation) :
  énoncé + options avec la/les correcte(s) en vert + bouton Copier. On ouvre, on tape Copier, on lance
  Meta AI — sans refaire la question. Distinct du « Deck reset » (2ᵉ passe interactive).
  - `step5_anki(answer_only=True)` ; `generate_meta_apkg` / `generate_meta_apkgs` (anki_review).
  - Endpoint `POST /api/anki-review/meta-apkg-one` + bouton « 📎 Paquet Meta » (picker examens finis).


## v4.42.0 — 2026-10-16
- **Fix cochage sur AnkiMobile (iPhone)** : taper une option coche désormais réellement la case.
  Le toggle passe par un handler onclick explicite sur la ligne (au lieu de label[for], que WebKit/iOS
  ne propage pas de façon fiable) ; un tap sur la case elle-même reste géré (stopPropagation anti double-toggle).


## v4.41.0 — 2026-10-16
- **Toute la ligne de l'option est cliquable** (recto des cartes d'examen) : taper n'importe où sur
  l'option coche/décoche sa case — grande cible tactile (padding + bordure), bien plus facile au gym
  que viser la petite case. Le `<label>` couvre toute la ligne.


## v4.40.0 — 2026-10-15
- **Fix fiable de l'affichage des réponses** (cartes d'examen), sans bouton Reset :
  - Recto : auto-reset du localStorage de la question au chargement → plus d'état « fantôme »
    (fini les options correctes cochées à tort venant d'une tentative précédente).
  - Verso : séparation nette — badge vert « ✓ Correct » sur les bonnes réponses (sans case cochée),
    badge rouge « ✗ ton choix » UNIQUEMENT sur ce que l'utilisateur a réellement coché. Plus de
    mélange checked/correct sur le même widget. Bouton Reset retiré.


## v4.39.0 — 2026-10-15
- **Cartes Anki AIB-C01** générées (45 questions, badges « Choisis N », bouton Copier avec explication).
- **Prompt du bouton Copier adapté au périmètre de l'examen** : ligne « Exam scope » injectée, dérivée
  par subtheme. Pour AIB-C01 (AI Business Strategist), le prompt cadre l'explication sur la STRATÉGIE
  business (valeur/KPI/ROI, gouvernance/responsible AI, transformation) plutôt que l'implémentation technique,
  conformément à l'exam guide officiel. Overridable via config META_EXAM_SCOPE.<subtheme>.


## v4.38.0 — 2026-10-15
- **Correction du slug** de l'examen AI Business Strategist : `ab1-c01` → **`aib-c01`** (code officiel).
- Migration DB v9 : renomme l'entrée catalogue existante `ab1-c01` → `aib-c01` (idempotent) ; dossier assets renommé.


## v4.37.0 — 2026-10-11
- **Bouton Reset masqué par défaut** sur les cartes d'examen : nouvelle variable `SHOW_RESET_BUTTON`
  (défaut `false`). Le mettre à `true` (env ou config) réaffiche le bouton. Le feedback couleur localStorage reste.
- **Prompt du bouton Copier adapté au certif** : le code d'examen dans le prompt Meta AI est désormais
  dérivé du subtheme (SAP-C02 / SAA-C03 / AB1-C01 / …) au lieu d'être figé sur SAP-C02 (cartes + deck vidéo).


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
