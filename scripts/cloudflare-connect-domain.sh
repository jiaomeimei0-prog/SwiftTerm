#!/usr/bin/env bash
# Deploy SwiftTerm WASM site to Cloudflare Pages and attach custom domain(s).
# Requires env (never paste into chat):
#   CLOUDFLARE_API_TOKEN
#   CLOUDFLARE_ACCOUNT_ID
#
# Usage (from repo root, after prepare-cloudflare-web.sh):
#   export CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=...
#   bash scripts/cloudflare-connect-domain.sh [domain ...]
#
# Default domains: toolvip1.top www.toolvip1.top
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF_DIR="$ROOT/Web/cloudflare"
PROJECT="${PAGES_PROJECT:-swiftterm-web}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "FAIL: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set in the environment." >&2
  echo "Add them as GitHub Actions secrets, then re-run the Cloudflare Pages workflow." >&2
  exit 1
fi

DOMAINS=("$@")
if [[ ${#DOMAINS[@]} -eq 0 ]]; then
  DOMAINS=(toolvip1.top www.toolvip1.top)
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
for d in "${DOMAINS[@]}"; do
  echo "--- domain add: $d ---"
  if ./node_modules/.bin/wrangler pages domain add "$d" --project-name="$PROJECT"; then
    echo "OK attached (or already attached): $d"
  else
    echo "WARN: could not attach $d — domain may be unregistered, wrong zone, or DNS not ready."
  fi
done

echo "=== Probe Access lock (public GET) ==="
for d in "${DOMAINS[@]}"; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 12 "https://${d}/" || echo "000")
  echo "https://${d}/ → HTTP $code"
  if [[ "$code" == "302" ]] || [[ "$code" == "401" ]] || [[ "$code" == "403" ]]; then
    echo "WARN: $d may still be behind Cloudflare Access — disable Access app for this hostname in Zero Trust."
  fi
done

echo "Done. After DNS settles, open https://${DOMAINS[0]}/"
