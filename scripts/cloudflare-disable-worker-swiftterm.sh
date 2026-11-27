#!/usr/bin/env bash
# Disable/remove the competing Workers script "swiftterm" (Workers Builds)
# that previously bound toolvip1.top and served Hello World.
#
# Requires (after cloudflare-resolve-account.sh):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
#
# Safe by default: lists + removes custom domains/routes for claimed hosts,
# then deletes the worker script named "swiftterm" if present.
set -euo pipefail

ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:?}"
TOKEN="${CLOUDFLARE_API_TOKEN:?}"
SCRIPT="${WORKER_SCRIPT_NAME:-swiftterm}"
APEX="${CUSTOM_DOMAIN:-toolvip1.top}"
HOSTS=("$APEX" "www.${APEX}")

auth_hdr=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

cf_get() { curl --proto '=https' --tlsv1.2 -sS "${auth_hdr[@]}" "$1"; }

cf_delete() {
  local url="$1"
  local body http
  body="$(mktemp)"
  http="$(
    curl --proto '=https' --tlsv1.2 -sS -o "$body" -w '%{http_code}' \
      -X DELETE "${auth_hdr[@]}" "$url" || echo "000"
  )"
  python3 - "$body" "$http" <<'PY'
import json, sys
path, http = sys.argv[1], sys.argv[2]
raw = open(path, encoding="utf-8").read().strip()
data = {}
if raw:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  http={http} non-JSON: {raw[:200]}")
        sys.exit(0 if http in {"200","201","204","404"} else 1)
ok = bool(data.get("success")) or http in {"200","201","204","404"}
print(f"  http={http} success={data.get('success')} errors={data.get('errors')}")
sys.exit(0 if ok else 1)
PY
  local rc=$?
  rm -f "$body"
  return "$rc"
}

echo "=== List Workers scripts (look for ${SCRIPT}) ==="
SCRIPTS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts")"
python3 - "$SCRIPTS_JSON" "$SCRIPT" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
want = sys.argv[2]
if not data.get("success"):
    print("WARN: list scripts failed:", data.get("errors"))
    sys.exit(0)
names = []
for row in data.get("result") or []:
    # result may be list of script objects or {id: ...}
    name = row.get("id") or row.get("name") or ""
    names.append(name)
    mark = " <== TARGET" if name == want else ""
    print(f"  script={name}{mark}")
if want not in names:
    print(f"OK: worker script '{want}' not present")
else:
    print(f"FOUND: worker script '{want}'")
open("/tmp/cf-worker-script-found","w").write("1" if want in names else "0")
PY

echo "=== Remove Worker custom domains on ${HOSTS[*]} ==="
DOMAINS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains")"
python3 - "$DOMAINS_JSON" "${HOSTS[@]}" <<'PY' > /tmp/cf-worker-domains-del.txt
import json, sys
data = json.loads(sys.argv[1])
wanted = set(sys.argv[2:])
for row in data.get("result") or []:
    host = row.get("hostname") or row.get("domain") or ""
    did = row.get("id") or ""
    service = row.get("service") or "?"
    if host in wanted and did:
        print(f"{did}\t{host}\t{service}")
PY
if [[ -s /tmp/cf-worker-domains-del.txt ]]; then
  while IFS=$'\t' read -r did host service; do
    echo "DELETE workers/domains ${host} service=${service}"
    cf_delete "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains/${did}" \
      || echo "WARN: domain delete failed (continuing)"
  done < /tmp/cf-worker-domains-del.txt
else
  echo "No Worker custom domains on claimed hosts"
fi

if [[ -f /tmp/cf-worker-script-found ]] && [[ "$(cat /tmp/cf-worker-script-found)" == "1" ]]; then
  echo "=== Delete Workers script ${SCRIPT} (stops Workers Builds Hello World) ==="
  cf_delete "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/${SCRIPT}" \
    || echo "WARN: could not delete script ${SCRIPT} — remove Workers Builds trigger in dashboard if it returns"
else
  echo "Skip script delete — '${SCRIPT}' not listed (already gone or token lacks Workers Scripts:Edit)"
fi

echo "=== Try list Workers Builds / CI triggers (best-effort) ==="
for path in \
  "builds/workers/triggers" \
  "workers/scripts/${SCRIPT}/deployments" \
  ; do
  url="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/${path}"
  code="$(curl --proto '=https' --tlsv1.2 -sS -o /tmp/cf-builds.json -w '%{http_code}' "${auth_hdr[@]}" "$url" || echo 000)"
  echo "GET /${path} -> HTTP ${code}"
  python3 - <<'PY' 2>/dev/null || true
import json
try:
    d=json.load(open("/tmp/cf-builds.json"))
    print("  success=", d.get("success"), "errors=", d.get("errors"), "n=", len(d.get("result") or []) if isinstance(d.get("result"), list) else type(d.get("result")).__name__)
except Exception as e:
    print("  parse:", e)
PY
done

echo "Done. Confirm GitHub check 'Workers Builds: swiftterm' stops after next push,"
echo "or disconnect the Workers Builds project in Cloudflare Dashboard → Workers → ${SCRIPT}."
