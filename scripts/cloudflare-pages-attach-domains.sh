#!/usr/bin/env bash
# Attach custom hostnames to a Cloudflare Pages project via the REST API.
# Wrangler 4.45 no longer accepts `wrangler pages domain add … --project-name`.
#
# Requires (after cloudflare-resolve-account.sh):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
# Optional:
#   PAGES_PROJECT (default: swiftterm-web)
#
# Usage:
#   source scripts/cloudflare-resolve-account.sh
#   bash scripts/cloudflare-pages-attach-domains.sh [host ...]
set -euo pipefail

PROJECT="${PAGES_PROJECT:-swiftterm-web}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID required}"
TOKEN="${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN required}"

HOSTS=("$@")
if [[ ${#HOSTS[@]} -eq 0 ]]; then
  HOSTS=(toolvip1.top www.toolvip1.top)
fi

attach_one() {
  local host="$1"
  local url="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/${PROJECT}/domains"
  echo "--- pages domain add (API): $host ---"
  local body http
  body="$(mktemp)"
  http="$(
    curl --proto '=https' --tlsv1.2 -sS -o "$body" -w '%{http_code}' \
      -X POST "$url" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      --data "{\"name\":\"${host}\"}"
  )"
  python3 - "$body" "$http" "$host" <<'PY'
import json, sys
path, http, host = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(path, encoding="utf-8").read()
try:
    data = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    print(f"WARN: {host} non-JSON HTTP {http}: {raw[:300]}")
    sys.exit(0)
ok = bool(data.get("success"))
errs = data.get("errors") or []
# Already exists is success for our purposes.
codes = {e.get("code") for e in errs if isinstance(e, dict)}
msgs = "; ".join(
    str(e.get("message") or e) for e in errs
) or raw[:300]
if ok or http in {"200", "201", "409"} or 8000012 in codes or 8000032 in codes:
    status = (data.get("result") or {}).get("status") or "ok"
    print(f"OK: {host} attached (http={http} status={status})")
    sys.exit(0)
print(f"WARN: {host} not attached (http={http}): {msgs}")
PY
  rm -f "$body"
}

for h in "${HOSTS[@]}"; do
  attach_one "$h"
done

echo "After DNS settles: https://${HOSTS[0]}/"
echo "If HTTPS returns Cloudflare Access login, disable Access for that hostname."
