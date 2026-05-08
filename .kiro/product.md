# GNL Process - Product Context

## What is GNL?
GNL (Google NotebookLM) Process is a personal automation system that converts PDF documents into podcast-style audio content using Google NotebookLM's Audio Overview feature.

## Use Cases
- Convert AWS What's New monthly reports into Arabic podcast episodes
- Split large PDFs into manageable chunks for individual podcast generation
- Produce multi-part podcast series from technical documentation

## User Workflow
1. User splits a PDF into parts and inserts records into DB
2. System generates podcast names (titles)
3. System creates NotebookLM notebooks, uploads PDFs, generates audio
4. System downloads completed audio files
5. System converts and combines into final podcast episode

## Constraints

### NotebookLM Quota (Google AI Pro)
- **20 audio overviews per day** (hard limit)
- A parent with >20 records requires multiple days to complete
- The orchestrator handles this automatically — re-run daily until complete

### Multi-Day Strategy
- Day 1: Generate up to 20 audios, download what's ready
- Day 2+: Generate remaining, download all pending
- Convert/combine only when ALL parts of a parent are downloaded
- No partial podcasts — either complete or wait

### Audio Characteristics
- Format: M4A (from NotebookLM), converted to MP3
- Duration: ~12 minutes per part (controlled by prompt)
- Language: Arabic (controlled by source PDF language)
- Generation time: 5-10 minutes per audio

### Naming Convention
- Notebook title = `podcast_name` in DB (used as lookup key)
- Pattern: `p{N}-{subtheme}` (e.g., `p1-whatsnew-mars`)
- Must be unique across all notebooks for reliable matching

### Reliability
- Generation is confirmed via status polling before marking DB
- Failed generations trigger automatic notebook cleanup
- Download uses polling with configurable timeout (45min default)
- Scripts are idempotent — safe to re-run without side effects

## Non-Goals
- Real-time podcast generation (batch processing only)
- Multi-user support (single Google account)
- Custom audio voices or music (NotebookLM default hosts)
