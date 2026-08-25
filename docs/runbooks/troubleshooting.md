# Runbook — Troubleshooting

## Erreurs fréquentes

### `RPC rate limit (RESOURCE_EXHAUSTED)`

**Cause** : Trop de notebooks actifs ou trop de requêtes simultanées vers NotebookLM.

**Solution** :
1. Lister les notebooks : vérifier le nombre total
2. Supprimer les notebooks obsolètes (éditions terminées)
3. Vérifier qu'un seul process (dev OU prod) tourne, pas les deux en même temps

```python
from notebooklm_tools.mcp.tools._utils import get_client
client = get_client()
print(len(client.list_notebooks()))  # Si > 50, nettoyer
```

### `Audio media URL returned 404 while propagating`

**Cause** : L'audio n'est pas encore prêt côté Google. La lib fait des retries avec backoff.

**Solution** : Attendre. Si ça dure > 1h, le notebook est peut-être corrompu → supprimer et relancer.

### `Permission denied` lors de la génération PDF

**Cause** : Le fichier PDF est ouvert dans un lecteur (Acrobat, Edge, etc.)

**Solution** : Fermer le PDF et relancer.

### `TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'`

**Cause** : Une édition podcast n'a aucun épisode généré (`generated=NULL`).

**Solution** : Déjà fixé (fallback `or 0`). Si ça revient, vérifier la DB.

### LinkedIn MCP : `No valid LinkedIn session`

**Cause** : La session LinkedIn a expiré.

**Solution** :
```bash
cd ~/HomeWspce/linkedin-mcp-fork && .venv/bin/python -m linkedin_mcp_server --login
```

### LinkedIn MCP : `Tool timed out after 180s`

**Cause** : Timeout par défaut trop court pour le scraping.

**Solution** : Déjà augmenté à 600s dans `linkedin_mcp_server/config/schema.py`.

### Pas d'accès à l'app après reboot WSL

**Cause** : L'IP WSL a changé.

**Solution** :
```bash
hostname -I  # Nouvelle IP
# Accéder via http://<nouvelle-ip>:8001
```

### Schedule manqué ("Run time of job was missed")

**Cause** : Le serveur était arrêté à l'heure prévue. `misfire_grace_time=3600` rattrape dans l'heure.

**Impact** : Si le serveur était éteint > 1h après l'heure prévue, le job est perdu. Il sera exécuté au prochain cycle (lendemain).

### Classification Bedrock lente (What's New)

**Contexte** : 238 articles × 1 appel Bedrock chacun = ~5-6 minutes.

**Solution** : Normal. Pas de parallélisation possible sans risque de throttling.

### L'ancien compact markdown marquait les mauvaises réponses

**Cause** : L'ancien step4_compact comparait les débuts d'options (50 chars) — si deux options commencent pareil, mauvais matching.

**Solution** : step4_compact supprimé. step5_anki utilise le dict `answers` directement (plus de matching textuel).

## Commandes de diagnostic

```bash
# Logs du service prod
sudo journalctl -u gnl-process -f
sudo journalctl -u gnl-process --since "1 hour ago"

# Vérifier les process
ps aux | grep gnl
ps aux | grep uvicorn

# Vérifier les ports
ss -tlnp | grep -E "800[01]"

# DB état
python3 -c "
from gnl_core.db import get_db
with get_db() as conn:
    print('Parents:', conn.execute('SELECT count(*) FROM parent_configuration').fetchone()[0])
    print('Episodes:', conn.execute('SELECT count(*) FROM podcast_download').fetchone()[0])
    print('Articles:', conn.execute('SELECT count(*) FROM saved_articles').fetchone()[0])
    print('Crawl items:', conn.execute('SELECT count(*) FROM crawl_item').fetchone()[0])
"
```
