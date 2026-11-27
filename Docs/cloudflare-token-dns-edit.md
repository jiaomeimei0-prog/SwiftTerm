# Cập nhật CLOUDFLARE_API_TOKEN — DNS:Edit + Workers Scripts:Edit

CI hiện deploy Pages được nhưng **Zone DNS API trả 10000/403** với token đang lưu trên GitHub. Vì vậy agent không tự tạo CNAME apex; bạn đã thêm DNS tay để `toolvip1.top` lên được.

## Việc bạn cần làm (một lần)

1. Cloudflare → **My Profile** → **API Tokens** → token đang dùng (vd. `acc`) → **Edit** hoặc **Roll**.
2. Thêm / giữ quyền:
   - Account · **Cloudflare Pages: Edit**
   - Account · **Account Settings: Read**
   - Account · **Workers Scripts: Edit**
   - Zone `toolvip1.top` · **Zone: Read**
   - Zone `toolvip1.top` · **DNS: Edit**
3. Copy chuỗi token mới → GitHub  
   `jiaomeimei0-prog/SwiftTerm` → Settings → Secrets → Actions → Update `CLOUDFLARE_API_TOKEN`.
4. (Không bắt buộc) Run workflow **Cloudflare Pages (Web WASM)** để xác nhận DNS API hết 403 và Worker `swiftterm` bị xóa.

**Không** dán token vào chat.
