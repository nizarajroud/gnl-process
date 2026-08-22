# Runbook — Déploiement

## Environnements

| Env | Port | Chemin | Service |
|-----|------|--------|---------|
| Dev | 8000 | `/home/nizar/workspace/gnl-process/` | Manuel (`gnl serve`) |
| Prod | 8001 | `/home/nizar/.gnl-process-prod/` | systemd (`gnl-process.service`) |

**DB partagée** : les deux environnements utilisent le même `gnl.db`.

## Commandes rapides

```bash
# Dev
cd ~/workspace/gnl-process && gnl serve

# Prod (via script)
./gnl-prod.sh start
./gnl-prod.sh stop
./gnl-prod.sh status
```

## Déploiement vers prod

```bash
# Depuis le repo dev
./delivery.sh
```

Le script `delivery.sh` :
1. Copie le code vers `/home/nizar/.gnl-process-prod/`
2. Installe les dépendances dans le venv prod
3. Redémarre le service systemd

## Service systemd

Fichier : `/etc/systemd/system/gnl-process.service`

```bash
sudo systemctl status gnl-process
sudo systemctl start gnl-process
sudo systemctl stop gnl-process
sudo systemctl restart gnl-process
sudo journalctl -u gnl-process -f  # Logs live
```

## Après un reboot WSL

- L'IP WSL change → noter la nouvelle IP (`hostname -I`)
- Le service prod démarre automatiquement (enabled)
- Accéder via `http://<nouvelle-ip>:8001`
- Si besoin port forwarding Windows :
  ```powershell
  netsh interface portproxy add v4tov4 listenport=8001 listenaddress=0.0.0.0 connectport=8001 connectaddress=<ip-wsl>
  ```

## Google Drive (G:)

Monté automatiquement au démarrage du serveur :
```bash
sudo mount -t drvfs G: /mnt/g
```
Si le mount échoue, le serveur fonctionne quand même mais le COMBINE ne peut pas écrire sur le Drive.
