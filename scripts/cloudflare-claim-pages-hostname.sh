#!/usr/bin/env bash
# Claim toolvip1.top (and optional hosts) for Cloudflare Pages project swiftterm-web.
# Removes competing Worker custom domains / routes that serve the default
# "Hello World" Worker (historically patient-pond-3427 / toolvip1-ssh / swiftterm).
#
# Requires (after cloudflare-resolve-account.sh):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
# Optional:
#   PAGES_PROJECT (default swiftterm-web)
#   CUSTOM_DOMAIN (default toolvip1.top) — also claims www.$CUSTOM_DOMAIN
set -euo pipefail

PROJECT="${PAGES_PROJECT:-swiftterm-web}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:?}"
TOKEN="${CLOUDFLARE_API_TOKEN:?}"
APEX="${CUSTOM_DOMAIN:-toolvip1.top}"
HOSTS=("$APEX" "www.${APEX}")

auth_hdr=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

cf_get() {
  local url="$1"
  curl --proto '=https' --tlsv1.2 -sS "${auth_hdr[@]}" "$url"
}

cf_delete() {
  local url="$1"
  curl --proto '=https' --tlsv1.2 -sS -X DELETE "${auth_hdr[@]}" "$url"
}

echo "=== Resolve zone for ${APEX} ==="
ZONE_JSON="$(cf_get "https://api.cloudflare.com/client/v4/zones?name=${APEX}")"
ZONE_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("result") or []; print(r[0]["id"] if r else "")' <<<"$ZONE_JSON")"
if [[ -z "$ZONE_ID" ]]; then
  echo "WARN: no zone named ${APEX} visible to this token — skip DNS/route cleanup"
else
  echo "Zone ID prefix=${ZONE_ID:0:8}…"
fi

echo "=== Remove Worker custom domains matching hosts ==="
DOMAINS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains")"
python3 - "$DOMAINS_JSON" "${HOSTS[@]}" <<'PY' > /tmp/cf-worker-domains-to-delete.txt
import json, sys
data = json.loads(sys.argv[1])
wanted = set(sys.argv[2:])
for row in data.get("result") or []:
    host = row.get("hostname") or row.get("domain") or ""
    did = row.get("id") or ""
    service = row.get("service") or row.get("environment") or "?"
    if host in wanted and did:
        print(f"{did}\t{host}\t{service}")
PY
if [[ -s /tmp/cf-worker-domains-to-delete.txt ]]; then
  while IFS=$'\t' read -r did host service; do
    echo "DELETE workers/domains id=${did} host=${host} service=${service}"
    cf_delete "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains/${did}" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  success=", d.get("success"), "errors=", d.get("errors"))'
  done < /tmp/cf-worker-domains-to-delete.txt
else
  echo "No Worker custom domains matched ${HOSTS[*]}"
fi

if [[ -n "$ZONE_ID" ]]; then
  echo "=== Remove Worker routes matching hosts ==="
  ROUTES_JSON="$(cf_get "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/workers/routes")"
  python3 - "$ROUTES_JSON" "${HOSTS[@]}" <<'PY' > /tmp/cf-worker-routes-to-delete.txt
import json, sys
data = json.loads(sys.argv[1])
wanted = set(sys.argv[2:])
for row in data.get("result") or []:
    pattern = row.get("pattern") or ""
    rid = row.get("id") or ""
    script = row.get("script") or "?"
    host = pattern.split("/")[0]
    if rid and any(host == w or host.endswith("." + w) or pattern.startswith(w + "/") for w in wanted):
        print(f"{rid}\t{pattern}\t{script}")
PY
  if [[ -s /tmp/cf-worker-routes-to-delete.txt ]]; then
    while IFS=$'\t' read -r rid pattern script; do
      echo "DELETE workers/routes id=${rid} pattern=${pattern} script=${script}"
      cf_delete "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/workers/routes/${rid}" \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  success=", d.get("success"), "errors=", d.get("errors"))'
    done < /tmp/cf-worker-routes-to-delete.txt
  else
    echo "No Worker routes matched ${HOSTS[*]}"
  fi

  echo "=== DNS records for ${APEX} (inspect) ==="
  DNS_JSON="$(cf_get "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?per_page=100")"
  python3 - "$DNS_JSON" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
for row in data.get("result") or []:
    name = row.get("name") or ""
    typ = row.get("type") or ""
    content = row.get("content") or ""
    proxied = row.get("proxied")
    print(f"  {typ:6} {name:40} -> {content}  proxied={proxied}")
PY

  # Drop DNS that clearly targets workers.dev Hello-World style hosts.
  python3 - "$DNS_JSON" "${HOSTS[@]}" <<'PY' > /tmp/cf-dns-to-delete.txt
import json, sys
data = json.loads(sys.argv[1])
wanted = set(sys.argv[2:])
bad_bits = ("workers.dev", "workers.cloudflare.com")
for row in data.get("result") or []:
    name = (row.get("name") or "").rstrip(".")
    content = (row.get("content") or "").lower()
    rid = row.get("id") or ""
    typ = row.get("type") or ""
    if name not in wanted:
        continue
    if any(b in content for b in bad_bits):
        print(f"{rid}\t{typ}\t{name}\t{row.get('content')}")
PY
  if [[ -s /tmp/cf-dns-to-delete.txt ]]; then
    while IFS=$'\t' read -r rid typ name content; do
      echo "DELETE dns ${typ} ${name} -> ${content}"
      cf_delete "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${rid}" \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  success=", d.get("success"))'
    done < /tmp/cf-dns-to-delete.txt
  else
    echo "No workers.dev DNS records to delete for claimed hosts"
  fi
fi

echo "=== Re-assert Pages custom domains for project=${PROJECT} ==="
bash "$(dirname "$0")/cloudflare-pages-attach-domains.sh" "${HOSTS[@]}"

echo "=== Pages domain status ==="
PAGES_DOM="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/pages/projects/${PROJECT}/domains")"
python3 - "$PAGES_DOM" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
if not data.get("success"):
    print("WARN: list domains failed:", data.get("errors"))
    sys.exit(0)
for row in data.get("result") or []:
    print(f"  {(row.get('name') or '?'):30} status={row.get('status')} verification={row.get('verification_data')}")
PY

echo "Done. Open https://${APEX}/ — expect SwiftTerm WASM title, not Hello World."
echo "If Hello World remains: Cloudflare Dashboard → Workers → delete script bound to ${APEX},"
echo "and Workers Builds project 'swiftterm' custom domains if present."
