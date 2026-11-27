#!/usr/bin/env bash
# Disable/remove the competing Workers script "swiftterm" (Workers Builds)
# that previously bound toolvip1.top and served Hello World.
#
# Requires (after cloudflare-resolve-account.sh):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
#
# Token needs (user-owned API token preferred for Builds API):
#   Account · Workers Scripts: Edit
#   Account · Workers Builds Configuration: Edit  (aka Workers CI Write)
#
# Steps: disconnect Builds triggers → drop Worker custom domains → delete script.
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

rm -f /tmp/cf-worker-script-found /tmp/cf-worker-script-tag /tmp/cf-worker-triggers.txt
echo "0" >/tmp/cf-worker-script-found

echo "=== List Workers scripts (look for ${SCRIPT}) ==="
SCRIPTS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts")"
python3 - "$SCRIPTS_JSON" "$SCRIPT" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
want = sys.argv[2]
if not data.get("success"):
    print("WARN: list scripts failed:", data.get("errors"))
    sys.exit(0)
found = False
tag = ""
for row in data.get("result") or []:
    name = row.get("id") or row.get("name") or ""
    row_tag = row.get("tag") or row.get("script_tag") or ""
    mark = " <== TARGET" if name == want else ""
    print(f"  script={name} tag={row_tag or '?'}{mark}")
    if name == want:
        found = True
        tag = row_tag
if not found:
    print(f"OK: worker script '{want}' not present")
    open("/tmp/cf-worker-script-found", "w").write("0")
else:
    print(f"FOUND: worker script '{want}' tag={tag or '(empty)'}")
    open("/tmp/cf-worker-script-found", "w").write("1")
    if tag:
        open("/tmp/cf-worker-script-tag", "w").write(tag)
PY

SCRIPT_TAG=""
if [[ -f /tmp/cf-worker-script-tag ]]; then
  SCRIPT_TAG="$(cat /tmp/cf-worker-script-tag)"
fi

# Fallback: fetch single-script metadata for tag when list omitted it.
if [[ "$(cat /tmp/cf-worker-script-found)" == "1" ]] && [[ -z "$SCRIPT_TAG" ]]; then
  echo "=== Fetch script metadata for tag ==="
  META="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/${SCRIPT}")"
  SCRIPT_TAG="$(python3 - "$META" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
row = data.get("result") or {}
if isinstance(row, dict):
    print(row.get("tag") or row.get("script_tag") or "", end="")
PY
)"
  if [[ -n "$SCRIPT_TAG" ]]; then
    echo "  tag=${SCRIPT_TAG}"
    printf '%s' "$SCRIPT_TAG" >/tmp/cf-worker-script-tag
  else
    echo "WARN: could not resolve Workers Builds script_tag for ${SCRIPT}"
  fi
fi

echo "=== Disconnect Workers Builds triggers ==="
if [[ -n "$SCRIPT_TAG" ]]; then
  TRIG_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/builds/workers/${SCRIPT_TAG}/triggers")"
  python3 - "$TRIG_JSON" <<'PY' >/tmp/cf-worker-triggers.txt
import json, sys
data = json.loads(sys.argv[1])
if not data.get("success"):
    print(f"# WARN list triggers failed: {data.get('errors')}", file=sys.stderr)
    sys.exit(0)
for row in data.get("result") or []:
    tid = row.get("trigger_uuid") or row.get("id") or ""
    name = row.get("trigger_name") or "?"
    repo = ""
    conn = row.get("repo_connection") or {}
    if isinstance(conn, dict):
        repo = conn.get("repo_name") or ""
    if tid:
        print(f"{tid}\t{name}\t{repo}")
PY
  if [[ -s /tmp/cf-worker-triggers.txt ]]; then
    while IFS=$'\t' read -r tid name repo; do
      [[ "$tid" == \#* ]] && continue
      echo "DELETE builds/triggers ${tid} name=${name} repo=${repo}"
      cf_delete "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/builds/triggers/${tid}" \
        || echo "WARN: trigger delete failed (need Workers Builds Configuration:Edit on user-owned token)"
    done </tmp/cf-worker-triggers.txt
  else
    echo "No Builds triggers listed for tag=${SCRIPT_TAG} (already disconnected or token lacks Builds API)"
  fi
else
  echo "Skip Builds trigger delete — no script_tag (script absent or list failed)"
fi

echo "=== Remove Worker custom domains on ${HOSTS[*]} ==="
DOMAINS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains")"
python3 - "$DOMAINS_JSON" "${HOSTS[@]}" <<'PY' >/tmp/cf-worker-domains-del.txt
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
  done </tmp/cf-worker-domains-del.txt
else
  echo "No Worker custom domains on claimed hosts"
fi

if [[ "$(cat /tmp/cf-worker-script-found)" == "1" ]]; then
  echo "=== Delete Workers script ${SCRIPT} ==="
  if cf_delete "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/${SCRIPT}"; then
    echo "OK: deleted worker script ${SCRIPT}"
  else
    echo "WARN: could not delete script ${SCRIPT} — need Account · Workers Scripts:Edit"
    echo "      Dashboard: https://dash.cloudflare.com/${ACCOUNT_ID}/workers/services/view/${SCRIPT}/production"
  fi
else
  echo "Skip script delete — '${SCRIPT}' not listed"
fi

echo "=== Post-check: re-list scripts ==="
POST="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts")"
python3 - "$POST" "$SCRIPT" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
want = sys.argv[2]
if not data.get("success"):
    print("WARN: post-check list failed:", data.get("errors"))
    sys.exit(0)
names = [(row.get("id") or row.get("name") or "") for row in (data.get("result") or [])]
if want in names:
    print(f"STILL_PRESENT: worker '{want}' — disconnect Builds in dashboard or fix token perms")
    sys.exit(0)
print(f"CLEAN: worker script '{want}' gone from account")
PY

echo "Done. GitHub check 'Workers Builds: ${SCRIPT}' should stop after next push once triggers are deleted."
echo "If it still fires: Dashboard → Workers → ${SCRIPT} → Settings → Builds → Disconnect,"
echo "or delete the Worker entirely. Token must be user-owned for Builds API."
