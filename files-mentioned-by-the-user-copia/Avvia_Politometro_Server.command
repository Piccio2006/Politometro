#!/bin/zsh
set -e
cd "$(dirname "$0")"

export MPLCONFIGDIR="$PWD/.matplotlib-cache"

if [ -z "$POLITOMETRO_ADMIN_EMAIL" ]; then
  echo "Email admin [piccioligiovanni@outlook.it]: "
  read ADMIN_INPUT_EMAIL
  export POLITOMETRO_ADMIN_EMAIL="${ADMIN_INPUT_EMAIL:-piccioligiovanni@outlook.it}"
fi

if [ -z "$POLITOMETRO_ADMIN_PASSWORD_HASH" ]; then
  echo "Scegli una password admin temporanea per questa sessione:"
  read -s ADMIN_PASSWORD
  echo ""
  if [ -z "$ADMIN_PASSWORD" ]; then
    echo "Password vuota: annullo."
    exit 1
  fi
  export POLITOMETRO_ADMIN_PASSWORD_HASH="$(printf "%s" "$ADMIN_PASSWORD" | "$PWD/.venv-politometro/bin/python" -c 'import base64, hashlib, secrets, sys; password=sys.stdin.read(); rounds=260000; salt=secrets.token_bytes(16); digest=hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds); print("pbkdf2_sha256$%d$%s$%s" % (rounds, base64.urlsafe_b64encode(salt).decode("ascii"), base64.urlsafe_b64encode(digest).decode("ascii")))' )"
  unset ADMIN_PASSWORD
fi

if [ -z "$POLITOMETRO_SESSION_SECRET" ]; then
  export POLITOMETRO_SESSION_SECRET="$("$PWD/.venv-politometro/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
fi

PORT="${POLITOMETRO_PORT:-7860}"
URL="http://127.0.0.1:${PORT}/"
ADMIN_URL="http://127.0.0.1:${PORT}/admin"

OLD_PIDS="$(lsof -ti tcp:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$OLD_PIDS" ]; then
  echo "Ho trovato un vecchio server Politometro sulla porta ${PORT}. Lo chiudo e riparto pulito..."
  kill $OLD_PIDS 2>/dev/null || true
  sleep 1
fi

echo ""
echo "Politometro server avviato."
echo "Sito: ${URL}"
echo "Dashboard dataset: ${ADMIN_URL}"
echo "Login: ${POLITOMETRO_ADMIN_EMAIL} + la password appena scelta."
echo "Per fermarlo: chiudi questa finestra o premi Ctrl+C."
echo ""

sleep 1 && open "${ADMIN_URL}?fresh=$(date +%s)" >/dev/null 2>&1 &
exec "$PWD/.venv-politometro/bin/uvicorn" politometro_custom_app:app --host 127.0.0.1 --port "${PORT}"
