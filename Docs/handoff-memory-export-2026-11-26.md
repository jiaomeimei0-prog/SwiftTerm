# HANDOFF / BỘ NHỚ CÔNG VIỆC — SwiftTerm + a-Shell (2026-11-26 ~21:55 Asia/Bangkok)

Dùng tài liệu này gửi AI/agent khác. Anti-fake: chỉ claim PASS khi có lệnh + kết quả; không đánh dấu 158 PASS nếu chưa xác nhận trên device.

---

## 1. Mục tiêu cuối cùng (Supreme acceptance)

Phải đạt **đồng thời**:

1. **158 lệnh a-Shell** khớp catalogue nhà sản xuất (`commandDictionary.plist`) — PASS runtime trên device người dùng (iOS/a-Shell), không chỉ khớp source.
2. **SwiftTerm-core E2E** (host + WASM/web) có evidence lệnh + kết quả.
3. **Cloudflare public bền vững** trên domain thật **`toolvip1.top`** (không phải `tooltop1.vip` — user chưa đăng ký tooltop1).
4. Browser verify public: body chứa SwiftTerm, **không** Error 1033 / Hello World / Cloudflare Access login.
5. Người dùng đối chiếu kết quả “manufacturer-matching” trước khi gọi “hoàn thành tuyệt đối”.
6. Mọi claim phải kèm lệnh + kết quả; không báo cáo giả.

---

## 2. Repos / nhánh / PR

| Repo | Path | Remote | Branch hiện tại (agent) | Ghi chú |
|------|------|--------|-------------------------|---------|
| SwiftTerm (SoT) | `/workspace` | `https://github.com/jiaomeimei0-prog/SwiftTerm` | `cursor/fix-named-tunnel-ps1-45fd` | tip `15a18a7` |
| a-Shell | `/agent/repos/a-shell` | `https://github.com/jiaomeimei0-prog/a-Shell.git` | `master` | submodule / fork |

- **PR chính đang mở:** [#28](https://github.com/jiaomeimei0-prog/SwiftTerm/pull/28) — Windows named-tunnel PS1 + bring-up/persistent/My Machines.
- Base: `main`.
- Commit tip: `15a18a7` — Fix Bugbot (diagnose port từ config; inline PATH tunnel; throw no-port; `-AsService` copy System profile; one-shot worker+tunnel).
- PR #27 đã merge (lịch sử trước đó).

---

## 3. Domain / Cloudflare (đã xảy ra thật)

| Mục | Giá trị |
|-----|---------|
| Domain thật | `toolvip1.top` (apex). `www.toolvip1.top` = NXDOMAIN |
| Domain sai / chưa đăng ký | `tooltop1.vip` |
| Named tunnel | `swiftterm-web` |
| Tunnel UUID | `b3fae273-5e2e-428c-aaff-7bfc20e441f5` |
| Sai tunnel từng dùng | `toolvip1-ssh` → Hello World |
| Worker DNS từng lỗi | `patient-pond-3427` → Hello World (đã/đang cần xóa Worker DNS, CNAME → `….cfargotunnel.com`) |
| Access từng lỗi | app `purple-frost-65fb` — cần xóa Access ở apex để khỏi login wall |
| Error 1033 | = `cloudflared` không chạy / tunnel down |
| WinError 10013 | bind port bị chặn → script auto chọn 8787+ |

**Public probe mới nhất (agent VM, ~21:53 ICT):**  
`https://toolvip1.top/` → `SSL_ERROR_SYSCALL` / HTTP 000 → **FAIL** (tunnel down).  
Evidence: `Docs/evidence/toolvip1-public-probe-2026-11-26-agent-vm.json`

Khi tunnel + HTTP origin từng chạy đúng: public từng hiện SwiftTerm. Tắt tunnel → 1033 / connection closed.

---

## 4. Đã đạt (có evidence)

- Catalogue 158 identity (plist) — PASS **source** (`Docs/command-158-device-matrix-PENDING.csv` vẫn PENDING device).
- Host E2E SwiftTerm / HostHelpers — PASS host (`Docs/e2e-acceptance-results.md`).
- Quick Tunnel + browser WASM — PASS trên agent (`Docs/evidence/cloudflare-quick-tunnel-evidence.md`).
- Windows PS1: sửa parse PS 5.1 (em-dash / `-#`), stderr WRN, auto-port, exact tunnel name, persistent install, Bugbot 4 fixes trên tip `15a18a7`.
- Scripts chính:
  - `scripts/serve-named-tunnel-domain.ps1`
  - `scripts/windows-bringup-toolvip1.ps1`
  - `scripts/windows-install-persistent-tunnel.ps1`
  - `scripts/diagnose-toolvip1.ps1`
  - `scripts/windows-start-my-machine-and-tunnel.ps1` ← one-shot worker + tunnel
- Docs: `Docs/acceptance-remaining-checklist.md`, `Docs/run-agent-on-your-windows-pc.md`, `Docs/supreme-acceptance-overview-2026-11-26.md`

---

## 5. Chưa đạt / nút thắt hiện tại

### Nút thắt #1 (CRITICAL) — Agent không điều khiển được PC user
- User đã tải **Use my computer / My Machines**.
- `list-self-hosted-workers` → **`workers: []`**.
- Cài app/CLI **≠** worker online. Cần process `agent worker start` **KEEP OPEN**.
- Không có worker → agent cloud **không thể** tự chạy lệnh trên Windows PC (chỉ sửa repo + probe public).

### Nút thắt #2 (CRITICAL) — `toolvip1.top` không bền
- Tunnel/origin trên PC đang tắt → public SSL fail / 1033.
- Cần chạy one-shot / persistent trên PC và giữ `cloudflared` sống.

### Nút thắt #3 — 158 runtime
- Không có iOS/a-Shell device trong agent VM.
- CSV vẫn `PENDING_USER_DEVICE`. Không được fake PASS.

### Nút thắt #4 — Cloudflare Pages CI
- GitHub secrets `CLOUDFLARE_*` trống → Pages deploy CI chưa đóng.

---

## 6. Việc đang làm / vừa làm

1. Sửa hết 4 Bugbot trên PR #28 → push `15a18a7`.
2. Thêm one-shot My Machines + tunnel.
3. Ghi evidence public FAIL trung thực.
4. Chờ user bật worker trên PC; timer recheck workers đã đặt trước đó.
5. CI/Bugbot trên synchronize của PR #28 đang/đã chạy lại.

---

## 7. Việc AI kế tiếp phải làm (thứ tự)

1. **Recheck** `list-self-hosted-workers`. Nếu có worker → **ngay lập tức** chạy trên PC:
   - `git checkout cursor/fix-named-tunnel-ps1-45fd && git pull`
   - `scripts/windows-install-persistent-tunnel.ps1` (hoặc one-shot `-SkipWorker` nếu worker đã chạy)
   - Browser/curl verify `https://toolvip1.top/` body có `SwiftTerm`
   - Ghi evidence dưới `Docs/evidence/`
2. Nếu workers vẫn rỗng: **không giả vờ điều khiển PC**; chỉ cập nhật evidence FAIL + giữ script sẵn.
3. User trên PC (bắt buộc một lần để mở nút thắt #1+#2):

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git fetch origin
git checkout cursor/fix-named-tunnel-ps1-45fd
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\windows-start-my-machine-and-tunnel.ps1
```

Giữ cửa sổ My Machines mở. Cần `agent login` nếu CLI chưa login.

4. Sau domain PASS bền: xử lý Pages secrets nếu user cung cấp; 158 vẫn chỉ PASS khi device điền CSV.
5. Merge PR #28 chỉ khi Bugbot/CI sạch và user OK.

---

## 8. Tiêu chí PASS cuối (checklist)

| Hạng mục | PASS khi |
|----------|----------|
| Domain | `Invoke-WebRequest https://toolvip1.top/` = 200, body chứa SwiftTerm, không 1033/Hello World/Access |
| Durable | tunnel sống sau khi đóng cửa sổ launcher (detached/service); diagnose OK |
| My Machines | `list-self-hosted-workers` không rỗng; agent chạy lệnh trên PC được |
| 158 | CSV device xác nhận đủ catalogue; không chỉ plist source |
| Pages | CI deploy với secrets thật |
| Absolute complete | User đối chiếu manufacturer-matching OK |

---

## 9. Quy tắc bắt buộc cho AI tiếp theo

- Không claim hoàn thành tuyệt đối khi domain FAIL hoặc workers rỗng hoặc 158 PENDING.
- Không chỉ hướng dẫn nếu worker đã online — phải **thực thi** trên máy.
- Không fake browser/E2E evidence.
- Domain đúng: **`toolvip1.top`**.
- Tunnel đúng: **`swiftterm-web`** / UUID `b3fae273-5e2e-428c-aaff-7bfc20e441f5`.
- PS1 Windows: UTF-8 BOM, ASCII, không em-dash; tránh parse lỗi PS 5.1.
- Cloud agent run gốc: `bc-f6952eae-1f31-41cd-9b9d-525cc43645fd`.

---

## 10. Snapshot kỹ thuật ngắn (copy cho AI)

```
repos: jiaomeimei0-prog/SwiftTerm + a-Shell
branch: cursor/fix-named-tunnel-ps1-45fd @ 15a18a7
PR: https://github.com/jiaomeimei0-prog/SwiftTerm/pull/28 OPEN
domain: toolvip1.top FAIL (SSL_ERROR_SYSCALL) — cloudflared down on user PC
tunnel: swiftterm-web / b3fae273-5e2e-428c-aaff-7bfc20e441f5
workers: []  (Use my computer installed ≠ online)
158: PENDING_USER_DEVICE
Pages: CLOUDFLARE_* secrets missing
next: user run windows-start-my-machine-and-tunnel.ps1 KEEP worker open → agent takes over PC → durable SwiftTerm on toolvip1.top → then 158 device + Pages
```
