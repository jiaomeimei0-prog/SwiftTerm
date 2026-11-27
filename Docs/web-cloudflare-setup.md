# Setup Web WASM trên Cloudflare

**Mục tiêu:** chạy demo Canvas SwiftTerm (HTTP/HTTPS) qua Cloudflare.  
**Không phải** a-Shell iOS. Demo = stream local trong browser, **không** PTY/shell.

---

## Giới hạn quan trọng

| Artifact | Size | Cloudflare Pages |
|----------|------|------------------|
| `swiftterm-embedded.wasm` | ~0.9 MiB | **OK** — dùng mặc định |
| `swiftterm-full.wasm` | ~54 MiB | **Vượt** giới hạn file Pages (~25 MiB) → dùng **Tunnel** hoặc **R2** |

HTTPS: Cloudflare Pages/Tunnel terminate TLS giúp bạn (edge HTTPS).

---

## A. Deploy Cloudflare Pages (khuyến nghị)

### 1. Một lần trên Cloudflare Dashboard

1. Tạo API Token (Edit token / Create Custom Token) với tối thiểu:
   - **Account** → Cloudflare Pages → **Edit**
   - **Account** → Account Settings → **Read**
   - **Account** → Workers Scripts → **Edit** (để xóa Worker `swiftterm` / Workers Builds Hello World)
   - **Zone** `toolvip1.top` → Zone → **Read**
   - **Zone** `toolvip1.top` → DNS → **Edit** ← bắt buộc để agent/CI tự tạo CNAME apex (thiếu quyền này → NXDOMAIN / 403 DNS API)
2. Lấy **Account ID** (sidebar Overview) — **không** phải Zone ID.
3. (Tuỳ chọn) tạo sẵn Pages project tên `swiftterm-web`.

### 2. Secrets trên GitHub (`jiaomeimei0-prog/SwiftTerm`)

| Secret | Giá trị |
|--------|---------|
| `CLOUDFLARE_API_TOKEN` | token vừa tạo (Roll lại nếu thiếu DNS:Edit / Workers Scripts:Edit) |
| `CLOUDFLARE_ACCOUNT_ID` | account id |

### 3. Deploy

- **CI:** push `main` (đổi `Web/**`) hoặc chạy workflow **Cloudflare Pages (Web WASM)** (`workflow_dispatch`).  
- **Local:**

```sh
# Cần Web/dist (build hoặc artifact CI)
scripts/build-wasm.sh embedded --browser --release   # hoặc copy artifact
bash scripts/prepare-cloudflare-web.sh
cd Web/cloudflare && npm install
export CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=...
npm run deploy
```

Site output: `Web/cloudflare/site/` · config: `Web/cloudflare/wrangler.toml`.

URL dạng: `https://swiftterm-web.<account>.pages.dev/`

### Custom domain: `toolvip1.top`

**Trạng thái (2026-11-28):** `https://toolvip1.top` đã phục vụ **SwiftTerm WASM (Cloudflare)** (xác minh user device). Evidence: `Docs/evidence/toolvip1-user-verify-swiftterm-2026-11-28.md`.

**Bắt buộc** GitHub Actions secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` —
nếu thiếu, job deploy **fail** (không còn success giả).

Sau khi secrets có:

```sh
bash scripts/cloudflare-connect-domain.sh toolvip1.top www.toolvip1.top
# hoặc CI: workflow Cloudflare Pages (Web WASM)
bash scripts/cloudflare-disable-worker-swiftterm.sh   # dọn Worker/Workers Builds "swiftterm"
```

**Workers Builds `swiftterm`:** nếu GitHub vẫn hiện check fail `Workers Builds: swiftterm`, xóa script Worker đó (script trên) hoặc Dashboard → Workers → `swiftterm` → Settings → xóa / ngắt GitHub Builds. Không để custom domain Worker đè Pages.

**Access:** Zero Trust → Applications → tắt bảo vệ hostname demo (public WASM).

**DNS lỗi thường gặp:** apex không có A/CNAME → Chrome `DNS_PROBE_FINISHED_NXDOMAIN`. Thêm CNAME `@` → `swiftterm-web.pages.dev` (Proxied), hoặc cấp token **DNS:Edit** rồi chạy lại claim script.

Tạm thời (đã chứng minh): Quick Tunnel `*.trycloudflare.com` — không thay custom domain.

### Quick Tunnel từ máy Windows (vào bằng điện thoại ngay)

Không cần sửa DNS `toolvip1.top`. Trên PC (đã clone repo + chạy được local):

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\SwiftTerm\scripts\serve-via-cloudflare-tunnel.ps1"
```

Script mở `http.server` + `cloudflared tunnel` và in URL `https://….trycloudflare.com` —
mở URL đó trên điện thoại (4G cũng được).

---

## B. Cloudflare Tunnel (full WASM / máy local)

Khi cần **full** wasm hoặc serve từ laptop/Windows:

```sh
# Repo root — đã có Web/dist (full + embedded)
python3 -m http.server 8000
# Mở: http://127.0.0.1:8000/Web/example/?variant=embedded
#     http://127.0.0.1:8000/Web/example/          (full, nếu có file)

# Tunnel (cài cloudflared, login Cloudflare):
cloudflared tunnel --url http://127.0.0.1:8000
```

Gán hostname cố định trong Zero Trust → Networks → Tunnels nếu cần domain của bạn.

---

## C. HTTP local (không Cloudflare)

```sh
# Từ root monorepo, với Web/dist đã chuẩn bị:
python3 -m http.server 8000
# → http://127.0.0.1:8000/Web/example/?variant=embedded
```

---

## File trong repo

| Path | Vai trò |
|------|---------|
| `Web/cloudflare/site/` | Static site Pages (embedded) |
| `Web/cloudflare/wrangler.toml` | Wrangler Pages config |
| `scripts/prepare-cloudflare-web.sh` | Ghép site từ `Web/dist` |
| `.github/workflows/cloudflare-pages-web.yml` | Build embedded + deploy |

PTY/shell trên Windows vẫn theo [`host-ui-backend-web-windows.md`](host-ui-backend-web-windows.md) (WebSocket → WSL/remote) — ngoài scope Pages demo.
