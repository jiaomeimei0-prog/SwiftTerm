# BỘ NHỚ TOÀN DỰ ÁN — SwiftTerm + a-Shell (FULL)

**Cập nhật:** 2026-11-28 10:10 giờ Việt Nam (Asia/Saigon, UTC+7)  
**Phiên agent chính:** https://cursor.com/agents/bc-f6952eae-1f31-41cd-9b9d-525cc43645fd  
**Chủ tài khoản Cursor:** `jiaomeimei0@gmail.com`  
**Mục đích:** Một file duy nhất cho AI/người kế tiếp — SoT, kiến trúc, pin, CI, checklist 158, blocker đã đóng, việc còn lại. **Không bịa PASS.**

**Quy tắc nghiệm thu:** chỉ ĐẠT khi có lệnh + kết quả quan sát. Runtime iOS chưa chạy → `PENDING_USER_DEVICE`. Web WASM ≠ 158 lệnh a-Shell.

Handoff ngắn hơn (cũ hơn): `Docs/handoff-memory-export-2026-11-28-0518-ict.md` — **ưu tiên file FULL này**.

---

## 0. Mục tiêu người dùng (đã chốt)

Hoàn thành lớp **app shell iOS** (không phải web):

1. Lệnh  
2. `ios_system`  
3. Catalogue **158**  
4. Shortcuts / Intents  
5. File app (`pickFolder` / bookmark / Documents)

`https://toolvip1.top` = demo **SwiftTerm WASM** — track riêng, không đóng 158.

---

## 1. Kiến trúc (đọc trước mọi thứ)

```text
┌─ a-Shell fork (jiaomeimei0-prog/a-shell) ─────────────────────┐
│  App iOS: SceneDelegate, ExtraCommands, Intents, bookmarks    │
│  Catalogue 158 · replaceCommand · session/pipe                 │
│  Runtime: ios_system.xcframework (holzschu binary)             │
└───────────────────────────┬────────────────────────────────────┘
                            │ TerminalViewDelegate + HostHelpers
┌───────────────────────────▼────────────────────────────────────┐
│  SwiftTerm SoT (jiaomeimei0-prog/SwiftTerm)                     │
│  Emulator VT / render / HostHelpers — KHÔNG spawn lệnh          │
│  Web WASM toolvip1.top = CHỈ lớp này                            │
└────────────────────────────────────────────────────────────────┘
```

| Bề mặt | Ai kiểm soát |
|--------|----------------|
| Terminal vẽ + WASM web | **SwiftTerm** |
| Lệnh / ios_system / 158 / Shortcuts / file | **a-Shell** |
| Khi gõ `ls` | **`ios_system` in-process** (không phải host Mac/PC shell) |

### `ios_system` gốc là gì?

- Repo: https://github.com/holzschu/ios_system  
- Động cơ lệnh Unix-like **trong process** app iOS (App Store không cho `fork`/`exec` tùy ý).  
- API: `initializeEnvironment`, `ios_system`, `ios_fork`, `ios_waitpid`, `ios_setStreams`, `replaceCommand`, …  
- Catalogue: `commandDictionary.plist` → framework + `*_main`.  
- Pin binary hiện tại: **v3.0.5** qua `Apps/a-Shell/xcfs/Package.swift`.

### Dependency thật (không phải “20 submodule”)

| Loại | Số | Chi tiết |
|------|-----|----------|
| Git submodule trong a-Shell | **2** | `SwiftTerm` (fork SoT), `cpython` (holzschu 3.13) |
| `.binaryTarget` SPM | **65** (canonical) | `xcfs/Package.swift` — checksum holzschu |
| Podfile | **Không** | — |
| Local ports | `node/`, `fd/`, `fzf/`, … | Build Mac khi cần |

Evidence: `Docs/dependency-audit.md`, `Docs/fork-registry.md` + `.yaml`.

---

## 2. Pin / SHA hiện tại

| Thành phần | SHA / ref |
|------------|-----------|
| SwiftTerm `main` (tip SoT) | `5345160eab8a4b787bc7f8ff1278f84c8f19bd83` |
| Monorepo gitlink `Apps/a-Shell` | `e95741b8e59bef75cec490528f8f36a498555bcf` (sau a-shell#8) |
| Nested Xcode SwiftTerm | **`633a592ee9dd9585a0536314d26e906154ac43db`** (chưa bump) |
| Tip SoT vs nested | `Sources/SwiftTerm` **tree hash identical** (`cd66deb1…`) — bump tip **không** đổi emulator |
| Plist SHA256 @ e95741b8 | `6b73f4c2f2b5bb6e3708647f4c19a6642709c907adbea5bfc4f90bd15dc7a6cc` |

**A5 STOPPED:** `633a592e..5345160e` = **31** commits (>30). Plan: `Docs/swiftterm-nested-bump-plan-2026-11-28.md`. Pin nested **giữ** `633a592e`.

---

## 3. Catalogue 158 / CSV schema

| Mục | Giá trị |
|-----|---------|
| Nguồn | `Apps/a-Shell/Resources/commandDictionary.plist` @ `e95741b8` |
| Parity holzschu | Byte-identical (audit); hash trong `Docs/command-parity-vs-ashell-2026-11-26.md` |
| Ma trận | `Docs/command-158-device-matrix-PENDING.csv` |
| Device script | `Apps/a-Shell/scripts/verify_command_catalogue_158.sh` (A2a: EXPECTED ≡ plist, không mismatch) |

**CSV schema C (chốt):**

- `runtime_status` — cột chính (`PENDING_USER_DEVICE` / `PASS_DEVICE` / `FAIL_DEVICE`)  
- `user_observed_output` — evidence (trống đến device)  
- `user_pass_fail` — evidence phụ  

**Không** tự điền runtime / user_* trên agent.

---

## 4. PR / CI gần đây

| PR | Nội dung | State |
|----|----------|-------|
| a-shell #8 | `verify_command_catalogue_158.sh` | Merged → pin `e95741b8` |
| SwiftTerm #39 | Bump a-Shell pin + L4 runbook + worker disable | Merged |
| #40–#41 | Workers Builds disconnect + evidence | Merged |
| #42 | Handoff 05:18 | Merged |
| **#43** | Catalogue-158 checklist A1–A6 | **OPEN** — https://github.com/jiaomeimei0-prog/SwiftTerm/pull/43 |

PR #43 tip (lúc ghi): `5ba088f` — Swift + WASM CI **success** sau flake retry; Sonar **Quality Gate passed**.

Commits trên nhánh (ý nghĩa):

1. `checklist-158: docs+scripts`  
2. `swiftterm-bump: plan only, pin unchanged`  
3. `validate_catalogue: close A2b blockers` (`efb2351`)  
4. empty `ci: retrigger` (`5ba088f`)

---

## 5. Checklist A1–A6 (PR #43)

| ID | Deliverable | Status |
|----|-------------|--------|
| A1 | `Docs/fork-registry.md` + `.yaml` | Done |
| A2a | Review verify script | PASS — no schema mismatch |
| A2b | `scripts/validate_catalogue.sh` | PASS host — blockers đóng (dưới) |
| A2c | `scripts/finalize_catalogue.sh` | Ready — chờ device CSV |
| A3 | `scripts/build_noPython.sh` | Mac-only, **không chạy** trên agent |
| A4 | `scripts/sign_and_deploy.sh` | Mac-only, **không chạy** trên agent |
| A5 | Nested bump | **STOPPED** (>30); plan doc |
| A6 | `Docs/dependency-audit.md` | Done — 2 submodule, **65** binary |

### A2b blockers (đã đóng)

| Blocker | Trước | Sau |
|---------|--------|-----|
| 1 Cột runtime | Spec cũ `user_*` vs script `runtime_status` | Schema **C**; CSV có `runtime_status`; script require cột |
| 2 Cross-check | Chỉ đếm 158 | Set equality `command` ↔ plist keys (+ negative test) |
| 3 Shape plist | `len(keys)` mù | Assert `dict` + key `str` |

Part B user: `Docs/catalogue-158-checklist-part-B.md`.

---

## 6. Cloudflare / domain (track phụ)

| Mục | Status |
|-----|--------|
| `toolvip1.top` SwiftTerm WASM | PASS user Safari — `Docs/evidence/toolvip1-user-verify-swiftterm-2026-11-28.md` |
| Pages CI | Deploy + claim OK |
| Workers Builds `swiftterm` | Disconnect — check absent trên `d8b28ca` |
| Token DNS:Edit / Builds Configuration | Docs: `Docs/cloudflare-token-dns-edit.md` — user Roll nếu còn 403 |

Tên sai: `tooltop1.vip` — không dùng.

---

## 7. Agent Cloud LÀM / KHÔNG LÀM ĐƯỢC

**Làm được:** pin, docs, scripts host, audit, CI Pages, HostHelpers SoT, PR, validate catalogue pre-device.

**Không làm được:** build Xcode trên Linux; chạy 158 trên iPhone; Shortcuts/file runtime; Roll secret CF; điều khiển PC user; thay `ios_system` ecosystem trong một phiên.

---

## 8. Việc tiếp theo (ưu tiên)

1. **Merge PR #43** khi review OK (CI/Sonar đã xanh trên tip).  
2. **User Mac:** `./scripts/build_noPython.sh` → `./scripts/sign_and_deploy.sh` → device.  
3. **Device:** `sh verify_command_catalogue_158.sh` → điền CSV (`runtime_status` + evidence) → `./scripts/finalize_catalogue.sh`.  
4. Nested SwiftTerm bump: chỉ khi user duyệt plan A5 (không bắt buộc cho 158 — tree Sources identical).  
5. Shortcuts / pickFolder: smoke riêng trên device sau L4.

---

## 9. Anti-fake (cấm)

- PASS 158 vì plist có 158 keys / vì web mở được.  
- Tự điền `runtime_status` / `user_*`.  
- Gọi “độc lập holzschu” khi vẫn tải `ios_system` binary.  
- Bump nested 31 commit 1-shot (stop rule).  
- Nhầm tip SoT `5345160e` với pin nested `633a592e`.

---

## 10. File then chốt

| File | Việc |
|------|------|
| **File này** | Bộ nhớ FULL |
| `Docs/fork-registry.md` / `.yaml` | keep/fork/bump + rebase |
| `Docs/dependency-audit.md` | 2+65 bằng chứng |
| `Docs/l4-device-acceptance-runbook.md` | L4 device |
| `Docs/catalogue-158-checklist-part-B.md` | User Mac/device |
| `Docs/swiftterm-nested-bump-plan-2026-11-28.md` | A5 STOPPED |
| `Docs/command-158-device-matrix-PENDING.csv` | Ma trận |
| `scripts/validate_catalogue.sh` | Pre-device |
| `scripts/finalize_catalogue.sh` | Post-device |
| `scripts/build_noPython.sh` / `sign_and_deploy.sh` | Mac only |
| `Docs/audit/AUDIT-REPORT-2026-11-27.md` | Audit sâu (một số mục domain/pin có thể cũ) |

---

## 11. Verdict lúc xuất

- **Web + Pages + Workers cleanup + pin a-Shell + docs/scripts checklist:** có evidence / PR mở.  
- **Mục tiêu lõi user (158 + ios_system runtime + Shortcuts + file trên device):** **CHƯA ĐÓNG** — `PENDING_USER_DEVICE`.  
- Nested SwiftTerm tip bump: **không làm** (stop >30); Sources identical nên không chặn L4.
