# Product Context

## Purpose
Automate the end-to-end process of creating educational podcasts from PDF documents using Google NotebookLM's AI audio generation, with full lifecycle management (split, generate, download, convert, combine).

## Target Users
- Single user (personal learning tool)
- Content: AWS certifications, technical documentation, "What's New" digests

## Core Use Cases
1. **Bulk PDF Processing**: Split large PDFs (exam prep, documentation) into chunks, generate individual podcasts, then combine into a single audio file
2. **Web Content Podcasts**: Convert web articles and YouTube videos into audio podcasts via NotebookLM
3. **What's New Digests**: Crawl AWS What's New pages, aggregate monthly content, generate podcast episodes
4. **Exam Preparation**: Generate Anki flashcards and audio content from certification materials

## Content Sources
- Local PDF files (exam dumps, documentation)
- Web URLs (AWS blogs, What's New)
- YouTube videos
- Google Drive documents

## Output
- MP3 podcast files organized by theme/subtheme
- Stored in Google Drive (`GNL-BACKLOG` folder)
- Organized as: `{theme}/{subtheme}/{podcast-name}.mp3`

## Constraints
- NotebookLM has no public API (consumer version) — requires browser automation
- Daily generation quota: ~20 podcasts per day (Google's implicit limit)
- Audio generation takes ~5-10 minutes per podcast
- Chrome profile must maintain Google session
