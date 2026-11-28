# Phần B — User chạy trên Mac/device (AI soạn, không chạy)

## B1 — Build `.ipa` / archive

```sh
cd /path/to/SwiftTerm   # monorepo tip có scripts/
# Xcode 26.3 hoặc 27.1
./scripts/build_noPython.sh
# Có team signing:
SIGNED=1 EXPORT_METHOD=development ./scripts/build_noPython.sh
# Ad-hoc:
SIGNED=1 EXPORT_METHOD=ad-hoc ./scripts/build_noPython.sh
```

Artifact: `build/noPython/export/*.ipa` (khi SIGNED=1) hoặc `.xcarchive`.

## B2 — Cài lên device

```sh
./scripts/sign_and_deploy.sh --ipa build/noPython/export/YOUR.ipa --udid YOUR_UDID [--cert path.p12]
```

Nhắc: Apple ID free ~7 ngày; theo dõi `notAfter` của cert.

## B3 — Catalogue validate → device verify → finalize

```sh
# Trước device (host):
./scripts/validate_catalogue.sh

# Trên device (trong a-Shell):
sh verify_command_catalogue_158.sh
# Kỳ vọng: ACCEPT: all 158 catalogue names present in help -l

# Điền Docs/command-158-device-matrix-PENDING.csv
#   runtime_status: PASS_DEVICE | FAIL_DEVICE
#   user_observed_output / user_pass_fail
# KHÔNG để AI tự điền.

# Sau khi điền:
./scripts/finalize_catalogue.sh
# FAIL_PCT_MAX=5 ./scripts/finalize_catalogue.sh
```

## B4 — Review A5 nested bump

Đọc `Docs/swiftterm-nested-bump-plan-2026-11-28.md`.  
**31 commit > 30 → AI đã DỪNG.** Chỉ merge bump khi bạn duyệt PR nhỏ + test plan pass.

## B5 — Review docs

- `Docs/fork-registry.md` + `Docs/fork-registry.yaml`
- `Docs/dependency-audit.md`
- `Docs/verify-catalogue-158-review.md`
