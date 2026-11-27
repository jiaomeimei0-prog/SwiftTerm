# L4 — Chạy catalogue 158 lệnh trên thiết bị

**Trạng thái:** `PENDING_USER_DEVICE`  
Agent Cloud **không** có iPhone/iPad/Simulator → không thể tự PASS L4. Bạn chạy script dưới đây trên app a-Shell rồi gửi log.

## Điều kiện

1. Pin `Apps/a-Shell` = commit có `scripts/verify_command_catalogue_158.sh` (sau merge a-shell#8, `e95741b8…`).
2. Build & cài **a-Shell full** (có `Resources/commandDictionary.plist` 158 lệnh) lên iPhone/iPad hoặc Simulator.
3. Copy script vào thư mục Documents của app (hoặc mở repo trong a-Shell nếu bạn sync mã nguồn).

## Lệnh trên thiết bị

```sh
# Trong a-Shell:
cd Documents   # hoặc thư mục chứa script
sh verify_command_catalogue_158.sh
# Kỳ vọng cuối file:
# ACCEPT: all 158 catalogue names present in help -l
```

Nguồn script trong monorepo:

`Apps/a-Shell/scripts/verify_command_catalogue_158.sh`

## Ghi kết quả

1. Copy toàn bộ stdout/stderr vào  
   `Docs/evidence/command-158-device-run-YYYY-MM-DD.txt`
2. Cập nhật `Docs/command-158-device-matrix-PENDING.csv`:
   - `runtime_status` → `PASS_DEVICE` hoặc `FAIL_DEVICE`
   - `user_observed_output` / `user_pass_fail`
3. Đổi tên file PENDING → bỏ `PENDING` chỉ khi có log device thật.

## Không tính là L4

- Host E2E `scripts/e2e_acceptance_host.sh` (L1)
- Demo web `https://toolvip1.top` (WASM canvas, không có ios_system 158 lệnh)
