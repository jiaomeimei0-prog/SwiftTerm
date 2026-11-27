# toolvip1.top — trạng thái kết nối (2026-11-28 00:26 giờ Việt Nam)

## Kết quả công khai (trình duyệt thật)

| URL | DNS | Trình duyệt | Ảnh |
|-----|-----|-------------|-----|
| `https://toolvip1.top/` | Có (Cloudflare A/AAAA) | `ERR_CONNECTION_CLOSED` — đóng kết nối lúc TLS | `toolvip1-top-connection-closed-2026-11-28.webp` |
| `https://www.toolvip1.top/` | NXDOMAIN | `DNS_PROBE_FINISHED_NXDOMAIN` | `www-toolvip1-top-nxdomain-2026-11-28.webp` |

Không thấy trang SwiftTerm, không thấy Error 1033, không thấy Hello World, không thấy màn hình đăng nhập Cloudflare Access trong lần probe này — kết nối bị cắt trước HTTP.

JSON: `Docs/evidence/toolvip1-public-probe-2026-11-28.json`

## Vì sao chưa gắn được domain từ agent

1. **GitHub Actions secrets trống.** Log run `45821872722` (main) ghi `CLOUDFLARE_API_TOKEN:` và `CLOUDFLARE_ACCOUNT_ID:` rỗng → bước Deploy thoát với lỗi cố ý.
2. **Cursor đã có secret cùng tên (personal)** nhưng giá trị **không** vào shell của VM và **không** tự đồng bộ sang GitHub Actions.
3. **My Machines worker = 0.** Không thể chạy `cloudflared` / `wrangler` trên PC người dùng từ agent.
4. Agent **không** ghi được GitHub secret (`gh secret` / `workflow dispatch` → HTTP 403, integration read-only).
5. VM không hoàn tất TLS tới `api.cloudflare.com` / `toolvip1.top` (ClientHello rồi `SSL_ERROR_SYSCALL`), dù DNS resolve được.

## Việc đúng một lần để mở khóa

Trên GitHub repo `jiaomeimei0-prog/SwiftTerm` → **Settings → Secrets and variables → Actions** thêm:

| Secret | Nguồn giá trị |
|--------|----------------|
| `CLOUDFLARE_API_TOKEN` | Token Cloudflare (Pages Edit + Zone DNS Edit). Cursor Secrets đã có tên này — copy sang GitHub, **không** dán vào chat. |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID trên dashboard Cloudflare. Cursor Secrets đã có tên này. |

Sau đó chạy workflow **Cloudflare Pages (Web WASM)** (`workflow_dispatch`) trên nhánh có `CUSTOM_DOMAIN: toolvip1.top` (ví dụ `cursor/audit-command-inventory-45fd` hoặc `main` sau khi merge PR #29).

Script cục bộ khi secret đã có trong môi trường:

```bash
bash scripts/prepare-cloudflare-web.sh
bash scripts/deploy-toolvip1-pages.sh
```

## Việc Cloudflare Dashboard (song song)

1. DNS apex `toolvip1.top` → CNAME/alias tới project Pages `swiftterm-web` (hoặc để Pages tự gắn sau `wrangler pages domain add`).
2. Thêm bản ghi `www` nếu cần `www.toolvip1.top` (hiện NXDOMAIN).
3. Tắt Cloudflare Access cho hostname demo công khai nếu còn app Zero Trust trên apex.
4. SSL/TLS mode phù hợp (Full) — kết nối hiện đóng giữa ClientHello cho thấy hostname có thể chưa có chứng chỉ/origin sẵn sàng.
