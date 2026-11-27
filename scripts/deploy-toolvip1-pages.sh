#!/usr/bin/env bash
# Deploy the prepared Cloudflare Pages site and attach toolvip1.top.
# Requires CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID in the environment
# (GitHub Actions secrets, or the same names exported locally). Values must
# never be pasted into chat.
#
# Usage (repo root):
#   bash scripts/prepare-cloudflare-web.sh   # if Web/cloudflare/site is stale
#   bash scripts/deploy-toolvip1-pages.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF_DIR="$ROOT/Web/cloudflare"
PROJECT="${PAGES_PROJECT:-swiftterm-web}"
DOMAIN="${CUSTOM_DOMAIN:-toolvip1.top}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "FAIL: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are not set." >&2
  echo "Add them as GitHub Actions secrets on jiaomeimei0-prog/SwiftTerm, then:" >&2
  echo "  gh workflow run cloudflare-pages-web.yml -R jiaomeimei0-prog/SwiftTerm --ref main" >&2
  exit 1
fi

cd "$CF_DIR"
if [[ ! -x ./node_modules/.bin/wrangler ]]; then
  npm ci --ignore-scripts
fi
if [[ ! -f site/index.html ]]; then
  echo "FAIL: missing $CF_DIR/site — run: bash scripts/prepare-cloudflare-web.sh" >&2
  exit 1
fi

echo "=== Deploy Pages project=$PROJECT ==="
./node_modules/.bin/wrangler pages deploy site \
  --project-name="$PROJECT" \
  --commit-dirty=true

echo "=== Attach custom domains ==="
for host in "$DOMAIN" "www.${DOMAIN}"; do
  echo "--- pages domain add: $host ---"
  ./node_modules/.bin/wrangler pages domain add "$host" --project-name="$PROJECT" \
    || echo "WARN: $host not attached (unregistered, wrong zone, or already present)."
done

echo "=== Public probe (may fail from egress-restricted hosts) ==="
for host in "$DOMAIN" "www.${DOMAIN}"; do
  code=$(curl -4 -sS -o /tmp/swiftterm-domain-body.html -w "%{http_code}" --connect-timeout 15 "https://${host}/" || echo "000")
  title=$(python3 -c 'import re,sys; t=open("/tmp/swiftterm-domain-body.html","rb").read().decode("utf-8","replace"); m=re.search(r"<title>([^<]+)</title>", t, re.I); print(m.group(1) if m else "")' 2>/dev/null || true)
  echo "https://${host}/ → HTTP ${code} title=${title:-?}"
  case "$code" in
    200)
      if grep -qi 'SwiftTerm\|wasm\|canvas' /tmp/swiftterm-domain-body.html; then
        echo "OK: ${host} looks like the SwiftTerm site"
      else
        echo "WARN: ${host} returned 200 but body does not look like SwiftTerm"
      fi
      ;;
    302|401|403)
      echo "WARN: ${host} may still be behind Cloudflare Access — disable Access for this hostname"
      ;;
    000)
      echo "WARN: probe from this host failed (TLS/DNS). Check from a browser outside the agent VM."
      ;;
  esac
done

echo "Done. Open https://${DOMAIN}/ after DNS settles."
