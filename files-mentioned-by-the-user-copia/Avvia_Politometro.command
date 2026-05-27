#!/bin/zsh
cd "$(dirname "$0")"

export MPLCONFIGDIR="$PWD/.matplotlib-cache"
if [[ -z "$PORT" ]]; then
  for candidate in 7870 7871 7872 7873 7874 7875 7880 7881; do
    if ! lsof -nP -iTCP:"$candidate" -sTCP:LISTEN >/dev/null 2>&1; then
      PORT="$candidate"
      break
    fi
  done
fi
PORT="${PORT:-7890}"
URL="http://127.0.0.1:${PORT}/"

echo "Avvio Politometro aggiornato..."
echo "URL: ${URL}"
echo "Per fermarlo, chiudi questa finestra o premi Ctrl+C."
echo ""

echo "Creo la versione pubblica aggiornata..."
"$PWD/.venv-politometro/bin/python" "$PWD/build_public_site.py" || exit 1

sleep 1 && open "${URL}" >/dev/null 2>&1 &
exec "$PWD/.venv-politometro/bin/python" -m http.server "${PORT}" --bind 127.0.0.1 --directory "$PWD/dist"
