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

raw = plistlib.loads(open(plist_path, "rb").read())
# Blocker 3: shape — flat dict[str] → catalogue entry (list values OK).
if not isinstance(raw, dict):
    print(f"FAIL: plist root is {type(raw).__name__}, want flat dict", file=sys.stderr)
    sys.exit(1)
bad_keys = [k for k in raw if not isinstance(k, str)]
if bad_keys:
    print(f"FAIL: non-string plist keys: {bad_keys[:10]}", file=sys.stderr)
    sys.exit(1)
plist_names = set(raw.keys())
n_plist = len(plist_names)
print(f"OK: plist shape=flat dict[str] keys={n_plist}")

rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
n_csv = len(rows)
fieldnames = list(rows[0].keys()) if rows else []
# Blocker 1: schema C — runtime_status is authoritative; user_* may also exist.
if "runtime_status" not in fieldnames:
    print(
        "FAIL: CSV missing column runtime_status "
        f"(have {fieldnames})",
        file=sys.stderr,
    )
    sys.exit(1)
print(
    "OK: CSV schema has runtime_status"
    + (" + user_observed_output/user_pass_fail" if "user_pass_fail" in fieldnames else "")
)

print(f"OK: plist_keys={n_plist} csv_rows={n_csv}")
if n_plist != 158 or n_csv != 158:
    print(f"FAIL: counts want 158 (plist={n_plist} csv={n_csv})", file=sys.stderr)
    sys.exit(1)

# Blocker 2: cross-check command names ↔ plist keys (not counts alone).
csv_names = []
missing_cmd = []
for i, r in enumerate(rows, 1):
    cmd = (r.get("command") or "").strip()
    if not cmd:
        missing_cmd.append(i)
        continue
    csv_names.append(cmd)
if missing_cmd:
    print(f"FAIL: empty command at CSV rows {missing_cmd[:10]}", file=sys.stderr)
    sys.exit(1)
if len(csv_names) != len(set(csv_names)):
    from collections import Counter
    dups = [n for n, c in Counter(csv_names).items() if c > 1]
    print(f"FAIL: duplicate CSV commands: {dups[:20]}", file=sys.stderr)
    sys.exit(1)
csv_set = set(csv_names)
only_csv = sorted(csv_set - plist_names)
only_plist = sorted(plist_names - csv_set)
if only_csv or only_plist:
    print(f"FAIL: command↔plist mismatch only_csv={only_csv[:20]} only_plist={only_plist[:20]}", file=sys.stderr)
    sys.exit(1)
print("OK: CSV command set == plist key set (158)")

bad = [r.get("command") for r in rows if (r.get("runtime_status") or "").strip() != "PENDING_USER_DEVICE"]
if bad:
    print("FAIL: runtime_status not PENDING_USER_DEVICE for:", bad[:20], file=sys.stderr)
    sys.exit(1)
print("OK: all 158 runtime_status=PENDING_USER_DEVICE")
# Pre-device: user evidence columns must stay empty (anti-fake).
for col in ("user_observed_output", "user_pass_fail"):
    if col not in fieldnames:
        continue
    filled = [r.get("command") for r in rows if (r.get(col) or "").strip()]
    if filled:
        print(f"FAIL: {col} pre-filled for {filled[:10]} (must be empty until device)", file=sys.stderr)
        sys.exit(1)
idents = {(r.get("identity_status") or "").strip() for r in rows}
print(f"OK: identity_status values={sorted(idents)}")
PY

echo "ACCEPT: validate_catalogue passed (pre-device)"
exit 0
