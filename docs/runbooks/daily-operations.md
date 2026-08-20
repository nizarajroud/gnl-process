# Runbook — Opérations quotidiennes

## Scheduler automatique

| Job | Heure | Action |
|-----|-------|--------|
| `saved_articles_fetch` | 02:00 | Scrape LinkedIn saved posts → DB |
| `saved_articles_generate` | 03:00 | Génère texte + audio pour articles non traités |
| `gnl_deliver` | 08:00 (désactivé) | Auto-deliver éditions podcast actives |

## Quota NotebookLM

- **20 audios/jour** (plan Google AI Pro)
- **Reset** : minuit UTC = **20:00 heure Montréal**
- Si rate limit (`RESOURCE_EXHAUSTED`) : attendre le reset ou réduire le nombre de notebooks

## Opérations manuelles

### Lancer un pipeline examen
1. Ouvrir le dashboard (port 8000/8001)
2. Tab "Exams" → sélectionner fichier
3. Choisir pipeline : Anki / Génération / Both
4. Cliquer "Traiter"

### Combiner des articles LinkedIn
1. Tab "Saved Articles"
2. Cliquer "🔗 Combiner"
3. Popup : sélectionner les MP3 à combiner
4. "All" pour tout sélectionner
5. Cliquer "Combiner" → fichier sur Google Drive

### Générer un What's New PDF
1. Tab "Génération" → sous-thème "aws-whats-new"
2. Cocher les mois (ou Q1/Q2/Q3/Q4)
3. Choisir catégorie (ou "Toutes")
4. "Générer PDF"

## Nettoyage notebooks NLM

Les notebooks s'accumulent (1 par épisode podcast). Nettoyer périodiquement :

```python
from notebooklm_tools.mcp.tools._utils import get_client
client = get_client()
notebooks = client.list_notebooks()
# Supprimer ceux dont le podcast est terminé
for nb in notebooks:
    if 'whatsnew' in nb.title or 'old-edition' in nb.title:
        client.delete_notebook(nb.id)
```

## Vérifier l'état des éditions

```bash
gnl status  # Affiche toutes les éditions et leur progression
```

## Interruption d'un process

- **Bouton Stop** : arrête entre les épisodes (pas pendant un épisode en cours)
- **Ctrl+C** sur `gnl serve` : arrêt immédiat
- **`./gnl-prod.sh stop`** : arrête le service prod
