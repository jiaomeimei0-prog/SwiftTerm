# Ma trận nghiệm thu 158 lệnh — PENDING thiết bị

- Generated: 2026-11-26T11:43:21Z UTC
- Identity: `Apps/a-Shell/Resources/commandDictionary.plist` = **158** keys (byte catalogue vs holzschu full dictionary)
- Runtime: **PENDING_USER_DEVICE** for all 158 until you paste observed output in the CSV
- CSV làm việc: `Docs/command-158-device-matrix-PENDING.csv`
- Script trên device: `Apps/a-Shell/scripts/verify_command_catalogue_158.sh`

## Quy tắc đối chiếu (không được sửa thành PASS giả)

| Cột | Ý nghĩa |
|-----|---------|
| identity_status | Catalogue có lệnh (source) — agent đã khóa |
| runtime_status | Chỉ đổi thành `PASS_DEVICE` sau khi **bạn** chạy trên a-Shell và ghi output |
| user_observed_output | Dán nguyên văn kết quả lệnh trên máy/thiết bị của bạn |
| user_pass_fail | `PASS` / `FAIL` do bạn điền |

## Ranh giới trung thực

- Cloudflare WASM demo (`*.trycloudflare.com`) = SwiftTerm terminal renderer — **không** chạy 158 lệnh ios_system.
- Windows PowerShell script chỉ phục vụ demo web + tunnel.
- 158 lệnh chỉ nghiệm thu runtime trong **app a-Shell** trên iPhone/iPad (hoặc Simulator Mac).

## Smoke tối thiểu (bạn chạy trong a-Shell)

```sh
help -l | wc -l
sh scripts/verify_command_catalogue_158.sh
echo hello
true; echo exit:$?
pwd
uname
whoami
date
ls
```

Điền kết quả vào CSV cột `user_observed_output` / `user_pass_fail`.
