#!/bin/bash
case "$1" in
  start)
    sudo systemctl start gnl-process
    echo "✓ gnl-process (prod) démarré"
    ;;
  stop)
    sudo systemctl stop gnl-process
    echo "✓ gnl-process (prod) arrêté"
    ;;
  status)
    sudo systemctl status gnl-process --no-pager
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
