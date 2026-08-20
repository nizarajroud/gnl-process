# Runbook — Workflow Examen

## Vue d'ensemble

```
DOCX (Tutorials Dojo) → FORMAT → MARKDOWN → [ANKI branch] + [GÉNÉRATION branch]
```

## Prérequis

- Fichier `.docx` dans `assets/exams/{subtheme}/origin/`
- AWS credentials configurées (pour Bedrock)
- Si `EXAM_USE_NLM=1` : session NotebookLM active (`nlm login`)

## Étapes

### 1. Upload du fichier source
Placer le `.docx` dans :
```
INBOX_FOLDER/exams/{subtheme}/origin/{nom}.docx
```

### 2. Lancer le pipeline
- Dashboard → Tab Exams → Sélectionner le fichier
- Choisir : **Anki** / **Génération** / **Both**
- Cliquer "Traiter"

### 3. Tronc commun (automatique)
1. **FORMAT** : Copie + formate le DOCX → `pdf-formatting/word/{nom}.docx`
2. **MARKDOWN** : Convertit DOCX → `pdf-formatting/full-markdown/{nom}.md`

### 4a. Branche Anki
1. **HIGHLIGHT** : Identifie les réponses correctes
   - Mode Bedrock (défaut) : lit le DOCX, batch de 5 questions, 3 parallèles
   - Mode NLM (`EXAM_USE_NLM=1`) : query le markdown dans NotebookLM
   - Fallback : Bedrock → Regex
2. **ANKI** : Génère depuis le dict `answers` :
   - `.apkg` → `Anki-generation/anki/{nom}.apkg`
   - Compact `.md` → `Anki-generation/markdown/{nom}.md`
   - Cartes avec checkboxes interactives (front) + réponses cochées en vert (back)

### 4b. Branche Génération (podcast)
1. **SPLIT** : Découpe le `.md` en chunks de N questions
2. **DB INSERT** : Crée parent + épisodes dans la DB
3. **GENERATE** : Lance la génération NLM (comme un podcast normal)

## Résultat

| Artefact | Chemin |
|----------|--------|
| Full markdown | `assets/exams/{sub}/pdf-formatting/full-markdown/{nom}.md` |
| Anki package | `assets/exams/{sub}/Anki-generation/anki/{nom}.apkg` |
| Compact markdown | `assets/exams/{sub}/Anki-generation/markdown/{nom}.md` |
| Podcast audio | `GNL-BACKLOG/exams/{sub}/{nom}.mp3` |

## Prompt podcast

Fichier : `prompts/exams-default.txt`

Structure en 4 étapes :
1. Context & Architecture
2. Requirements Analysis
3. Options Analysis
4. Conclusion + Summary

Variante archivée : `prompts/exams-2phases.txt` (quiz sans réponse puis explication).

## Configuration spécifique

```json
{
  "EXAM_USE_NLM": "0",          // 0=Bedrock, 1=NLM+fallback
  "EXAM_BATCH_SIZE": "5",       // Questions par batch Bedrock
  "EXAM_NLM_BATCH_SIZE": "15",  // Questions par batch NLM
  "EXAM_PARALLEL_BATCHES": "3", // Batches Bedrock en parallèle
  "DEBUG_NLM": "0",             // 1=logs détaillés
  "ANKI_FONT_SIZE": "16"        // Taille police cartes
}
```

## Nettoyage

Le bouton "Clean" dans l'UI supprime :
- Le dossier `full-markdown/`
- Le notebook NLM (`{nom}-FULL`)
- Les fichiers Anki générés
