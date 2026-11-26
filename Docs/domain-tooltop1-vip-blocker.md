# Kết nối domain — blocker thật (không báo cáo giả)

> **Đính chính (2026-11-26):** tên miền thật của dự án là **`toolvip1.top`**. `tooltop1.vip` là tên gõ nhầm, chưa đăng ký, và đã bị gỡ khỏi workflow/script. Tài liệu này được giữ lại như lịch sử điều tra, không phải hướng dẫn vận hành.

Cập nhật: **2026-11-26 18:59 Asia/Bangkok**  
Evidence lệnh: `Docs/evidence/domain-tooltop1-vip-probe.md`

## Kết quả lệnh thật

| Domain | DNS | HTTPS | Kết luận |
|--------|-----|-------|----------|
| **tooltop1.vip** | `NXDOMAIN` @1.1.1.1 · RDAP **404 Not found** | không resolve | **Chưa đăng ký** — không gắn được Pages/Tunnel |
| **toolvip1.top** | A + NS Cloudflare OK | **302 → Cloudflare Access Sign-in** | Domain sống nhưng **bị Access khóa**, không phải SwiftTerm |
| `*.trycloudflare.com` | OK | 200 WASM demo | Tunnel tạm — **không** phải custom domain |

GitHub Actions deploy gần nhất: secrets `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` **trống** → deploy fail (run `45803275310`).

## Việc bạn phải làm trên tài khoản Cloudflare / GitHub (agent không ghi được secret)

### A. Nếu đúng là **tooltop1.vip** (tên bạn yêu cầu)

1. Đăng ký domain `tooltop1.vip` tại registrar (hiện registry trả 404).  
2. Trỏ nameserver về Cloudflare (zone mới), hoặc CNAME về project Pages sau khi deploy.  
3. Thêm GitHub Actions secrets trên repo `jiaomeimei0-prog/SwiftTerm`:
   - `CLOUDFLARE_API_TOKEN` (Pages Edit + Zone DNS Edit)
   - `CLOUDFLARE_ACCOUNT_ID`
4. Chạy workflow **Cloudflare Pages (Web WASM)** (`workflow_dispatch`) hoặc:

```sh
export CLOUDFLARE_API_TOKEN=… CLOUDFLARE_ACCOUNT_ID=…
bash scripts/prepare-cloudflare-web.sh   # cần Web/dist
bash scripts/cloudflare-connect-domain.sh tooltop1.vip www.tooltop1.vip
```

### B. Nếu ý bạn là **toolvip1.top** (domain đang có trên Cloudflare)

1. Zero Trust → Access → **Applications**: xóa / tắt app bảo vệ `toolvip1.top` (public demo không dùng Access).  
2. Thêm 2 GitHub secrets như trên.  
3. Deploy + attach:

```sh
bash scripts/cloudflare-connect-domain.sh toolvip1.top www.toolvip1.top
```

Hoặc trên Windows (tunnel đặt tên, cửa sổ không đóng):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\serve-named-tunnel-domain.ps1 -Hostname toolvip1.top
```

### C. Nghiệm thu công khai (chỉ PASS khi lệnh này ra SwiftTerm)

```sh
curl -sS -D- -o /tmp/idx.html -w "http=%{http_code}\n" https://<domain>/
# Expect: HTTP 200, body chứa "SwiftTerm WASM"
# KHÔNG chấp nhận: 302 Access login, NXDOMAIN, connection refused
```

## Agent không thể hoàn tất một mình vì

1. Không có `CLOUDFLARE_*` trong shell / GitHub Actions (giá trị secret không inject vào VM).  
2. `tooltop1.vip` chưa tồn tại trên registry.  
3. `toolvip1.top` Access policy chỉ chủ tài khoản Zero Trust tắt được.
