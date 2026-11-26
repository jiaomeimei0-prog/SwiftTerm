# Báo cáo test kiểm tra chức năng — 2026-11-26

Timezone ghi nhận: Asia/Bangkok (UTC+7). Timestamp máy agent = UTC.

## 1. SwiftTerm lõi (host)

| ID | Chức năng | Cách kiểm | Kết quả agent | Verdict |
|----|-----------|-----------|---------------|---------|
| ST-01 | Pin SoT / submodule a-Shell | `e2e_acceptance_host.sh` / gitlink | PASS (báo cáo trước) | ĐẠT host |
| ST-02 | HostHelpers 20 API | static scan | PASS | ĐẠT host |
| ST-03 | Call-site a-Shell ↔ helpers | static scan | PASS | ĐẠT host |
| ST-04 | WASM embed demo load | curl + browser | PASS local+CF | ĐẠT web demo |
| ST-05 | `xcodebuild` / device UI | cần Mac | SKIP | CHƯA |

## 2. Cloudflare kết nối thực tế

| ID | Chức năng | Lệnh | Kết quả | Verdict |
|----|-----------|------|---------|---------|
| CF-01 | Local serve site | `python3 -m http.server 8765 --bind 127.0.0.1` | index 200, wasm 200 | ĐẠT |
| CF-02 | Quick Tunnel | `cloudflared tunnel --url http://127.0.0.1:8765` | URL `https://folks-assumed-met-engine.trycloudflare.com` | ĐẠT |
| CF-03 | Index qua CF | `curl …/ ` | HTTP/2 200, `server: cloudflare` | ĐẠT |
| CF-04 | WASM qua CF | `curl …/pkg/swiftterm-embedded.wasm` | 200, 909857 bytes | ĐẠT |
| CF-05 | Browser mở URL CF | computerUse Chrome | PASS — title đúng, Live stream chạy, wasm 200 | **ĐẠT** |
| CF-06 | Phiên không tự đóng | để process chạy | pid cloudflared + python còn sống | ĐẠT trên agent host |

Evidence: `Docs/evidence/cloudflare-quick-tunnel-evidence.md`

## 3. a-Shell 158 lệnh

| ID | Chức năng | Kết quả agent | Verdict |
|----|-----------|---------------|---------|
| AS-01 | Catalogue = 158 keys trong plist | PASS identity | ĐẠT source |
| AS-02 | Script `verify_command_catalogue_158.sh` tồn tại | PASS file | ĐẠT artifact |
| AS-03 | `help -l` liệt kê đủ 158 trên device | chưa chạy device | **PENDING_USER** |
| AS-04 | Smoke `echo/true/pwd/uname/...` trên device | chưa chạy device | **PENDING_USER** |
| AS-05 | Toàn bộ 158 runtime manufacturer-match | chưa | **PENDING_USER** |

Ma trận: `Docs/command-158-device-matrix-PENDING.csv` (158 dòng `PENDING_USER_DEVICE`).

## 4. Ranh giới chức năng (để đối chiếu đúng)

- **PASS CF / WASM** ≠ PASS lệnh `ls`/`curl`/`python` của a-Shell.
- **PASS host HostHelpers** ≠ PASS interactive trên iPhone.
- Chỉ khi bạn điền CSV và xác nhận mới đổi runtime 158 sang PASS.

## 5. Kết luận chức năng tại thời điểm báo cáo

- Web + Cloudflare + SwiftTerm demo: **đã chạy thật**, kèm lệnh/kết quả.
- 158 a-Shell runtime: **chưa nghiệm thu** — chờ bạn chạy trên thiết bị và đối chiếu.
