#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Charger .env
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^$' | xargs)
fi

# Déterminer le port (dev par défaut, prod si --prod)
if [ "$1" = "--prod" ]; then
  PORT=${PROD_PORT:-8000}
  MODE="prod"
else
  PORT=${DEV_PORT:-8000}
  MODE="dev"
fi

# Arrêter les processus sur ce port
lsof -ti:$PORT | xargs kill 2>/dev/null || true
sleep 1

# Installer les dépendances si nécessaire
echo "[$MODE] Vérification des dépendances..."
pip install -e "$SCRIPT_DIR" --quiet 2>/dev/null

# Appliquer les migrations DB
python3 "$SCRIPT_DIR/setup_database.py"

# Lancer l'application
echo "[$MODE] Démarrage de GNL Process (port $PORT)..."
if [ "$MODE" = "prod" ]; then
  nohup python3 -m uvicorn gnl_core.web.app:app --host 0.0.0.0 --port $PORT > "$SCRIPT_DIR/gnl-${MODE}.log" 2>&1 &
  echo "[$MODE] PID: $!"
else
  python3 -m uvicorn gnl_core.web.app:app --host 0.0.0.0 --port $PORT
fi

echo "[$MODE] GNL Process démarré → http://localhost:${PORT}"
