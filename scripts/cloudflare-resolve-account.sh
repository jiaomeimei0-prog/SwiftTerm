#!/usr/bin/env bash
# Trim Cloudflare secrets and resolve a real Account ID for wrangler Pages.
# Fixes Authentication error [code: 10000] when CLOUDFLARE_ACCOUNT_ID is a
# Zone ID (same 32-hex shape) or has stray whitespace from GitHub Secrets.
#
# Usage (sourced or executed):
#   source scripts/cloudflare-resolve-account.sh
#   # exports: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
set -euo pipefail

export CLOUDFLARE_API_TOKEN="$(printf '%s' "${CLOUDFLARE_API_TOKEN:-}" | tr -d '[:space:]')"
export CLOUDFLARE_ACCOUNT_ID="$(printf '%s' "${CLOUDFLARE_ACCOUNT_ID:-}" | tr -d '[:space:]')"

if [[ -z "${CLOUDFLARE_API_TOKEN}" ]]; then
  echo '::error::Set GitHub Actions secret CLOUDFLARE_API_TOKEN (Pages:Edit + Account Settings:Read + Zone DNS:Edit).' >&2
  return 1 2>/dev/null || exit 1
fi

RESOLVED="$(
  CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" \
  CLOUDFLARE_ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID" \
  python3 - <<'PY'
import json, os, sys, urllib.error, urllib.request

token = os.environ["CLOUDFLARE_API_TOKEN"]
preferred = (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()

req = urllib.request.Request(
    "https://api.cloudflare.com/client/v4/accounts?per_page=50",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
)
try:
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", "replace")
    print(f"Cloudflare /accounts HTTP {exc.code}: {body}", file=sys.stderr)
    sys.exit(1)

if not data.get("success"):
    print(f"Cloudflare /accounts failed: {data.get('errors') or data}", file=sys.stderr)
    sys.exit(1)

accounts = data.get("result") or []
ids = [a["id"] for a in accounts if a.get("id")]
names = {a["id"]: a.get("name") or "?" for a in accounts if a.get("id")}

if preferred and preferred in ids:
    print(preferred)
    sys.exit(0)

if preferred and preferred not in ids:
    print(
        f"::warning::CLOUDFLARE_ACCOUNT_ID is not visible to this token "
        f"(often a Zone ID was pasted). Auto-selecting from /accounts.",
        file=sys.stderr,
    )

if len(ids) == 1:
    print(ids[0])
    sys.exit(0)

if not ids:
    print(
        "Token returned zero accounts. Need Account Settings:Read and "
        "Cloudflare Pages:Edit on the target account.",
        file=sys.stderr,
    )
    sys.exit(1)

listing = ", ".join(f"{names[i]} ({i[:8]}…)" for i in ids)
print(
    f"Multiple accounts visible; set CLOUDFLARE_ACCOUNT_ID to one of: {listing}",
    file=sys.stderr,
)
sys.exit(1)
PY
)"

export CLOUDFLARE_ACCOUNT_ID="$RESOLVED"
echo "Cloudflare auth OK: account_id length=${#CLOUDFLARE_ACCOUNT_ID} prefix=${CLOUDFLARE_ACCOUNT_ID:0:4}…"
