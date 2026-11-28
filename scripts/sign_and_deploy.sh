#!/usr/bin/env bash
# sign_and_deploy.sh — Mac ONLY. Install .ipa to a physical device.
# Usage:
#   ./scripts/sign_and_deploy.sh --ipa path/to/app.ipa --udid <UDID> [--cert path/to/cert.p12]
# Env: UDID, IPA, CERT (optional), PASSWORD (optional for p12)
set -euo pipefail

IPA="${IPA:-}"
UDID="${UDID:-}"
CERT="${CERT:-}"
PASSWORD="${PASSWORD:-}"

usage() {
  cat <<'EOF'
Usage: sign_and_deploy.sh --ipa <file.ipa> --udid <DEVICE_UDID> [--cert <cert.p12>]

Installs with xcrun devicectl (Xcode 15+) or ios-deploy if available.
Prints certificate not-after date when --cert is given; reminds free Apple ID 7-day refresh.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ipa) IPA="$2"; shift 2 ;;
    --udid) UDID="$2"; shift 2 ;;
    --cert) CERT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: macOS required" >&2
  exit 2
fi

[[ -n "$IPA" && -f "$IPA" ]] || { echo "ERROR: --ipa required" >&2; exit 1; }
[[ -n "$UDID" ]] || { echo "ERROR: --udid required" >&2; exit 1; }

echo "=== sign_and_deploy ==="
echo "ipa=$IPA"
echo "udid=$UDID"
echo "ipa_sha256=$(shasum -a 256 "$IPA" | awk '{print $1}')"

if [[ -n "$CERT" ]]; then
  [[ -f "$CERT" ]] || { echo "ERROR: cert not found: $CERT" >&2; exit 1; }
  echo "=== certificate not-after ==="
  set +e
  if [[ -n "$PASSWORD" ]]; then
    openssl pkcs12 -in "$CERT" -passin "pass:$PASSWORD" -nokeys -clcerts 2>/dev/null \
      | openssl x509 -noout -enddate 2>/dev/null
  else
    openssl pkcs12 -in "$CERT" -nokeys -clcerts 2>/dev/null \
      | openssl x509 -noout -enddate 2>/dev/null
  fi
  CERT_EC=$?
  set -e
  if [[ "$CERT_EC" -ne 0 ]]; then
    echo "WARN: could not parse cert enddate (wrong password or openssl pkcs12 legacy flags)"
  fi
  echo "REMINDER: Free Apple Developer signing typically expires in ~7 days — refresh before expiry."
  echo 'Paid Apple Developer ($99/yr): distribution certs last up to ~1 year — still calendar the not-after date.'
fi

install_ec=1
if command -v xcrun >/dev/null && xcrun devicectl --help >/dev/null 2>&1; then
  echo "=== xcrun devicectl device install app ==="
  set +e
  xcrun devicectl device install app --device "$UDID" "$IPA"
  install_ec=$?
  set -e
  echo "devicectl_exit=$install_ec"
elif command -v ios-deploy >/dev/null; then
  echo "=== ios-deploy ==="
  set +e
  ios-deploy --id "$UDID" --bundle "$IPA"
  install_ec=$?
  set -e
  echo "ios_deploy_exit=$install_ec"
else
  echo "ERROR: need xcrun devicectl or ios-deploy" >&2
  exit 2
fi

[[ "$install_ec" -eq 0 ]] || exit "$install_ec"
echo "ACCEPT: install finished exit=0"
exit 0
