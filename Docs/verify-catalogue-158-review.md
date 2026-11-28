# A2a — Review `verify_command_catalogue_158.sh`

**Script:** `Apps/a-Shell/scripts/verify_command_catalogue_158.sh`  
**Pin a-Shell:** `e95741b8`  
**Reviewed:** 2026-11-28

## Schema / mismatch check

| Check | Result |
|-------|--------|
| Embedded `EXPECTED` token count | **158** |
| `commandDictionary.plist` key count | **158** |
| Keys in plist not in EXPECTED | **[]** (empty) |
| Names in EXPECTED not in plist | **[]** (empty) |
| Sorted order equal | **Yes** |
| Stop condition “mismatch schema” | **Không kích hoạt** — script khớp plist |

## Hành vi (không sửa script)

- Chạy **trên device/Simulator trong app** (`help -l` là builtin a-Shell).
- Smoke subset: `echo env date pwd uname whoami true ls cat head wc`.
- Exit 0 chỉ khi 158 tên có trong `help -l` và smoke không FAIL.

## Kết luận A2a

**PASS review** — không viết lại; tiếp tục dùng cho B3 trên device.

## CSV schema (chốt cho A2b)

| Cột | Bắt buộc pre-device |
|-----|---------------------|
| `runtime_status` | Có — toàn `PENDING_USER_DEVICE` |
| `user_observed_output` / `user_pass_fail` | Có trong CSV; **trống** đến device |
| `command` | Phải **trùng set** với key `commandDictionary.plist` (không chỉ đếm 158) |
