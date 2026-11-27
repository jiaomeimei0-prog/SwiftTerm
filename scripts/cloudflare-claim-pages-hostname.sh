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

# DELETE may return an empty body on 200 — never crash on that.
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
if not raw:
    print(f"  http={http} (empty body)")
    sys.exit(0 if http in {"200", "201", "204", "404"} else 1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print(f"  http={http} non-JSON: {raw[:200]}")
    sys.exit(0 if http in {"200", "201", "204", "404"} else 1)
ok = bool(data.get("success")) or http in {"200", "201", "204", "404"}
print(f"  http={http} success={data.get('success')} errors={data.get('errors')}")
sys.exit(0 if ok else 1)
PY
  local rc=$?
  rm -f "$body"
  return "$rc"
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
      || echo "WARN: delete workers/domains ${did} returned non-success (continuing)"
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
        || echo "WARN: delete workers/routes ${rid} returned non-success (continuing)"
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
        || echo "WARN: delete dns ${rid} failed (continuing)"
    done < /tmp/cf-dns-to-delete.txt
  else
    echo "No workers.dev DNS records to delete for claimed hosts"
  fi

  echo "=== Ensure Pages DNS (CNAME → ${PROJECT}.pages.dev, proxied) ==="
  # Apex missing A/AAAA causes Chrome DNS_PROBE_FINISHED_NXDOMAIN even though
  # the zone exists (NOERROR / ANSWER:0). Pages expects a proxied CNAME; CF
  # flattens apex CNAMEs. If Zone DNS API is forbidden for this token, we fall
  # back to Pages domain rebind (delete+add) which recreates DNS.
  TARGET="${PROJECT}.pages.dev"
  DNS_ENSURE_RC=0
  python3 - "$DNS_JSON" "$ZONE_ID" "$TOKEN" "$APEX" "www.${APEX}" "$TARGET" <<'PY' || DNS_ENSURE_RC=$?
import json, sys, urllib.error, urllib.request

dns_json, zone_id, token, apex, www, target = sys.argv[1:7]
data = json.loads(dns_json)
records = data.get("result") or []
if not data.get("success"):
    print("WARN: prior DNS list unsuccessful:", data.get("errors"))

wanted = {
    apex: ("CNAME", target),
    www: ("CNAME", target),
}

def req(method, url, body=None):
    data_bytes = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        url,
        data=data_bytes,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(r, timeout=45) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw) if raw.strip() else {"success": True}

by_name = {}
for row in records:
    name = (row.get("name") or "").rstrip(".")
    by_name.setdefault(name, []).append(row)

wrote = 0
denied = False
for host, (typ, content) in wanted.items():
    existing = by_name.get(host, [])
    good = [
        r for r in existing
        if (r.get("type") == typ and (r.get("content") or "").rstrip(".") == content and r.get("proxied") is True)
    ]
    if good:
        print(f"OK DNS already: {typ} {host} -> {content} proxied")
        continue
    for r in existing:
        rid = r.get("id")
        if not rid:
            continue
        if r.get("type") in {"A", "AAAA", "CNAME"}:
            print(f"DELETE conflicting {r.get('type')} {host} -> {r.get('content')}")
            try:
                out = req("DELETE", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{rid}")
                print(f"  success={out.get('success')} errors={out.get('errors')}")
            except Exception as exc:
                denied = True
                print(f"  WARN delete failed: {exc}")
    body = {
        "type": typ,
        "name": host,
        "content": content,
        "proxied": True,
        "ttl": 1,
    }
    print(f"CREATE {typ} {host} -> {content} proxied")
    try:
        out = req("POST", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", body)
        print(f"  success={out.get('success')} errors={out.get('errors')} id={(out.get('result') or {}).get('id','')[:8]}")
        if out.get("success"):
            wrote += 1
        else:
            denied = True
    except Exception as exc:
        denied = True
        print(f"  WARN create failed: {exc}")

try:
    final = req("GET", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?per_page=100")
    print("=== DNS after ensure ===")
    for row in final.get("result") or []:
        print(f"  {(row.get('type') or ''):6} {(row.get('name') or ''):40} -> {row.get('content')}  proxied={row.get('proxied')}")
except Exception as exc:
    denied = True
    print(f"WARN: cannot list DNS after ensure: {exc}")

if denied and wrote == 0:
    print("DNS_API_DENIED=1")
    sys.exit(42)
print(f"DNS_ENSURE wrote={wrote} denied={denied}")
PY

  if [[ "$DNS_ENSURE_RC" -eq 42 ]]; then
    echo "Zone DNS API denied for this token — will rebind Pages domains to recreate DNS"
    export PAGES_DOMAIN_REBIND=1
  fi
fi

echo "=== Re-assert Pages custom domains for project=${PROJECT} ==="
# Always rebind once when apex has no addresses (NXDOMAIN / ANSWER:0).
export PAGES_DOMAIN_REBIND="${PAGES_DOMAIN_REBIND:-1}"
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
    print(f"  {(row.get('name') or '?'):30} status={row.get('status')}")
PY

echo "=== Remaining Worker custom domains (should be empty for claimed hosts) ==="
LEFT="$(cf_get "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/domains")"
python3 - "$LEFT" "${HOSTS[@]}" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
wanted = set(sys.argv[2:])
left = []
for row in data.get("result") or []:
    host = row.get("hostname") or row.get("domain") or ""
    if host in wanted:
        left.append(f"{host} -> service={row.get('service')}")
if left:
    print("WARN still bound:", "; ".join(left))
else:
    print("OK: no Worker custom domains on claimed hosts")
PY

echo "Done. Open https://${APEX}/ — expect SwiftTerm WASM title, not Hello World."
echo "Also verify https://${PROJECT}.pages.dev/"
