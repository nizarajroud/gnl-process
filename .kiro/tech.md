# GNL Process - Technology & Architecture

## System Architecture

```
n8n (localhost:5678)
  ├── MainForm → split → CollectAndSave → get_title → generate_and_deliver.py
  ├── Download Form → download_via_mcp.py
  ├── Clean Form → clean_notebooks_mcp.py
  ├── Daily Schedule → generate_and_deliver.py --all
  └── What's New Form → whats_new_report.py

generate_and_deliver.py (orchestrator)
  ├── generate_via_mcp.py (create notebook + upload + generate audio)
  ├── download_via_mcp.py (poll + download completed audio)
  ├── batch_convert_to_mp3_v2.py (m4a → mp3)
  └── combine_mp3_v2.py (concatenate all mp3s)
```

## NotebookLM Integration (MCP Library)

### Library: `notebooklm_tools`
- Installed at: `/home/nizar/.local/lib/python3.13/site-packages/notebooklm_tools/`
- CLI: `notebooklm-mcp` (MCP server) and `nlm` (auth CLI)
- Auth: `nlm login` → cached tokens at `~/.notebooklm-mcp/`

### Key Services Used
```python
from notebooklm_tools.mcp.tools._utils import get_client
from notebooklm_tools.services.notebooks import create_notebook, list_notebooks, delete_notebook
from notebooklm_tools.services.sources import add_source
from notebooklm_tools.services.studio import create_artifact, get_studio_status
from notebooklm_tools.services.downloads import download_async
```

### API Patterns
- `create_notebook(client, title=...)` → returns `{notebook_id: ...}`
- `add_source(client, notebook_id, source_type="file", file_path=..., wait=True)` → uploads local PDF
- `create_artifact(client, notebook_id, artifact_type="audio", focus_prompt=...)` → starts generation
- `get_studio_status(client, notebook_id)` → returns artifacts with status and URLs
- `download_async(client, notebook_id, "audio", output_path)` → downloads audio file (requires asyncio.run)
- `delete_notebook(client, notebook_id)` → permanent deletion

### Important Notes
- Audio download requires `download_async()` (not `download_sync()`)
- Audio URLs require Google auth (cannot download with plain requests)
- `get_studio_status` returns artifact status: `in_progress` or `completed`
- Generation confirmation: poll `get_studio_status` until `in_progress` before marking DB

## Database Schema

### parent_configuration
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| source_type | TEXT | LocalStorage, WebAndYoutube |
| generation_mode | TEXT | bulk, single |
| podcast_theme | TEXT | aws, azure, etc. |
| podcast_subtheme | TEXT | whatsnew-mars, etc. |
| parent_file | TEXT | Source filename |
| source_path | TEXT | Full path to source directory |

### podcast_download
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| parent_configuration_id | INTEGER FK | References parent_configuration |
| source_id | TEXT | p1.pdf, p2.pdf, etc. |
| podcast_name | TEXT | Notebook title in NotebookLM |
| generation_state | INTEGER | 0=pending, 1=done |
| download_state | INTEGER | 0=pending, 1=done |
| conversion_state | INTEGER | 0=pending, 1=done |
| date | TEXT | Date of generation |

## Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| AUDIO_PARTS_FOLDER | Output directory for downloaded audio | required |
| GNL_BACKLOG | Google Drive backlog folder | required |
| MCP_DOWNLOAD_TIMEOUT | Download polling timeout (seconds) | 2700 |
| TRACING | Enable tracing logs | 0 |

## File Flow
```
Source PDF → split_pdf.py → p1.pdf, p2.pdf, ...
  → CollectAndSave.py → DB records
  → get_title_v2.py → podcast_name in DB
  → generate_via_mcp.py → NotebookLM notebooks with audio
  → download_via_mcp.py → Audio-Parts/{subtheme}/{parent_file}/{name}.m4a
  → batch_convert_to_mp3_v2.py → .mp3 files
  → combine_mp3_v2.py → final combined podcast
```

## Learnings & Constraints
- Google auth cannot be automated with Playwright/Puppeteer (anti-bot detection)
- `nlm login` handles auth via headless Chrome with saved profile
- NotebookLM audio generation takes 5-10 minutes per file
- Daily quota: 20 audio overviews (Google AI Pro plan)
- Audio files are .m4a (MP4 container) from NotebookLM
- Notebook titles must be unique for lookup (podcast_name used as key)
