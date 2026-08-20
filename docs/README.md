# 🎙️ GNL Process — Documentation

## Table des matières

### Architecture (Diagrammes)
| Fichier | Format | Description |
|---------|--------|-------------|
| [pipeline-overview.d2](architecture/pipeline-overview.d2) | D2 | Vue macro de tous les pipelines |
| [exam-pipeline.d2](architecture/exam-pipeline.d2) | D2 | Pipeline examen (Anki + Podcast) |
| [podcast-pipeline.d2](architecture/podcast-pipeline.d2) | D2 | Pipeline podcast (split → audio) |
| [saved-articles.d2](architecture/saved-articles.d2) | D2 | Pipeline LinkedIn saved articles |
| [whatsnew-pipeline.d2](architecture/whatsnew-pipeline.d2) | D2 | Pipeline AWS What's New |
| [infrastructure.drawio](architecture/infrastructure.drawio) | Draw.io | Infra: WSL, services, ports, drives |
| [database-schema.drawio](data-flows/database-schema.drawio) | Draw.io | Schéma relationnel SQLite |
| [file-paths.d2](data-flows/file-paths.d2) | D2 | Chemins fichiers et dossiers |

### Runbooks
| Fichier | Description |
|---------|-------------|
| [deployment.md](runbooks/deployment.md) | Déploiement dev/prod, delivery, DB |
| [daily-operations.md](runbooks/daily-operations.md) | Scheduler, quota, opérations courantes |
| [troubleshooting.md](runbooks/troubleshooting.md) | Erreurs fréquentes et résolutions |
| [exam-workflow.md](runbooks/exam-workflow.md) | Workflow complet examen |

### Configuration
| Fichier | Description |
|---------|-------------|
| [settings-reference.md](config/settings-reference.md) | Toutes les clés gnl-config.json |

---

## Quick Start

```bash
pip install -e .
python setup_database.py
nlm login
gnl serve  # Dev sur port 8000
```

## Architecture résumée

```
PODCAST:     PDF → Split → NLM Generate → Download → Convert → Combine
EXAMS:       DOCX → Markdown → Highlight (Bedrock) → Anki (.apkg)
ARTICLES:    LinkedIn → Fetch (MCP) → Bedrock TTS → Combine
WHATS-NEW:   AWS API → Classify (Bedrock) → PDF par catégorie
```
