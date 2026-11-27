# Cập nhật CLOUDFLARE_API_TOKEN — DNS:Edit + Workers Scripts + Builds

CI deploy Pages được nhưng **Zone DNS API** từng trả `10000/403`, và check GitHub **`Workers Builds: swiftterm`** vẫn fail khi Worker/Git trigger còn sống. Agent không tự Roll secret — bạn cập nhật một lần trên dashboard.

## Việc bạn cần làm (một lần)

1. Cloudflare → **My Profile** → **API Tokens** → token đang dùng (vd. `acc`) → **Edit** hoặc **Roll**.
   - Dùng **user-owned** token (My Profile), không phải account-owned — Workers Builds API từ chối account token.
2. Thêm / giữ quyền:
   - Account · **Cloudflare Pages: Edit**
   - Account · **Account Settings: Read**
   - Account · **Workers Scripts: Edit**
   - Account · **Workers Builds Configuration: Edit** (Workers CI Write — xóa Git trigger)
   - Zone `toolvip1.top` · **Zone: Read**
   - Zone `toolvip1.top` · **DNS: Edit**
3. Copy chuỗi token mới → GitHub  
   `jiaomeimei0-prog/SwiftTerm` → Settings → Secrets → Actions → Update `CLOUDFLARE_API_TOKEN`.
4. Chạy lại workflow **Cloudflare Pages (Web WASM)** (`workflow_dispatch` hoặc push `main`).
   - Script `scripts/cloudflare-disable-worker-swiftterm.sh` sẽ: xóa Builds triggers → bỏ Worker domains → xóa script `swiftterm`.
5. Nếu check `Workers Builds: swiftterm` vẫn xuất hiện: Dashboard → Workers → `swiftterm` → Settings → Builds → **Disconnect**, rồi xóa Worker.

**Không** dán token vào chat.

## Kiểm chứng nhanh sau khi Roll

| Kỳ vọng | Ý nghĩa |
|---------|---------|
| Pages deploy + claim domain success | Token Pages OK |
| Log CI có `CLEAN: worker script 'swiftterm' gone` | Worker đã xóa |
| Push `main` **không** còn check fail `Workers Builds: swiftterm` | Builds trigger đã ngắt |
| DNS API không còn 403 khi claim CNAME | Zone DNS:Edit OK |
