#!/usr/bin/env bash
# Startet Backend und Frontend gleichzeitig.
# Beenden mit Ctrl+C — beide Prozesse werden automatisch beendet.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Backend starten..."
cd "$ROOT/backend"
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
python -m gysi_ml.main &
BACKEND_PID=$!

echo "==> Frontend starten..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend  PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Beenden mit Ctrl+C"

# Beide Prozesse beim Beenden sauber stoppen
trap "echo ''; echo 'Stoppe...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait $BACKEND_PID $FRONTEND_PID
