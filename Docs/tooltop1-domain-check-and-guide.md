# Kiểm tra `tooltop1` + hướng dẫn cụ thể (kèm phương án khi không làm được)

- Probe lúc: **2026-11-26 19:25:07 Asia/Bangkok** (`2026-11-26T12:25:07Z`)
- Resolver: `dig @1.1.1.1`
- Evidence thô: `Docs/evidence/domain-tooltop1-vip-probe.md` (bản trước) + bảng dưới (bản mới)

---

## 1. Kết quả kiểm tra rõ ràng

| Tên | DNS | HTTPS | RDAP / ghi chú | Kết luận |
|-----|-----|-------|----------------|----------|
| **tooltop1.vip** | **NXDOMAIN** (không A/AAAA/NS) | không resolve | nic.vip **404 Not found** | **Chưa đăng ký** |
| www.tooltop1.vip | NXDOMAIN | không resolve | — | Không tồn tại |
| **tooltop1.top** | **NXDOMAIN** | không resolve | rdap.nic.top không resolve từ host probe | **Chưa thấy DNS** |
| **toolvip1.top** | NOERROR · A `104.21.95.42` `172.67.142.251` · NS `jarred`/`raegan`.ns.cloudflare.com | **302 → Cloudflare Access Sign-in** | `protected: true` | Domain **có**, nhưng **khóa Access** — chưa phục vụ SwiftTerm |
| www.toolvip1.top | NXDOMAIN | không resolve | — | Chưa gắn www |
| toolvip1.vip | NXDOMAIN | không resolve | nic.vip 404 | Chưa đăng ký |

**Phân biệt tên (dễ nhầm):**

| Bạn gõ | Khả năng | Thực tế DNS |
|--------|----------|-------------|
| `tooltop1.vip` | tên bạn yêu cầu | **không tồn tại** |
| `toolvip1.top` | domain đang trên Cloudflare | **tồn tại + Access khóa** |
| `tooltop1.top` / `toolvip1.vip` | biến thể | **không tồn tại** |

**Kết luận ngắn:** Hiện **không có hostname `tooltop1*` nào** đang phục vụ site. Chỉ `toolvip1.top` sống trên Cloudflare nhưng bị Access chặn trang đăng nhập — **không phải** demo SwiftTerm WASM.

---

## 2. Hướng dẫn cụ thể — chọn đúng 1 đường

### Đường A — Bạn muốn đúng tên `tooltop1.vip`

Làm lần lượt:

1. **Mua/đăng ký** `tooltop1.vip` tại registrar (GoDaddy, Namecheap, Cloudflare Registrar, …).  
   - Kiểm tra trước khi trả tiền: mở https://rdap.nic.vip/domain/tooltop1.vip — phải **không còn 404**.
2. Trong Cloudflare Dashboard → **Add a site** → nhập `tooltop1.vip` → lấy 2 nameserver Cloudflare.  
3. Ở registrar → đổi NS sang đúng 2 NS Cloudflare → chờ Active (thường vài phút–vài giờ).  
4. GitHub repo `jiaomeimei0-prog/SwiftTerm` → **Settings → Secrets and variables → Actions** → thêm:
   - `CLOUDFLARE_API_TOKEN` (quyền Pages Edit + Zone DNS Edit)
   - `CLOUDFLARE_ACCOUNT_ID` (Account ID trên dashboard)
5. Chạy workflow **Cloudflare Pages (Web WASM)** → `Run workflow`, **hoặc** trên máy đã có token:

```powershell
# Windows — sau khi clone repo vào Documents\SwiftTerm
cd $env:USERPROFILE\Documents\SwiftTerm
# (token chỉ set trong PowerShell của bạn — không gửi chat)
$env:CLOUDFLARE_API_TOKEN="…"
$env:CLOUDFLARE_ACCOUNT_ID="…"
bash scripts/prepare-cloudflare-web.sh
bash scripts/cloudflare-connect-domain.sh tooltop1.vip www.tooltop1.vip
```

6. **Nghiệm thu bắt buộc** (chỉ PASS khi đúng):

```sh
curl -sS -D- -o /tmp/idx.html -w "http=%{http_code}\n" https://tooltop1.vip/
# PASS: HTTP 200 + body có chữ "SwiftTerm WASM"
# FAIL: NXDOMAIN / 000 / 302 Access login / trang trống
```

Mở trình duyệt: `https://tooltop1.vip/` — phải thấy terminal canvas SwiftTerm.

---

### Đường B — Bạn thực ra đang dùng `toolvip1.top` (domain đã có)

1. Cloudflare → **Zero Trust** → **Access** → **Applications** → tìm app gắn `toolvip1.top` → **Delete** hoặc tắt (public demo không dùng Access).  
2. Thêm 2 GitHub secrets như bước 4 Đường A.  
3. Deploy + gắn domain:

```sh
bash scripts/cloudflare-connect-domain.sh toolvip1.top www.toolvip1.top
```

4. Nghiệm thu:

```sh
curl -sS -D- -o /tmp/idx.html -w "http=%{http_code}\n" https://toolvip1.top/
# PASS: 200 + "SwiftTerm WASM" — KHÔNG được 302 tới *.cloudflareaccess.com
```

---

### Đường C — Chưa mua domain / chưa có secret / Access không tắt được

Dùng **Quick Tunnel** (đã chứng minh chạy được; **không** phải custom domain):

**Trên máy Windows của bạn** (hai cửa sổ HTTP + tunnel **giữ mở**):

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
powershell -ExecutionPolicy Bypass -File .\scripts\windows-persistent-e2e.ps1
```

- Copy URL `https://….trycloudflare.com` in ra ở cửa sổ cloudflared.  
- Mở URL đó trên trình duyệt / điện thoại.  
- Nghiệm thu: thấy **SwiftTerm WASM (Cloudflare)** + Live stream chạy.

Tunnel agent từng chạy: `https://folks-assumed-met-engine.trycloudflare.com` (có thể đã hết hạn — chạy lại script trên PC để lấy URL mới).

---

## 3. Nếu không thực hiện được — làm gì tiếp

| Tình huống | Dấu hiệu | Việc làm ngay |
|------------|----------|---------------|
| Domain chưa mua | `dig` = NXDOMAIN · RDAP 404 | Đăng ký domain **hoặc** chuyển sang Đường B (`toolvip1.top`) **hoặc** Đường C (tunnel) |
| Quên / không thêm GitHub secret | Workflow Cloudflare Pages **fail** với `CLOUDFLARE_*` trống | Settings → Secrets → thêm 2 secret → Run workflow lại |
| Vẫn thấy trang Sign in Cloudflare | `curl` = 302 · `protected: true` | Zero Trust → xóa Access app; không PASS nếu còn login |
| `www` không vào được | www = NXDOMAIN | Pages → Custom domains → Add `www.…` hoặc `wrangler pages domain add www.…` |
| Apex chỉ AAAA `100::` | điện thoại/PC không vào | DNS zone: xóa `100::`; để Pages tạo lại bản ghi |
| Không có quyền Cloudflare/GitHub | không tạo token / không vào Zero Trust | Dùng **Đường C** Quick Tunnel trên PC; nhờ chủ tài khoản làm A/B |
| Agent Cloud không gắn domain hộ | secret không inject vào VM | Bạn (chủ tài khoản) làm bước secret + DNS; agent chỉ chuẩn bị script/CI |

**Không được gọi “hoàn thành domain” khi:**

- còn NXDOMAIN, hoặc  
- còn 302 Access, hoặc  
- chỉ có báo cáo/docs mà chưa `curl`/browser ra SwiftTerm 200.

---

## 4. Checklist đối chiếu (bạn tự tick)

- [ ] Đã chọn đúng tên: `tooltop1.vip` **hoặc** `toolvip1.top`  
- [ ] `dig @1.1.1.1 <domain> A` → có IP Cloudflare (không NXDOMAIN)  
- [ ] GitHub secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` đã có  
- [ ] Access đã tắt (không còn Sign-in)  
- [ ] `curl https://<domain>/` → **200** + body có `SwiftTerm WASM`  
- [ ] Browser mở domain → thấy terminal / Live stream  

Nếu dừng ở Đường C: tick URL `trycloudflare.com` 200 thay cho custom domain — ghi rõ **chưa xong custom domain**.
