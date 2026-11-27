# BỘ NHỚ HANDOFF — SwiftTerm + a-Shell

**Cập nhật:** 2026-11-28 05:18 giờ Việt Nam (Asia/Saigon, UTC+7)  
**Phiên agent:** https://cursor.com/agents/bc-f6952eae-1f31-41cd-9b9d-525cc43645fd  
**Chủ tài khoản:** `jiaomeimei0@gmail.com` (Cursor)  
**Mục đích file:** AI / người kế tiếp đọc **một lần** để nắm SoT, ranh giới, blocker, và **không bịa PASS**.

Quy tắc nghiệm thu: chỉ ghi ĐẠT khi có lệnh + kết quả quan sát được. Runtime iOS chưa chạy → `PENDING_USER_DEVICE`. Web WASM ≠ 158 lệnh a-Shell.

---

## 0. Mục tiêu người dùng (đã làm rõ 2026-11-28)

Người dùng cần hoàn thành lớp **app shell iOS**, không phải web:

1. Lệnh  
2. `ios_system`  
3. Catalogue **158**  
4. Shortcuts  
5. File app (`pickFolder` / bookmark / Documents)

Web/`toolvip1.top` là track riêng (SwiftTerm WASM) — **không** đóng mục tiêu trên.

---

## 1. Kiến trúc hai lớp (đọc kỹ — hay bị hiểu nhầm)

```text
┌─ a-Shell (fork jiaomeimei0-prog/a-shell) ─────────────────────┐
│  App iOS: SceneDelegate, ExtraCommands, Intents, bookmarks    │
│  Catalogue 158 · replaceCommand · pipe/session                 │
│  Gọi ios_system (binary holzschu) để CHẠY lệnh                 │
└───────────────────────────┬────────────────────────────────────┘
                            │ TerminalViewDelegate + HostHelpers
┌───────────────────────────▼────────────────────────────────────┐
│  SwiftTerm (SoT jiaomeimei0-prog/SwiftTerm)                     │
│  Emulator VT / render / HostHelpers — KHÔNG spawn lệnh          │
│  Web WASM toolvip1.top = chỉ lớp này                            │
└────────────────────────────────────────────────────────────────┘
```

| Bề mặt | Ai kiểm soát |
|--------|----------------|
| Vẽ terminal, WASM web | **SwiftTerm** |
| Lệnh, ios_system, 158, Shortcuts, file/bookmark | **a-Shell** |
| Runtime thật khi gõ `ls` | **`ios_system` (holzschu binary)** bên trong a-Shell |

**Không đúng:** “cả dự án đều là a-Shell” / “web cũng của a-Shell”.  
**Đúng:** a-Shell kiểm soát **app shell iOS**; SwiftTerm kiểm soát **emulator + web**.

---

## 2. `ios_system` gốc là gì?

- Repo: https://github.com/holzschu/ios_system  
- Tác giả: Nicolas Holzschuch (cùng hệ a-Shell).  
- **Là:** thư viện / XCFramework — động cơ chạy lệnh Unix-like **in-process** trên iOS (không phải `fork`/`exec` POSIX hệ thống).  
- **Không phải:** terminal emulator; không phải app a-Shell.  
- API tiêu biểu: `initializeEnvironment`, `ios_system`, `ios_fork`, `ios_waitpid`, `ios_setStreams`, `replaceCommand`, `addCommandList`.  
- Catalogue: `Resources/commandDictionary.plist` → `[framework, symbol_main, …]` → `dlopen` → gọi `*_main`.  
- Pin binary hiện tại trong fork: **v3.0.5** qua `Apps/a-Shell/xcfs/Package.swift`  
  (`ios_system.xcframework.zip` + `files`/`shell`/`awk`/`dash`/`ssh_cmd`/… từ release holzschu).

Luồng gõ lệnh:

```text
User → SceneDelegate → ios_setStreams / ios_fork
     → ios_system("ls") → plist → files.framework → stdout pipe → SwiftTerm vẽ
```

**Hệ quả:** muốn “a-Shell mới không phụ thuộc gốc” thật sự = thay hoặc tự build lại cả `ios_system` + ecosystem framework — không đủ chỉ fork đổi tên / đổi SwiftTerm.

---

## 3. Repo / pin hiện tại (main @ `20b6307`)

| Thành phần | Remote | Ref |
|------------|--------|-----|
| SwiftTerm SoT | `https://github.com/jiaomeimei0-prog/SwiftTerm` | `main` |
| Submodule `Apps/a-Shell` | `https://github.com/jiaomeimei0-prog/a-shell.git` | **`e95741b8`** (sau merge a-shell#8) |
| Nested `Apps/a-Shell/SwiftTerm` | `jiaomeimei0-prog/SwiftTerm` | pin cũ **`633a592e`** (chậm tip main; Sources tree từng khớp) |
| Nested `cpython` | **`holzschu/cpython`** `3.13` | vẫn upstream holzschu |
| a-Shell upstream remote | `holzschu/a-shell` | fork **diverged** (từng đo ~ahead 8 / behind 84 vs holzschu master) |

Clone local agent thường có: `/workspace` (SwiftTerm), `/agent/repos/a-shell` (fork + `upstream`).

---

## 4. Trạng thái nghiệm thu (trung thực)

### ĐÃ ĐẠT (có evidence)

| Hạng mục | Evidence |
|----------|----------|
| Catalogue 158 identity (plist keys = 158, parity byte vs gốc lúc audit) | `Docs/command-parity-vs-ashell-2026-11-26.md`, `Docs/command-158-device-matrix-PENDING.csv` |
| Script L4 trên pin | `Apps/a-Shell/scripts/verify_command_catalogue_158.sh` |
| Runbook L4 | `Docs/l4-device-acceptance-runbook.md` |
| Pin bump sau a-shell#8 | SwiftTerm PR **#39** |
| `toolvip1.top` hiện SwiftTerm WASM (user Safari) | `Docs/evidence/toolvip1-user-verify-swiftterm-2026-11-28.md` + PNG |
| Cloudflare Pages CI deploy | run `46070836385` success |
| Ngắt Workers Builds `swiftterm` (check GitHub biến mất trên `d8b28ca`) | PR **#40**/#**41**, `Docs/evidence/workers-builds-swiftterm-disconnect-2026-11-28.md` |
| Token/DNS docs | `Docs/cloudflare-token-dns-edit.md` |
| Host E2E SwiftTerm (không phải 158 device) | `Docs/e2e-acceptance-results.md` / audit |
| Checklist tổng | `Docs/acceptance-remaining-checklist.md` |

### CHƯA ĐẠT / BLOCKER

| Hạng mục | Trạng thái | Ai đóng |
|----------|------------|---------|
| **L4 — 158 lệnh runtime trên iPhone/iPad** | `PENDING_USER_DEVICE` | **User** chạy script trong app |
| Shortcuts / Intents / pickFolder runtime | Code có; chưa evidence device | User + Xcode device |
| Build Xcode full a-Shell trên Cloud Agent | **Không thể** (Linux, không Xcode) | Mac của user / CI Apple |
| Tự Roll `CLOUDFLARE_API_TOKEN` (DNS:Edit, Workers Builds Configuration:Edit) | Docs sẵn; secret do user | User Cloudflare + GitHub Secrets |
| Self-hosted worker trên PC user | Thường `workers: []` | User `agent worker start` |
| Greenfield a-Shell độc lập khỏi ios_system | Ngoài phạm vi chỉnh pin | Dự án runtime mới (B/C) |

---

## 5. Việc agent Cloud LÀM ĐƯỢC / KHÔNG LÀM ĐƯỢC

**Làm được:** audit source, pin submodule, script host, docs, CI Cloudflare Pages, HostHelpers trong SwiftTerm, parity catalogue tĩnh, mở/merge PR GitHub.

**Không làm được:** chạy 158 trên device; `xcodebuild` iOS; chứng minh Shortcuts/file runtime; Roll secret Cloudflare; điều khiển PC user; thay thế `ios_system` + ship App Store trong VM này.

---

## 6. Lệnh tiếp theo bắt buộc (user / AI có Mac+device)

```sh
# Trong app a-Shell build từ pin e95741b8+
sh verify_command_catalogue_158.sh
# Kỳ vọng cuối:
# ACCEPT: all 158 catalogue names present in help -l
```

Sau đó:

1. Lưu log → `Docs/evidence/command-158-device-run-YYYY-MM-DD.txt`  
2. Cập nhật `Docs/command-158-device-matrix-PENDING.csv` (`runtime_status` = `PASS_DEVICE` / `FAIL_DEVICE`)  
3. Đổi tên bỏ `PENDING` **chỉ** khi có log device thật.

Chi tiết: `Docs/l4-device-acceptance-runbook.md`.

---

## 7. Ba đường chiến lược (nếu hỏi “tách khỏi a-Shell gốc”)

| Đường | Ý | Phụ thuộc ios_system gốc? |
|-------|----|---------------------------|
| **A. Fork + sync** (đang đi) | Giữ a-Shell fork, SoT SwiftTerm riêng | Có (binary) |
| **B. Hard-fork runtime** | Tự build ios_system + ports | Giảm dần |
| **C. Greenfield** | App mới: SwiftTerm + runtime khác | Không — nhưng **mất** sản phẩm 158/Shortcuts parity |

Mục tiêu hiện tại của user → **A + nghiệm thu device**, không phải C.

---

## 8. PR gần đây (SwiftTerm)

| PR | Nội dung | State |
|----|----------|-------|
| #39 | Bump `Apps/a-Shell` → `e95741b8`; L4 runbook; disable worker script | MERGED |
| #40 | Disconnect Workers Builds triggers (`script_tag` + DELETE triggers) | MERGED |
| #41 | Evidence disconnect + refresh checklist | MERGED |

a-Shell **#8** (verify catalogue 158): đã merge vào master fork trước pin `e95741b8`.

---

## 9. File then chốt để AI kế đọc

| File | Nội dung |
|------|----------|
| `Docs/handoff-memory-export-2026-11-28-0518-ict.md` | **File này** |
| `Docs/handoff-memory-export-2026-11-28.md` | Handoff sớm hơn (pin/PR cũ — đối chiếu, đừng tin pin cũ) |
| `Docs/l4-device-acceptance-runbook.md` | Cách PASS L4 |
| `Docs/command-158-device-matrix-PENDING.md` | Quy tắc CSV 158 |
| `Docs/cloudflare-token-dns-edit.md` | Quyền token CF |
| `Docs/web-cloudflare-setup.md` | Pages / domain |
| `Docs/acceptance-remaining-checklist.md` | Checklist còn lại |
| `Docs/audit/AUDIT-REPORT-2026-11-27.md` | Audit sâu (số liệu; một số mục domain/pin đã cũ) |
| `scripts/cloudflare-disable-worker-swiftterm.sh` | Dọn Worker/Builds |
| `Apps/a-Shell/scripts/verify_command_catalogue_158.sh` | Nghiệm thu device |

---

## 10. Câu trả lời mẫu (tránh hiểu sai)

- **“Tất cả đều là a-Shell?”** → Không. Web = SwiftTerm. App lệnh = a-Shell.  
- **“a-Shell kiểm soát gì?”** → Catalogue, ios_system bridge, Shortcuts, file/bookmark, SceneDelegate spawn — không kiểm soát emulator/web SoT.  
- **“158 đã kiểm soát?”** → Danh sách/plist trong fork: đã khóa. Runtime trên máy user: chưa. Engine: vẫn ios_system holzschu.  
- **“Làm a-Shell mới không bị gốc kiểm soát?”** → Được về lý thuyết (B/C); không phải việc Cloud Agent hoàn tất trong phiên pin/CI; sản phẩm 158 hiện tại **là** lớp gốc.

---

## 11. Anti-fake — cấm ghi

- PASS 158 chỉ vì plist có 158 keys.  
- PASS lệnh vì `toolvip1.top` mở được.  
- PASS Shortcuts/file vì đọc thấy source.  
- “Độc lập holzschu” trong khi vẫn tải `ios_system.xcframework` từ release holzschu.

**Verdict lúc xuất file:** Domain WASM + pin a-Shell + dọn Workers Builds = đã có evidence. **Mục tiêu lõi user (158 + ios_system runtime + Shortcuts + file trên device) = CHƯA ĐÓNG** — chờ device.
