#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Charger .env
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^$' | xargs)
fi

DEV_DIR="$SCRIPT_DIR"
PROD_DIR="${PROD_DIR:-/home/nizar/.gnl-process-prod}"
REPO_URL="${APP_REPO_URL:-https://github.com/nizarajroud/gnl-process.git}"
SERVICE_NAME="${SERVICE_NAME:-gnl-process}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROD_PORT="${PROD_PORT:-8000}"

# === Menu ===
CHOICE=$(echo -e "Créer un tag\nDéployer une version" | fzf --prompt="GNL Delivery > " --height=5 --reverse)

case "$CHOICE" in

# ============================================================
# OPTION 1: Créer un tag (depuis le dossier dev, sur main)
# ============================================================
"Créer un tag")
  cd "$DEV_DIR"
  git checkout main --quiet
  git pull --rebase origin main --quiet

  # Lire version actuelle et incrémenter
  CURRENT=$(cat VERSION | tr -d '[:space:]')
  MAJOR=$(echo "$CURRENT" | sed 's/v\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\)/\1/')
  MINOR=$(echo "$CURRENT" | sed 's/v\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\)/\2/')
  PATCH=$(echo "$CURRENT" | sed 's/v\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\)/\3/')

  # Menu: choisir type d'incrément
  INCREMENT=$(echo -e "patch\nminor\nmajor" | fzf --prompt="Type de release > " --height=5 --reverse)

  case "$INCREMENT" in
    "major") NEW_VERSION="v$((MAJOR + 1)).0.0" ;;
    "minor") NEW_VERSION="v${MAJOR}.$((MINOR + 1)).0" ;;
    "patch") NEW_VERSION="v${MAJOR}.${MINOR}.$((PATCH + 1))" ;;
    *) echo "Annulé."; exit 0 ;;
  esac

  # Écrire nouvelle version
  echo "$NEW_VERSION" > VERSION

  # Commit + push + tag
  git add VERSION
  git commit -m "release: ${NEW_VERSION}"
  git tag -a "$NEW_VERSION" -m "Release ${NEW_VERSION}"
  git push origin main --quiet
  git push origin "$NEW_VERSION" --quiet

  echo ""
  echo "✅ Tag créé: $NEW_VERSION"
  ;;

# ============================================================
# OPTION 2: Déployer une version (dans le dossier prod isolé)
# ============================================================
"Déployer une version")
  # Cloner ou mettre à jour le dossier prod
  if [ ! -d "$PROD_DIR" ]; then
    echo "Clonage du repo dans $PROD_DIR..."
    git clone "$REPO_URL" "$PROD_DIR" --quiet
  fi

  cd "$PROD_DIR"
  git fetch --tags --quiet

  LATEST_TAG=$(git tag -l --sort=-v:refname | head -1)

  if [ -z "$LATEST_TAG" ]; then
    echo "❌ Aucun tag trouvé. Créez d'abord un tag (option 1)."
    exit 1
  fi

  echo "Déploiement de: $LATEST_TAG"
  git reset --hard HEAD --quiet
  git checkout "$LATEST_TAG" --quiet

  # Écrire la version déployée
  echo "$LATEST_TAG" > .deployed-version

  # Créer/utiliser virtualenv isolé pour la prod
  if [ ! -d "$PROD_DIR/.venv" ]; then
    echo "Création du virtualenv prod..."
    python3 -m venv "$PROD_DIR/.venv"
  fi
  PROD_PYTHON="$PROD_DIR/.venv/bin/python3"
  PROD_PIP="$PROD_DIR/.venv/bin/pip"

  # Installer les dépendances dans le venv prod
  echo "Installation des dépendances (venv prod)..."
  $PROD_PIP install -e . --quiet 2>/dev/null
  $PROD_PYTHON setup_database.py

  # Copier .env et config depuis dev
  cp "$DEV_DIR/.env" .env 2>/dev/null || true
  cp "$DEV_DIR/gnl-config.json" gnl-config.json 2>/dev/null || true

  # Arrêter le service
  echo "Arrêt du service..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  lsof -ti:$PROD_PORT | xargs kill 2>/dev/null || true
  sleep 1

  # Créer/écraser le service systemd
  echo "Configuration du service systemd..."
  sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=GNL Process (prod)
After=network.target

[Service]
Type=simple
WorkingDirectory=${PROD_DIR}
ExecStart=${PROD_DIR}/.venv/bin/python3 -m uvicorn gnl_core.web.app:app --host 0.0.0.0 --port ${PROD_PORT}
ExecStop=/bin/kill -SIGTERM \$MAINPID
Restart=on-failure
RestartSec=5
User=$(whoami)
Environment=PATH=${PROD_DIR}/.venv/bin:/usr/bin:/usr/local/bin
EnvironmentFile=${PROD_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable "$SERVICE_NAME" --quiet
  sudo systemctl start "$SERVICE_NAME"

  sleep 3

  # Vérifier
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "✅ Déploiement réussi"
    echo "   Version: $LATEST_TAG"
    echo "   Dossier: $PROD_DIR"
    echo "   URL: http://localhost:${PROD_PORT}"
    echo "   Auto-start: activé"
  else
    echo "❌ Erreur — vérifiez: journalctl -u $SERVICE_NAME"
    exit 1
  fi
  ;;

*)
  echo "Annulé."
  exit 0
  ;;
esac
