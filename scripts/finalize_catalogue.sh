#!/usr/bin/env bash
# finalize_catalogue.sh — chạy SAU khi user điền CSV từ device.
# Không tự điền runtime. Exit 1 nếu fail% > ngưỡng (mặc định 5%).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="${PLIST:-$ROOT/Apps/a-Shell/Resources/commandDictionary.plist}"
CSV="${CSV:-$ROOT/Docs/command-158-device-matrix-PENDING.csv}"
FAIL_PCT_MAX="${FAIL_PCT_MAX:-5}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

[[ -f "$PLIST" ]] || fail "missing plist: $PLIST"
[[ -f "$CSV" ]] || fail "missing csv: $CSV"

python3 - "$PLIST" "$CSV" "$FAIL_PCT_MAX" <<'PY'
import csv, plistlib, sys
plist_path, csv_path, fail_max_s = sys.argv[1], sys.argv[2], sys.argv[3]
fail_max = float(fail_max_s)
keys = set(plistlib.loads(open(plist_path, "rb").read()).keys())
rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
if len(rows) != 158:
    print(f"FAIL: csv rows={len(rows)} want 158", file=sys.stderr)
    sys.exit(1)

pending = [r["command"] for r in rows if (r.get("runtime_status") or "").strip() == "PENDING_USER_DEVICE"]
if pending:
    print(f"FAIL: still PENDING_USER_DEVICE ({len(pending)}): {pending[:15]}...", file=sys.stderr)
    sys.exit(1)
print("OK: no PENDING_USER_DEVICE left")

# Commands in plist that failed on device
fail_cmds = []
pass_cmds = []
unknown = []
for r in rows:
    cmd = (r.get("command") or "").strip()
    status = (r.get("runtime_status") or "").strip()
    user = (r.get("user_pass_fail") or "").strip().upper()
    if cmd not in keys:
        print(f"WARN: csv command not in plist: {cmd}")
    if status == "FAIL_DEVICE" or user == "FAIL":
        fail_cmds.append(cmd)
    elif status == "PASS_DEVICE" or user == "PASS":
        pass_cmds.append(cmd)
    else:
        unknown.append((cmd, status, user))

print(f"OK: PASS-like={len(pass_cmds)} FAIL-like={len(fail_cmds)} other={len(unknown)}")
if fail_cmds:
    print("FAIL_DEVICE commands:")
    for c in fail_cmds:
        print(f"  - {c}")

total = len(rows)
fail_pct = (100.0 * len(fail_cmds) / total) if total else 0.0
print(f"OK: fail_pct={fail_pct:.2f}% threshold={fail_max}%")
if fail_pct > fail_max:
    print(f"FAIL: fail% {fail_pct:.2f} > {fail_max}", file=sys.stderr)
    sys.exit(1)
if unknown:
    print("FAIL: unresolved runtime rows:", unknown[:20], file=sys.stderr)
    sys.exit(1)
print("ACCEPT: finalize_catalogue passed")
sys.exit(0)
PY
