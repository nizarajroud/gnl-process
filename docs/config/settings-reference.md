# Configuration Reference — gnl-config.json

Toutes les clés de configuration avec description, valeur par défaut et impact.

## Général

| Clé | Défaut | Description |
|-----|--------|-------------|
| `INBOX_FOLDER` | (requis) | Dossier principal des fichiers source (PDFs, markdown, exams) |
| `AUDIO_PARTS_FOLDER` | (requis) | Stockage des MP3 individuels (par épisode/article) |
| `PDF_PARTS_FOLDER` | (requis) | Stockage des chunks PDF découpés |
| `GNL_BACKLOG` | (requis) | Dossier final (Google Drive) pour les fichiers combinés |
| `TEST_MODE` | `0` | Mode test (désactive les appels réels NLM) |

## Podcast / NotebookLM

| Clé | Défaut | Description |
|-----|--------|-------------|
| `NOTEBOOKLM_LANGUAGE` | `ar-EG` | Langue audio BCP-47 pour NotebookLM |
| `DEFAULT_SPEED` | `1.37` | Multiplicateur de vitesse (ffmpeg atempo) |
| `MCP_DOWNLOAD_TIMEOUT` | `10800` | Timeout polling download (secondes, 3h) |
| `MAX_GENERATION_RETRIES` | `3` | Retries max sur échec génération |
| `NLM_QUOTA_RESET_LOCAL` | `20:00` | Heure locale (Montréal) du reset quota NLM (20 audios/jour) |
| `CONFIRM_POLL_INTERVAL` | `10` | Intervalle polling confirmation (secondes) |
| `CONFIRM_TIMEOUT` | `300` | Timeout confirmation (secondes) |
| `DELIVER_TIMEOUT` | `48` | Timeout total deliver (heures) |
| `DELIVER_RETRY_DELAY` | `180` | Délai entre retries deliver (secondes) |
| `TEST_GENERATION_DELAY` | `5` | Délai simulé en mode test (secondes) |

## Examen

| Clé | Défaut | Description |
|-----|--------|-------------|
| `EXAM_USE_NLM` | `0` | `1` = NLM en premier (markdown), `0` = Bedrock uniquement (DOCX) |
| `EXAM_NLM_BATCH_SIZE` | `15` | Questions par batch pour NotebookLM |
| `EXAM_BATCH_SIZE` | `5` | Questions par batch pour Bedrock |
| `EXAM_PARALLEL_BATCHES` | `3` | Nombre de batches Bedrock en parallèle |
| `EXAM_GENERATE_DIAGRAMS` | `1` | `1` = générer diagrammes draw.io par question |
| `EXAM_DIAGRAM_PLACEMENT` | `front` | Placement par défaut (overridé par UI checkboxes) |
| `DEBUG_NLM` | `0` | `1` = logs détaillés NLM (raw response, bold items, parsed) |
| `ANKI_FONT_SIZE` | `16` | Taille police dans les cartes Anki |

## Saved Articles (LinkedIn)

| Clé | Défaut | Description |
|-----|--------|-------------|
| `LINKEDIN_MCP_PATH` | `/home/nizar/HomeWspce/linkedin-mcp-fork` | Chemin du serveur MCP LinkedIn |
| `LINKEDIN_SCRAPE_COUNT` | `50` | Nombre de posts à scraper par fetch |
| `LINKEDIN_BATCH_SIZE` | `5` | Articles par batch de génération |
| `TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Modèle TTS pour les articles |
| `TTS_VOICE` | `Orus` | Voix TTS |
| `TTS_DELAY_SECONDS` | `15` | Délai entre appels TTS (rate limiting) |

## What's New

| Clé | Défaut | Description |
|-----|--------|-------------|
| `WHATSNEW_CATEGORIES` | (liste) | Catégories AWS par ordre de priorité dans le PDF |

## Bedrock

| Clé | Défaut | Description |
|-----|--------|-------------|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Modèle Claude pour classification/highlight |
| `BEDROCK_MAX_TOKENS` | `4096` | Max tokens par réponse |
| `AWS_PROFILE` | `csna-operations-sso-828` | Profil AWS CLI |
| `AWS_REGION` | `ca-central-1` | Région AWS par défaut |

## Scheduler

| Clé | Description |
|-----|-------------|
| `SCHEDULER.gnl_deliver.enabled` | Active/désactive l'auto-deliver |
| `SCHEDULER.gnl_deliver.time` | Heure d'exécution (ex: `08:00`) |
| `SCHEDULER.saved_articles_fetch.enabled` | Active/désactive le fetch LinkedIn |
| `SCHEDULER.saved_articles_fetch.time` | Heure du fetch (ex: `02:00`) |
| `SCHEDULER.saved_articles_generate.enabled` | Active/désactive la génération batch |
| `SCHEDULER.saved_articles_generate.time` | Heure de génération (ex: `03:00`) |

## Notes

- Dev et prod partagent la **même base de données** (`gnl.db`)
- Le scheduler utilise `misfire_grace_time=3600` (1h) — les jobs manqués sont rattrapés dans l'heure
- `NLM_QUOTA_RESET_LOCAL=20:00` signifie minuit UTC = 20h Montréal (EDT)
