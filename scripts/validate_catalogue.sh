#!/usr/bin/env bash
# validate_catalogue.sh — chạy TRƯỚC device (host/CI).
# Không điền cột runtime. Không thay verify_command_catalogue_158.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="${PLIST:-$ROOT/Apps/a-Shell/Resources/commandDictionary.plist}"
CSV="${CSV:-$ROOT/Docs/command-158-device-matrix-PENDING.csv}"
PARITY="${PARITY:-$ROOT/Docs/command-parity-vs-ashell-2026-11-26.md}"
# Canonical hash recorded in parity doc (sha256 of plist bytes @ e95741b8 pin).
EXPECTED_PLIST_SHA256="${EXPECTED_PLIST_SHA256:-6b73f4c2f2b5bb6e3708647f4c19a6642709c907adbea5bfc4f90bd15dc7a6cc}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

[[ -f "$PLIST" ]] || fail "missing plist: $PLIST"
[[ -f "$CSV" ]] || fail "missing csv: $CSV"
[[ -f "$PARITY" ]] || fail "missing parity doc: $PARITY"

# Prefer shasum on macOS; sha256sum on Linux.
if command -v shasum >/dev/null 2>&1; then
  ACTUAL_SHA="$(shasum -a 256 "$PLIST" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA="$(sha256sum "$PLIST" | awk '{print $1}')"
else
  ACTUAL_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$PLIST")"
fi
ok "plist sha256=$ACTUAL_SHA"
if [[ "$ACTUAL_SHA" != "$EXPECTED_PLIST_SHA256" ]]; then
  fail "plist hash mismatch (want $EXPECTED_PLIST_SHA256)"
fi
if ! grep -q "$EXPECTED_PLIST_SHA256" "$PARITY"; then
  fail "parity doc does not embed expected hash $EXPECTED_PLIST_SHA256"
fi
ok "parity doc embeds plist hash"

python3 - "$PLIST" "$CSV" <<'PY'
import csv, plistlib, sys
plist_path, csv_path = sys.argv[1], sys.argv[2]
keys = plistlib.loads(open(plist_path, "rb").read())
n_plist = len(keys)
rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
n_csv = len(rows)
print(f"OK: plist_keys={n_plist} csv_rows={n_csv}")
if n_plist != 158 or n_csv != 158 or n_plist != n_csv:
    print(f"FAIL: counts want 158 (plist={n_plist} csv={n_csv})", file=sys.stderr)
    sys.exit(1)
bad = [r.get("command") for r in rows if (r.get("runtime_status") or "").strip() != "PENDING_USER_DEVICE"]
if bad:
    print("FAIL: runtime_status not PENDING_USER_DEVICE for:", bad[:20], file=sys.stderr)
    sys.exit(1)
print("OK: all 158 runtime_status=PENDING_USER_DEVICE")
# identity optional sanity
idents = {(r.get("identity_status") or "").strip() for r in rows}
print(f"OK: identity_status values={sorted(idents)}")
PY

echo "ACCEPT: validate_catalogue passed (pre-device)"
exit 0
