#!/usr/bin/env bash
# build_noPython.sh — Mac + Xcode ONLY. DO NOT run on Linux Cloud Agent.
# Builds unsigned/signed archive for scheme a-Shell-noPython and verifies
# xcfs binary checksums against Package.swift after resolve.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASHELL="${ASHELL:-$ROOT/Apps/a-Shell}"
SCHEME="${SCHEME:-a-Shell-noPython}"
CONFIG="${CONFIG:-Release}"
OUT_DIR="${OUT_DIR:-$ROOT/build/noPython}"
DERIVED="${DERIVED:-$OUT_DIR/DerivedData}"
ARCHIVE_PATH="${ARCHIVE_PATH:-$OUT_DIR/${SCHEME}.xcarchive}"
EXPORT_DIR="${EXPORT_DIR:-$OUT_DIR/export}"
DEPLOYMENT_TARGET="${IPHONEOS_DEPLOYMENT_TARGET:-15.0}"

echo "=== build_noPython ==="
echo "ASHELL=$ASHELL"
echo "SCHEME=$SCHEME CONFIG=$CONFIG"
echo "DEPLOYMENT_TARGET=$DEPLOYMENT_TARGET"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: macOS + Xcode required (uname=$(uname -s)). Refusing to run." >&2
  exit 2
fi
command -v xcodebuild >/dev/null || { echo "ERROR: xcodebuild missing" >&2; exit 2; }
command -v swift >/dev/null || { echo "ERROR: swift missing" >&2; exit 2; }

[[ -d "$ASHELL/a-Shell.xcodeproj" ]] || { echo "ERROR: missing $ASHELL/a-Shell.xcodeproj" >&2; exit 1; }
[[ -f "$ASHELL/xcfs/Package.swift" ]] || { echo "ERROR: missing xcfs/Package.swift" >&2; exit 1; }

mkdir -p "$OUT_DIR" "$EXPORT_DIR"

echo "=== Resolve + verify binary checksums (canonical count=65) ==="
(
  cd "$ASHELL"
  ./downloadFrameworks.sh --jobs "${JOBS:-4}"
)

python3 - "$ASHELL/xcfs/Package.swift" <<'PY'
import re, pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text()
blocks = re.findall(
    r'\.binaryTarget\(\s*name:\s*"([^"]+)"\s*,\s*url:\s*"([^"]+)"\s*,\s*checksum:\s*"([^"]+)"\s*\)',
    text,
    re.S,
)
print(f"binaryTarget_count={len(blocks)}")
if len(blocks) != 65:
    print(f"WARN: expected 65 binaryTargets, found {len(blocks)}", file=sys.stderr)
for name, url, checksum in blocks:
    if len(checksum) != 64:
        print(f"FAIL: bad checksum length for {name}", file=sys.stderr)
        sys.exit(1)
print("OK: all binaryTarget checksum fields look like sha256 hex")
PY

# exportOptions — development + ad-hoc templates
DEV_PLIST="$OUT_DIR/exportOptions-development.plist"
ADHOC_PLIST="$OUT_DIR/exportOptions-ad-hoc.plist"
cat >"$DEV_PLIST" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key><string>development</string>
  <key>compileBitcode</key><false/>
  <key>signingStyle</key><string>automatic</string>
  <key>stripSwiftSymbols</key><true/>
  <key>thinning</key><string>&lt;none&gt;</string>
</dict>
</plist>
PLIST
cat >"$ADHOC_PLIST" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key><string>ad-hoc</string>
  <key>compileBitcode</key><false/>
  <key>signingStyle</key><string>automatic</string>
  <key>stripSwiftSymbols</key><true/>
  <key>thinning</key><string>&lt;none&gt;</string>
</dict>
</plist>
PLIST

EXPORT_METHOD="${EXPORT_METHOD:-development}"
case "$EXPORT_METHOD" in
  development) EXPORT_PLIST="$DEV_PLIST" ;;
  ad-hoc|adhoc) EXPORT_PLIST="$ADHOC_PLIST" ;;
  *) echo "ERROR: EXPORT_METHOD must be development|ad-hoc" >&2; exit 1 ;;
esac

# Avoid empty-array expansion under bash 3.2 + set -u (stock macOS).
echo "=== xcodebuild archive ==="
set +e
if [[ "${SIGNED:-0}" == "1" ]]; then
  echo "SIGNED=1 — using project/team signing (Configuration.xcconfig)"
  xcodebuild \
    -project "$ASHELL/a-Shell.xcodeproj" \
    -scheme "$SCHEME" \
    -configuration "$CONFIG" \
    -destination 'generic/platform=iOS' \
    -archivePath "$ARCHIVE_PATH" \
    -derivedDataPath "$DERIVED" \
    IPHONEOS_DEPLOYMENT_TARGET="$DEPLOYMENT_TARGET" \
    archive
else
  xcodebuild \
    -project "$ASHELL/a-Shell.xcodeproj" \
    -scheme "$SCHEME" \
    -configuration "$CONFIG" \
    -destination 'generic/platform=iOS' \
    -archivePath "$ARCHIVE_PATH" \
    -derivedDataPath "$DERIVED" \
    IPHONEOS_DEPLOYMENT_TARGET="$DEPLOYMENT_TARGET" \
    CODE_SIGNING_ALLOWED=NO \
    archive
fi
XC_EC=$?
set -e
echo "xcodebuild_archive_exit=$XC_EC"
[[ "$XC_EC" -eq 0 ]] || exit "$XC_EC"

if [[ "${SIGNED:-0}" == "1" ]]; then
  echo "=== xcodebuild -exportArchive ($EXPORT_METHOD) ==="
  set +e
  xcodebuild -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_DIR" \
    -exportOptionsPlist "$EXPORT_PLIST"
  EX_EC=$?
  set -e
  echo "xcodebuild_export_exit=$EX_EC"
  [[ "$EX_EC" -eq 0 ]] || exit "$EX_EC"
  IPA="$(find "$EXPORT_DIR" -name '*.ipa' | head -1)"
else
  echo "UNSIGNED build — skip exportArchive; archive at $ARCHIVE_PATH"
  IPA=""
fi

echo "=== artifacts ==="
if [[ -n "$IPA" && -f "$IPA" ]]; then
  SHA="$(shasum -a 256 "$IPA" | awk '{print $1}')"
  echo "ipa=$IPA"
  echo "ipa_sha256=$SHA"
else
  if [[ -d "$ARCHIVE_PATH" ]]; then
    # hash a stable file inside archive if present
    APP="$(find "$ARCHIVE_PATH/Products" -name '*.app' -type d | head -1 || true)"
    echo "archive=$ARCHIVE_PATH"
    echo "app=${APP:-none}"
    if [[ -n "${APP:-}" ]]; then
      echo "app_sha256=$(find "$APP" -type f | sort | xargs cat 2>/dev/null | shasum -a 256 | awk '{print $1}')"
    fi
  fi
fi

echo "ACCEPT: build_noPython finished exit=0"
exit 0
