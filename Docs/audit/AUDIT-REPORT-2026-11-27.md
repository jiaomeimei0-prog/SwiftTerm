# Báo cáo kiểm kê tổng thể và rà soát an ninh — SwiftTerm (lõi) + a-Shell (master)

> Sinh tự động lúc 2026-11-27T09:25:33Z (UTC) = 2026-11-27 16:25 giờ Việt Nam (UTC+7) bởi `scripts/audit/run_audit.py`. Mọi con số được **tính từ git objects và lệnh chạy thật**, không gõ tay. Bộ phát hiện có 56 test đối chứng dương/âm (`scripts/audit/test_audit.py`): PASS. Dữ liệu thô: `Docs/audit/data/`.

## 0. Kết luận nhanh

1. **Lệnh:** 251 tên lệnh (catalogue full 158, mini 136, cộng extra/llvm/tex/luatex/sshStock và 39 host built-in). Định nghĩa **fork ≡ nhà sản xuất ≡ pin** cho 251/251 lệnh; **0 lỗi do fork đưa vào**. Có 12 lệnh lỗi cấu hình, 8 lệnh khoảng trống nguồn gốc, 37 lệnh TeX chưa xác minh symbol — tất cả là di sản của nhà sản xuất (mục 4.4).
2. **Lệnh gọi sai:** trước sửa 84 → **50 chỗ** (mục 4.6). Đã khắc phục: gốc repo PowerShell gắn cứng 12 → 0, tên miền sai 19 → 0, workflow thiếu `permissions` 2 → 0.
3. **Kiểm thử:** lõi emulator đạt trên Linux CI (78 XCTest + 1190 Swift Testing). **Fork a-Shell trượt bài test `worker-binding.sh` của nhà sản xuất** (upstream PASS; fork FAIL; pin FAIL). Biên dịch Apple (workflow `Swift` gốc): macOS ĐÃ có bằng chứng (`swiftpm-strict-concurrency` đạt), iOS/HostHelpers ĐÃ có bằng chứng (bước `Xcode iOS Build` đạt); hàng đợi macOS: 37/40 job xong, 0 đang chạy, 0 queued, 3 kết thúc khi chưa có runner. Script Windows: PowerShell 5.1 52 check đạt, 0 lỗi. Chưa có chạy thật 158 lệnh.
4. **An ninh:** 0 nghiêm trọng, 1 cao, 7 trung bình, 9 thấp, 5 thông tin. Không phát hiện token dạng literal (quét theo mẫu, không kiểm tra hiệu lực); có khoá riêng localhost công khai, handler WebView chấp nhận mọi chứng chỉ, 3 chỗ nội suy JS thiếu escape (đều là mã gốc của nhà sản xuất).
5. **Chưa thể khẳng định "hoàn tất"**: tên miền `toolvip1.top` chưa xác minh từ bên ngoài; 158 lệnh chưa chạy trên thiết bị; thiếu secrets Cloudflare. Chi tiết mục 6.4 và 10.

## 1. Hai nguồn lõi và đồ thị phụ thuộc

| Nguồn | Repo | Ref | Commit | Ngày | Tiêu đề |
|---|---|---|---|---|---|
| SwiftTerm (lõi, SoT) | jiaomeimei0-prog/SwiftTerm | `HEAD` | `8025a28594` | 2026-11-27 | audit: state the HostHelpers evidence level from the iOS build result |
| a-Shell gốc nhà sản xuất (holzschu/a-shell master) | a-shell | `upstream/master` | `17b01a4d36` | 2026-11-25 | Merge pull request #1126 from demrom/feature/openssh-client-registrati |
| a-Shell fork master (jiaomeimei0-prog/a-shell) | a-shell | `origin/master` | `4f039cdb70` | 2026-11-26 | Unify nested SwiftTerm pin to fork SoT main tip (#7) |
| a-Shell commit được SwiftTerm ghim (Apps/a-Shell) | a-shell | `d63526ba824f37d4d378cc4293e7dfe555e754d9` | `d63526ba82` | 2026-11-26 | Regenerate 158-command acceptance list from commandDictionary.plist |

- **Fork so với nhà sản xuất** (GitHub compare, thu thập 2026-11-27T09:25:43Z (UTC) = 2026-11-27 16:25 giờ Việt Nam (UTC+7)): `diverged`, ahead **7** / behind **31**, merge-base `34e0ae0141`. Đếm bằng `git rev-list` cục bộ không đáng tin vì bản clone a-shell trên VM là shallow.
- **Pin `Apps/a-Shell`** = `d63526ba82` = master tip + 2 commit chưa merge ([PR #8](https://github.com/jiaomeimei0-prog/a-shell/pull/8) (open)); behind = 0.
- **SwiftTerm lồng trong a-Shell** (`Apps/a-Shell/SwiftTerm`, bản a-Shell thực sự build qua `XCLocalSwiftPackageReference`): `633a592ee9` ("Make DocC Pages-optional and narrow SonarCloud scope (#22)"), tổ tiên của HEAD = **True**, chậm **37** commit; cây `Sources/SwiftTerm` **GIỐNG HỆT** HEAD (so tree hash). Upstream ghim bản SwiftTerm của nhà sản xuất `dcbd49d755`.
- **Đồ thị phụ thuộc là vòng**: `SwiftTerm (SoT) → Apps/a-Shell → SwiftTerm (bản lồng)`. SoT không được cưỡng chế bởi build graph; nó chỉ đúng khi pin lồng được bump đều.

### Thay đổi thật của fork so với nhà sản xuất (diff ba chấm từ merge-base: 16 file, 7 commit)

| File | Trạng thái | + | − |
|---|---|---|---|
| `.github/workflows/app-build.yml` | modified | 4 | 2 |
| `.gitmodules` | modified | 2 | 1 |
| `README.md` | modified | 28 | 3 |
| `Resources_mini/sshStockCommands.plist` | added | 34 | 0 |
| `ShellWorkers/PaneWire.h` | modified | 1 | 1 |
| `ShellWorkers/RemotePane.m` | modified | 3 | 1 |
| `ShellWorkers/Worker.m` | modified | 5 | 1 |
| `ShellWorkers/Worker.swift` | modified | 1 | 1 |
| `ShellWorkers/Worker.xcconfig` | modified | 1 | 0 |
| `ShellWorkers/resources.sh` | modified | 1 | 1 |
| `SwiftTerm` | modified | 1 | 1 |
| `a-Shell.xcodeproj/project.pbxproj` | modified | 70 | 0 |
| `a-Shell/AppDelegate.swift` | modified | 25 | 0 |
| `a-Shell/SceneDelegate+TerminalView.swift` | modified | 0 | 11 |
| `scripts/verify_ashell_integrity.sh` | added | 188 | 0 |
| `tests/ssh-stock-registration.sh` | added | 93 | 0 |

Commit của fork: `18595d50b1` Pin SwiftTerm submodule to fork v2 (keep five host capabilities) (#1); `b426f498dc` Bump SwiftTerm submodule to fork main tip (#2); `9b4c754891` Add on-device integrity smoke script (#3); `69f290306b` Harden integrity script TLS port probe parsing (#4); `f47f284cc9` Stop calling internal TerminalView.updateDisplay (#5); `0c9b11b6a1` Port Stock SSH tip wiring for command parity with holzschu (#6); `4f039cdb70` Unify nested SwiftTerm pin to fork SoT main tip (#7).

Lưu ý chức năng: fork xoá 11 dòng `terminalView?.updateDisplay()` khỏi `SceneDelegate+TerminalView.swift` (kiểm bằng `git diff upstream/master origin/master`) để tương thích SoT SwiftTerm; hiệu ứng vẽ lại chỉ kiểm chứng được trên thiết bị.

### So sánh đầu nhánh (`git diff upstream/master origin/master`) — LẪN lẫn thay đổi của fork và nội dung upstream mới hơn

| File | + | − |
|---|---|---|
| `.github/workflows/app-build.yml` | 4 | 2 |
| `.gitmodules` | 2 | 1 |
| `README.md` | 28 | 29 |
| `SwiftTerm` | 1 | 1 |
| `a-Shell.xcodeproj/project.pbxproj` | 19 | 19 |
| `a-Shell/SceneDelegate+TerminalView.swift` | 0 | 11 |
| `scripts/verify_ashell_integrity.sh` | 188 | 0 |
| `tests/ssh-stock-registration.sh` | 0 | 0 |
| `tests/worker-binding.sh` | 0 | 32 |
| `tests/worker-pool.m` | 8 | 23 |
| `tests/worker-pool.md` | 0 | 26 |

Các dòng `−` ở `tests/worker-*` là nội dung upstream đã thêm sau merge-base (không có trong danh sách thay đổi thật ở trên), nên không phải do fork xoá. Pin so với fork master: `scripts/verify_command_catalogue_158.sh` (+92/−0).

<details><summary>31 commit của nhà sản xuất chưa có trong fork</summary>

| SHA | Ngày | Nội dung |
|---|---|---|
| `f497d97662` | 2026-10-23 | Register stock OpenSSH clients with isolated workers |
| `783cc8a833` | 2026-10-23 | Limit stock client registration to the worker-enabled mini target |
| `a2fceba103` | 2026-10-23 | Document stock client home-path migration |
| `5dacf19091` | 2026-10-23 | Match migration instructions to the client home adapter |
| `43f1d3343c` | 2026-11-06 | Merge current worker base into OpenSSH clients |
| `4c94ab3397` | 2026-11-08 | Merge branch 'master' into feature/openssh-client-registration |
| `ef2efe466b` | 2026-11-09 | Merge branch 'master' into feature/openssh-client-registration |
| `1ff9685dca` | 2026-11-10 | Merge #1168 (libpng path fix) to unbreak the noPython CI builds |
| `2676b2bb7a` | 2026-11-15 | Merge master into feature/openssh-client-registration |
| `1e5642f5c7` | 2026-11-23 | Merge origin/master into the OpenSSH client candidate |
| `21976c4df6` | 2026-11-23 | Scope stock OpenSSH to worker-enabled a-Shell mini |
| `476092480b` | 2026-11-24 | Reconcile Stock OpenSSH project with current upstream workers |
| `b735f72187` | 2026-11-24 | Generate worker resources for the configured app host |
| `2dfd3d6558` | 2026-11-24 | Send Stock SSH activation explicitly to shell workers |
| `7201a40096` | 2026-11-24 | Pin the Stock SSH producer recipe and distinguish runtime checks |
| `5b5da7c22b` | 2026-11-24 | Restore generated Swift bindings for shell workers |
| `d767515e15` | 2026-11-24 | Package Stock SSH frameworks into the a-Shell checkout |
| `68d2c604d4` | 2026-11-24 | Restore generated Swift bindings for shell workers |
| `b22981efff` | 2026-11-24 | Check all ten generated worker source references |
| `d93c9c5292` | 2026-11-24 | Check all ten generated worker source references |
| `428300cdb9` | 2026-11-25 | Merge pull request #1194 from demrom/fix/generated-shell-worker-swift |
| `4a27abf0bb` | 2026-11-25 | Update to build 615 |
| `80479f02f0` | 2026-11-25 | Merge branch 'master' of github.com:holzschu/a-shell |
| `17b01a4d36` | 2026-11-25 | Merge pull request #1126 from demrom/feature/openssh-client-registration |
| `c70f4b4232` | 2026-11-25 | Build number 616 |
| `1770a58b3f` | 2026-11-25 | Merge branch 'master' of github.com:holzschu/a-shell |
| `e9671c34aa` | 2026-11-26 | Localize a-Shell Shortcuts actions in French |
| `2cfaafdf71` | 2026-11-26 | Adding codex to a-Shell mini to check if herdr sees it |
| `a68e97fcf7` | 2026-11-26 | Require Kilo Code config before offering its Herdr plugin on iOS |
| `994081b236` | 2026-11-26 | Merge pull request #1200 from demrom/fix/herdr-kilo-config |
| `8f1527610f` | 2026-11-26 | Merge pull request #1197 from jeanphilippe-mh/l10n/french-shortcuts-actions |

</details>

## 2. Kiểm kê ngôn ngữ, quy mô và chức năng

### 2.1 SwiftTerm (lõi) — commit `8025a28594`

Toàn bộ file theo dõi: **755** file / 184.783 dòng; first-party (loại tài nguyên đóng gói, patch, vendored): **755** file / 184.783 dòng.

| Ngôn ngữ | File | Dòng | Dòng không trống | Dung lượng (B) |
|---|---|---|---|---|
| Swift | 412 | 146.483 | 131.811 | 6.255.862 |
| Markdown | 81 | 11.888 | 9.172 | 602.259 |
| JavaScript | 50 | 6.521 | 6.410 | 369.341 |
| Python | 22 | 5.905 | 5.143 | 331.174 |
| TypeScript | 39 | 2.631 | 2.614 | 135.623 |
| JSON | 22 | 2.347 | 2.343 | 88.711 |
| Xcode project | 3 | 1.408 | 1.366 | 58.511 |
| Text | 9 | 1.370 | 1.286 | 61.779 |
| Other/no extension | 9 | 1.362 | 1.303 | 379.487 |
| PowerShell | 9 | 864 | 761 | 37.706 |
| Shell | 9 | 810 | 756 | 29.875 |
| YAML | 6 | 595 | 518 | 20.021 |
| Interface Builder | 3 | 595 | 595 | 45.177 |
| SwiftPM lock | 5 | 570 | 570 | 17.074 |

| Khu vực | File | Dòng | Dung lượng (B) |
|---|---|---|---|
| engine+libraries | 181 | 86.161 | 3.694.373 |
| tests | 243 | 57.226 | 3.432.339 |
| sample apps | 83 | 8.950 | 1.736.145 |
| web (TS/WASM/Cloudflare) | 81 | 7.929 | 1.288.718 |
| dev tools | 58 | 8.764 | 708.979 |
| scripts | 38 | 6.697 | 368.341 |
| docs/evidence | 46 | 5.975 | 345.929 |
| root files | 13 | 2.197 | 95.630 |
| ci | 7 | 597 | 20.139 |
| build plugins | 1 | 164 | 6.555 |
| submodule glue | 2 | 68 | 2.859 |
| config | 2 | 55 | 1.463 |

### 2.2 a-Shell (fork master) — commit `4f039cdb70`

Toàn bộ file theo dõi: **20.534** file / 4.231.729 dòng; first-party (loại tài nguyên đóng gói, patch, vendored): **308** file / 98.367 dòng.

| Ngôn ngữ | File | Dòng | Dòng không trống | Dung lượng (B) |
|---|---|---|---|---|
| JavaScript | 12 | 28.329 | 25.286 | 901.511 |
| Swift | 37 | 27.544 | 26.551 | 1.555.749 |
| Patch | 56 | 15.522 | 14.637 | 520.570 |
| Xcode project | 1 | 6.561 | 6.543 | 740.138 |
| Shell | 47 | 4.110 | 4.016 | 185.123 |
| Objective-C | 21 | 3.818 | 3.640 | 174.788 |
| PEM key/cert | 3 | 3.065 | 2.946 | 203.093 |
| Rust | 12 | 2.111 | 2.065 | 73.954 |
| Other (.intentdefinition) | 2 | 1.580 | 1.580 | 51.512 |
| plist | 14 | 1.220 | 1.220 | 35.690 |
| Markdown | 20 | 819 | 486 | 115.186 |
| Localization | 15 | 707 | 353 | 25.523 |
| C++ | 3 | 578 | 556 | 24.173 |
| Python | 2 | 421 | 389 | 16.096 |

| Khu vực | File | Dòng | Dung lượng (B) |
|---|---|---|---|
| bundled resources | 20.226 | 4.133.362 | 216.821.321 |
| app (Swift) | 54 | 26.388 | 1.616.229 |
| root files | 31 | 32.938 | 1.191.427 |
| native command recipes | 131 | 22.164 | 833.404 |
| build config | 8 | 7.186 | 764.888 |
| tests | 25 | 1.795 | 103.701 |
| app (workers) | 12 | 2.054 | 99.452 |
| localization | 15 | 2.585 | 85.029 |
| ci/scripts | 13 | 1.975 | 73.336 |
| app (intents) | 18 | 1.261 | 58.318 |
| docs | 1 | 21 | 3.186 |

**Lưu ý đo lường:** `Web/cloudflare/site/` có **57** file sinh ra (`scripts/prepare-cloudflare-web.sh`) được commit, 1.120.627 B, trong đó 11 tên file JS xuất hiện hai lần (`pkg/` và `pkg/src/`) và nhị phân `pkg/swiftterm-embedded.wasm`; số dòng JS/TS của SwiftTerm vì vậy bị tính trùng.

### 2.3 Chức năng ↔ vị trí ↔ ngôn ngữ

| Repo | Thư mục | Chức năng | File | Dòng | Ngôn ngữ chính (số file) |
|---|---|---|---|---|---|
| swiftterm | `Sources` | Lõi emulator + view Apple/Mac/iOS + lõi WASM | 181 | 86.161 | Swift (153), Markdown (27), Metal (1) |
| swiftterm | `Tests` | Kiểm thử (Swift Testing, XCTest, WebWasm) | 243 | 57.226 | Swift (214), JavaScript (15), Binary asset (9) |
| swiftterm | `TerminalApp` | Ứng dụng mẫu + WebTerminal (PTY qua WebSocket) | 83 | 8.950 | Binary asset (28), Swift (22), JavaScript (8) |
| swiftterm | `Tools` | Công cụ dev (fuzz, benchmark, BiDi harness) | 57 | 8.723 | Swift (18), JSON (10), Python (7) |
| swiftterm | `Web` | Web/WASM + site Cloudflare Pages | 81 | 7.929 | TypeScript (39), JavaScript (26), JSON (6) |
| swiftterm | `scripts` | Script build/deploy/tunnel/E2E | 38 | 6.697 | Python (15), PowerShell (9), Shell (6) |
| swiftterm | `Docs` | Tài liệu và bằng chứng | 46 | 5.975 | Markdown (36), CSV (2), JSON (2) |
| swiftterm | `(root files)` | — | 13 | 2.197 | Markdown (4), Config (3), Text (1) |
| swiftterm | `.github` | CI | 7 | 597 | YAML (5), Markdown (2) |
| swiftterm | `Plugins` | — | 1 | 164 | Swift (1) |
| swiftterm | `Apps` | — | 2 | 68 | Markdown (1), Other/no extension (1) |
| swiftterm | `.swiftpm` | — | 2 | 55 | plist (2) |
| ashell | `Resources` | Tài nguyên đóng gói bản full (vim, node, perl...) | 19.364 | 3.846.482 | JavaScript (9454), Other (.vim) (1631), Perl (1318) |
| ashell | `man` | Trang man | 193 | 231.799 | man page (158), Other (.5) (11), Other (.7) (10) |
| ashell | `Resources_mini` | Tài nguyên bản mini | 524 | 54.664 | Other/no extension (162), JavaScript (115), TypeScript (83) |
| ashell | `(root files)` | Bộ nạp JS, cấu hình gốc | 31 | 32.938 | JavaScript (9), Shell (4), Markdown (3) |
| ashell | `a-Shell` | App iOS (Swift) | 49 | 25.815 | Swift (20), Binary asset (18), JSON (3) |
| ashell | `codex` | Công thức dựng lệnh native (Rust/Go/Patch/Shell) | 41 | 8.651 | Patch (29), Rust (4), Shell (2) |
| ashell | `a-Shell.xcodeproj` | Dự án Xcode (3 app target + worker) | 5 | 6.801 | plist (2), Xcode project (1), Other (.xcworkspacedata) (1) |
| ashell | `Herdr` | Công thức dựng lệnh native (Rust/Go/Patch/Shell) | 13 | 3.588 | Patch (4), Rust (4), Shell (2) |
| ashell | `node` | Công thức dựng lệnh native (Rust/Go/Patch/Shell) | 22 | 2.639 | Patch (9), Shell (5), JavaScript (3) |
| ashell | `ShellWorkers` | Worker cô lập A–J | 12 | 2.054 | Objective-C (4), C/C++/ObjC header (3), Swift (2) |
| ashell | `tests` | Test host/thiết bị | 25 | 1.795 | Shell (12), Objective-C (6), Markdown (5) |
| ashell | `helix` | Công thức dựng lệnh native (Rust/Go/Patch/Shell) | 10 | 1.715 | Patch (4), Config (1), Markdown (1) |

Bảng đầy đủ: `data/languages_by_language.csv`, `languages_by_area.csv`, `directories.csv`.

## 3. Kiểm kê script, entry point, workflow, host và điểm thực thi

### 3.1 Script

| Repo | Ngôn ngữ | Số script | Dòng | Có quyền thực thi | Có chế độ nghiêm ngặt | Không thấy tham chiếu (heuristic) |
|---|---|---|---|---|---|---|
| ashell | Python | 2 | 421 | 1 | n/a | 0 |
| ashell | Shell | 49 | 4.405 | 18 | 36/49 | 28 |
| swiftterm | Batch | 2 | 36 | 0 | n/a | 2 |
| swiftterm | Make | 2 | 49 | 0 | n/a | 1 |
| swiftterm | PowerShell | 9 | 864 | 0 | 9/9 | 0 |
| swiftterm | Python | 22 | 5.905 | 8 | n/a | 11 |
| swiftterm | Shell | 9 | 810 | 9 | 9/9 | 1 |

"Không thấy tham chiếu" chỉ tính các lời gọi nhìn thấy trong script/workflow/tài liệu; build phase của Xcode và lời gọi động có thể bỏ sót.

Script của SwiftTerm (đầy đủ):

| Script | Loại | Dòng | Số nơi tham chiếu | Mục đích (dòng chú thích đầu) |
|---|---|---|---|---|
| `Makefile` | Make | 44 | 0 | The fuzzer needs a Swift 6.2 or later toolchain from swift.org. |
| `TerminalApp/Makefile` | Make | 5 | 8 |  |
| `TerminalApp/WebTerminal/run.sh` | Shell | 14 | 0 |  |
| `Tools/BidiHarness/Scripts/capture-helper.py` | Python | 81 | 1 | Capture harness windows from a process that has Screen Recording access. |
| `Tools/BidiHarness/Scripts/harnessctl.py` | Python | 53 | 3 | Send one JSON Lines request to a running SwiftTerm BiDi harness. |
| `Tools/BidiHarness/Scripts/run-harness.sh` | Shell | 98 | 3 |  |
| `Tools/BidiHarness/Scripts/smoke-test.sh` | Shell | 72 | 1 |  |
| `Tools/SwiftTermBenchmarks/analyze-cpu-counters.py` | Python | 80 | 2 |  |
| `Tools/SwiftTermBenchmarks/analyze-time-profile.py` | Python | 108 | 2 |  |
| `Tools/SwiftTermBenchmarks/layout-report.py` | Python | 168 | 1 | Report where the hot SwiftTerm functions are in a SwiftTermProfile binary. |
| `Tools/generate_kitty_parity_matrix.py` | Python | 111 | 0 | Generate the pinned Ghostty Kitty graphics test inventory. |
| `Tools/run-pty-benchmark.py` | Python | 348 | 1 | Build and run paired MacTerminal PTY benchmarks. |
| `scripts/audit/audit_commands.py` | Python | 311 | 0 | a-Shell command inventory: plist catalogues, host built-ins, wiring in the Xcode |
| `scripts/audit/audit_hostapi.py` | Python | 85 | 0 | Usage audit of the SwiftTerm HostHelpers bridge (the API a-Shell consumes). |
| `scripts/audit/audit_invocations.py` | Python | 140 | 0 | Check command invocations written in docs, scripts and workflows against what th |
| `scripts/audit/audit_languages.py` | Python | 116 | 0 | Language / size inventory of one git ref (what is in the tree, by language and a |
| `scripts/audit/audit_lib.py` | Python | 526 | 0 | Shared helpers for the repository audit tools (standard library only). |
| `scripts/audit/audit_scripts.py` | Python | 369 | 0 | Script inventory and wrong-call detection (missing files, filters, modes, PowerS |
| `scripts/audit/audit_security.py` | Python | 326 | 0 | Static security inventory: outbound hosts, command-execution sinks, listeners an |
| `scripts/audit/openstep.py` | Python | 146 | 0 | Minimal OpenStep/NeXT ASCII property-list parser (Xcode project.pbxproj). |
| `scripts/audit/render_report.py` | Python | 680 | 0 | Render the Vietnamese audit report and the two full tables from audit results. |
| `scripts/audit/run_audit.py` | Python | 763 | 2 | Run the full audit of the two core sources and write machine-readable data. |
| `scripts/audit/shims/plutil` | Python | 78 | 0 | Linux stand-in for the subset of Apple's plutil used by a-Shell's own tests. |
| `scripts/audit/test_audit.py` | Python | 606 | 2 | Positive/negative controls for the audit detectors. |
| `scripts/build-wasm.sh` | Shell | 134 | 10 | Build the portable command or browser reactor with the pinned Swift SDK. |
| `scripts/check-fixed-layout.sh` | Shell | 73 | 2 | Fails when a hot-path type in SwiftTerm has a run-time field layout. |
| `scripts/check-wasm-exports.sh` | Shell | 4 | 1 |  |
| `scripts/cloudflare-connect-domain.sh` | Shell | 62 | 5 | Deploy SwiftTerm WASM site to Cloudflare Pages and attach custom domain(s). |
| `scripts/diagnose-toolvip1.ps1` | PowerShell | 52 | 3 | Quick local diagnostics for toolvip1.top named tunnel on Windows. |
| `scripts/e2e_acceptance_host.sh` | Shell | 301 | 7 | Host-side E2E acceptance for the SwiftTerm monorepo + nested a-Shell. |
| `scripts/esctest-known-good.py` | Python | 58 | 3 | Writes the esctest allowlist from the logs of full esctest runs. |
| `scripts/ios_input_ssh_server.py` | Python | 124 | 1 | Run a loopback SSH echo server for the iOSTerminal sample app. |
| `scripts/prepare-cloudflare-web.sh` | Shell | 52 | 6 | Assemble Web/cloudflare/site from Web/dist (embedded WASM for Pages size limits) |
| `scripts/regen_unicode_width_data.py` | Python | 628 | 3 | Generate the terminal-width lookup. |
| `scripts/serve-named-tunnel-domain.ps1` | PowerShell | 147 | 2 | Named Cloudflare Tunnel -> custom domain (Windows, windows stay open). |
| `scripts/serve-via-cloudflare-tunnel.cmd` | Batch | 31 | 0 |  |
| `scripts/serve-via-cloudflare-tunnel.ps1` | PowerShell | 75 | 1 | Serve SwiftTerm WASM locally and expose it through Cloudflare Quick Tunnel. |
| `scripts/tests/windows-tunnel-common.tests.ps1` | PowerShell | 107 | 3 | Tests for scripts\windows-tunnel-common.ps1 and for the rules every scripts\*.ps |
| `scripts/windows-bringup-toolvip1.ps1` | PowerShell | 94 | 3 | One-shot bring-up for https://toolvip1.top -> local SwiftTerm WASM. |
| `scripts/windows-install-persistent-tunnel.ps1` | PowerShell | 101 | 4 | Install SwiftTerm origin + Cloudflare tunnel as detached Windows processes |
| `scripts/windows-persistent-e2e.cmd` | Batch | 5 | 0 |  |
| `scripts/windows-persistent-e2e.ps1` | PowerShell | 109 | 3 | Persistent Windows E2E launcher for SwiftTerm Cloudflare WASM demo. |
| `scripts/windows-start-my-machine-and-tunnel.ps1` | PowerShell | 51 | 4 | One-shot on the USER Windows PC: |
| `scripts/windows-tunnel-common.ps1` | PowerShell | 128 | 7 | Shared helpers for Windows toolvip1.top tunnel scripts. |

Script a-Shell: 51 file (công thức dựng native, test host/thiết bị) — xem `data/scripts_inventory.csv`.

### 3.2 Entry point (SwiftPM, npm, make, workflow)

| Repo | Loại | Số | Danh sách |
|---|---|---|---|
| ashell | workflow | 4 | app-build.yml[build], native-frameworks.yml[build,node-slice,node,release], openrsync.yml[build,release], pico-framework.yml[build,release] |
| swiftterm | make-target | 13 | all, benchmark-unicode-width, build-fuzzer, check-unicode-width, clone-esctest, esctest-report, open, regen-unicode-width, run-bench, run-fuzzer, run-fuzzer-ghostty, run-fuzzer-ghostty2, test |
| swiftterm | npm-script | 7 | benchmark, build, deploy, domain, preview, test, test:browser |
| swiftterm | swift-executable | 7 | SwiftTermFuzz, SwiftTermFuzz, SwiftTermProfile, SwiftTermWasmSmoke, SwiftTermWebWasm, termcast, web-terminal |
| swiftterm | swift-library | 4 | SwiftTerm, SwiftTerm, SwiftTerm, VTEBenchWorkloads |
| swiftterm | workflow | 5 | cloudflare-pages-web.yml[deploy], docc.yml[build,deploy], web-wasm.yml[released-wasi,browser], windows-scripts.yml[powershell-5-1], xcode.yml[build,esctest,thread-sanitizer,swiftpm-strict-concurrency,swift6-tools,linux-headless] |

### 3.3 Workflow CI

| Repo | Workflow | Trigger | Runner | permissions | Action ghim SHA | Secrets dùng |
|---|---|---|---|---|---|---|
| swiftterm | `cloudflare-pages-web.yml` | push,workflow_dispatch | ubuntu-24.04 | per-job | 0/2 | CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_API_TOKEN |
| swiftterm | `docc.yml` | push,workflow_dispatch | macos-latest,ubuntu-latest | top-level | 0/4 | - |
| swiftterm | `web-wasm.yml` | pull_request,push,workflow_dispatch | ubuntu-24.04,ubuntu-latest | top-level | 0/4 | - |
| swiftterm | `windows-scripts.yml` | pull_request,push,workflow_dispatch | windows-latest | top-level | 1/1 | - |
| swiftterm | `xcode.yml` | pull_request,push | ubuntu-latest,xcode-27 | top-level | 0/8 | - |
| ashell | `app-build.yml` | pull_request,workflow_dispatch | macos-15 | top-level | 2/2 | - |
| ashell | `native-frameworks.yml` | pull_request,push,workflow_dispatch | macos-26,ubuntu-latest | top-level | 0/13 | GITHUB_TOKEN |
| ashell | `openrsync.yml` | pull_request,push,workflow_dispatch | macos-26,ubuntu-latest | top-level | 0/5 | GITHUB_TOKEN |
| ashell | `pico-framework.yml` | pull_request,push,workflow_dispatch | macos-26,ubuntu-latest | top-level | 0/4 | GITHUB_TOKEN |

Kết quả thật của fork trên commit CI đã chọn (nguồn: GitHub API, `data/github_facts.json`, thu thập 2026-11-27T09:25:43Z (UTC) = 2026-11-27 16:25 giờ Việt Nam (UTC+7)):

| Workflow | Trạng thái | Kết luận | Run |
|---|---|---|---|
| WebAssembly browser API | completed | success | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514916 |
| Swift | completed | success | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883 |
| Windows scripts | completed | success | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514950 |

| Job (workflow Swift) | Nhãn runner | Trạng thái | Kết luận |
|---|---|---|---|
| linux-headless | ubuntu-latest | completed | success |
| esctest | xcode-27 | completed | success |
| thread-sanitizer | xcode-27 | completed | success |
| build | xcode-27 | completed | success |
| swiftpm-strict-concurrency | xcode-27 | completed | success |
| swift6-tools | xcode-27 | completed | success |

### 3.4 Host / địa chỉ ngoài

- **swiftterm**: 64 host duy nhất; theo nhóm: Apple/Swift=5, Cloudflare=4, GitHub=5, IP literal=1, JS registries=1, Other=41, Project domain=4, Standards/reference=3. Có xuất hiện trong mã chạy/web/sample (không tính tài liệu chuẩn): 14 host.
- **ashell**: 66 host duy nhất; theo nhóm: Apple/Swift=1, GitHub=5, JS registries=3, Other=49, Package ecosystems=3, Standards/reference=5. Có xuất hiện trong mã chạy/web/sample (không tính tài liệu chuẩn): 53 host.

Tên miền dự án trong mã nguồn SwiftTerm:

| Host | Số lần | Vùng | Vị trí đầu tiên |
|---|---|---|---|
| tooltop1.vip | 35 | ci-dev-tooling,docs-evidence,documentation | Docs/domain-tooltop1-vip-blocker.md:3 |
| toolvip1.top | 105 | ci-dev-tooling,docs-evidence,documentation,web-runtime | Web/cloudflare/wrangler.toml:2 |
| www.tooltop1.vip | 3 | documentation | Docs/domain-tooltop1-vip-blocker.md:32 |
| www.toolvip1.top | 21 | ci-dev-tooling,docs-evidence,documentation,web-runtime | .github/workflows/cloudflare-pages-web.yml:2 |

### 3.5 Điểm thực thi lệnh / socket / WebView (heuristic có đối chứng, sau khi hạ mức khi thấy biện pháp bảo vệ)

Tổng **130** điểm: HIGH=7, MEDIUM=65, LOW=45, INFO=13. Trong 72 điểm HIGH/MEDIUM: CHƯA RÀ THỦ CÔNG=34, theo thiết kế=17, thư viện bên thứ ba=9, mã kiểm thử=8, đã thành phát hiện=3, công cụ dev=1.

| Repo | Quy tắc | File | Số điểm | Đánh giá thủ công | Lý do |
|---|---|---|---|---|---|
| ashell | js-eval-in-webview | `WkWebViewExtension.swift` | 2 | CHƯA RÀ THỦ CÔNG |  |
| ashell | js-eval-in-webview | `a-Shell/SceneDelegate+TerminalView.swift` | 4 | CHƯA RÀ THỦ CÔNG |  |
| ashell | js-eval-in-webview | `a-Shell/SceneDelegate.swift` | 13 | CHƯA RÀ THỦ CÔNG |  |
| ashell | js-eval-in-webview | `a-Shell/WKWebView+InputAssistant.swift` | 12 | CHƯA RÀ THỦ CÔNG |  |
| ashell | js-eval-in-webview | `a-Shell/WKWebView+KeyCommands.swift` | 1 | CHƯA RÀ THỦ CÔNG |  |
| swiftterm | shell-true | `scripts/audit/test_audit.py` | 1 | CHƯA RÀ THỦ CÔNG |  |
| swiftterm | tls-verify-off | `scripts/audit/audit_security.py` | 1 | CHƯA RÀ THỦ CÔNG |  |
| ashell | child-process | `node/child-process-test.cjs` | 6 | mã kiểm thử | mã kiểm thử |
| ashell | dom-injection | `hterm_all.js` | 9 | thư viện bên thứ ba | thư viện hterm đóng gói sẵn |
| ashell | dynamic-symbol | `a-Shell/AppDelegate.swift` | 1 | theo thiết kế | dò khả năng: dlsym(..., "ios_posix_spawn") != nil |
| ashell | eval | `require.js` | 1 | theo thiết kế | bộ nạp module CommonJS: new Function bọc mã module trong bộ nhớ đệm của app |
| ashell | eval | `require_jscore.js` | 1 | theo thiết kế | bộ nạp module CommonJS: new Function bọc mã module trong bộ nhớ đệm của app |
| ashell | network-listener | `a-Shell/Relay.swift` | 1 | theo thiết kế | Relay: opt-in, mặc định 127.0.0.1, TLS bắt buộc, token 32-256 ký tự, mTLS tuỳ chọn |
| ashell | process-spawn | `a-Shell-Intents/ExecuteCommandIntentHandler.swift` | 1 | theo thiết kế | đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent) |
| ashell | process-spawn | `a-Shell-LongCommands/ExecuteLongCommandIntent.swift` | 1 | theo thiết kế | đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent) |
| ashell | process-spawn | `a-Shell/ExtraCommands.swift` | 1 | theo thiết kế | đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent) |
| ashell | process-spawn | `a-Shell/Relay.swift` | 1 | theo thiết kế | Relay thực thi lệnh nhận qua TLS + token |
| ashell | process-spawn | `a-Shell/SceneDelegate.swift` | 5 | theo thiết kế | đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent) |
| ashell | process-spawn | `a-Shell/Util/jsc.swift` | 1 | theo thiết kế | đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent) |
| ashell | tls-trust-bypass | `a-Shell/SceneDelegate.swift` | 3 | đã thành phát hiện | xem phát hiện về handler chấp nhận mọi server-trust |
| swiftterm | child-process | `Tests/WebWasmTests/corpus.test.mjs` | 2 | mã kiểm thử | mã kiểm thử |
| swiftterm | js-eval-in-webview | `Tools/BidiHarness/BidiHarness/HarnessViewController.swift` | 1 | công cụ dev | harness phát triển, không phát hành |
| swiftterm | process-spawn | `Sources/SwiftTerm/Pty.swift` | 2 | theo thiết kế | LocalProcess: forkpty/execve chạy shell do app nhúng chỉ định |
| swiftterm | process-spawn | `Sources/SwiftTermBuildInfoGenerator/BuildInfoGenerator.swift` | 1 | theo thiết kế | công cụ build: chạy git với tham số cố định (-C <repo>) |

Điểm đã hạ xuống INFO vì thấy biện pháp bảo vệ ngay trước đó (đọc từ mã, không suy đoán):

| Repo | Quy tắc | Vị trí | Lý do hạ mức |
|---|---|---|---|
| swiftterm | network-listener | `TerminalApp/WebTerminal/Sources/WebTerminalServer/HTTPServer.swift:98` | listener chỉ loopback hoặc Unix domain socket |
| swiftterm | http-listener | `Tests/WebWasmTests/browser.mjs:24` | listener chỉ loopback |
| swiftterm | network-listener | `Tools/BidiHarness/BidiHarness/SocketControlServer.swift:58` | listener chỉ loopback hoặc Unix domain socket |
| swiftterm | archive-extractall | `scripts/audit/test_audit.py:257` | từng member được kiểm đường dẫn trước khi giải nén |
| swiftterm | archive-extractall | `scripts/audit/test_audit.py:259` | từng member được kiểm đường dẫn trước khi giải nén |
| ashell | archive-extractall | `ci/audit-artifact.py:245` | từng member được kiểm đường dẫn trước khi giải nén |
| ashell | unsafe-string | `helix/command.m:92` | độ dài đã được kiểm ngay trước đó |
| ashell | rm-rf-variable | `navi/build.sh:93` | biến có bảo vệ ${var:?} |
| ashell | rm-rf-variable | `scripts/build-openrsync.sh:87` | biến có bảo vệ ${var:?} |
| ashell | rm-rf-variable | `scripts/build-openrsync.sh:92` | biến có bảo vệ ${var:?} |
| ashell | rm-rf-variable | `scripts/build-pico.sh:106` | biến có bảo vệ ${var:?} |
| ashell | rm-rf-variable | `scripts/build-pico.sh:111` | biến có bảo vệ ${var:?} |
| ashell | insecure-tls | `scripts/verify_ashell_integrity.sh:150` | chỉ gọi loopback (chứng chỉ tự ký) |

Đã đọc tay các nhóm: `rm -rf $VAR` (28 điểm, đích đều là thư mục tạm hoặc artefact build, 5 điểm có `${var:?}`); `archive.extractall` ở `ci/audit-artifact.py` (kiểm `is_relative_to` và loại symlink từng member trước khi giải nén); `strcpy` ở `helix/command.m` (độ dài kiểm ngay trước); `curl -k` chỉ gọi `https://127.0.0.1`; `irm … | iex` ở `windows-start-my-machine-and-tunnel.ps1` chỉ là dòng `Write-Host` hướng dẫn. Các script tunnel cài `cloudflared` bằng `winget`, không tải file trần. Listener thật: SwiftTerm — `WebTerminal/HTTPServer.swift` (Hummingbird, `127.0.0.1`), `BidiHarness/SocketControlServer.swift` (Unix domain socket); a-Shell — `Relay.swift` (`NWListener`, TLS) và máy chủ HTTPS loopback phục vụ WASM trong `AppDelegate.swift`.

**Nội suy chuỗi vào JS của WebView (detector `js_escape_checks`)** — trên 32 điểm `evaluateJavaScript` của a-Shell chỉ có 3 điểm thiếu escape:

| Vị trí | Loại | Giống upstream | Mã |
|---|---|---|---|
| `a-Shell/SceneDelegate+TerminalView.swift:697` | js-interpolation-unescaped | có | `webView?.evaluateJavaScript("inputString += '\(commandBeforeCursor + string)'; commandIsRu` |
| `a-Shell/SceneDelegate.swift:1134` | js-escape-missing-quote | có | `self.webView?.evaluateJavaScript("document.execCommand(\"insertText\", false, \"" + title.` |
| `a-Shell/SceneDelegate.swift:4629` | js-interpolation-unescaped | có | `webView?.evaluateJavaScript("window.homedir = '\(homeurl)';")` |

## 4. Bảng lệnh: lệnh gốc, lệnh trên mã nguồn, lệnh lỗi, lệnh gọi sai

Bảng đầy đủ **251 tên lệnh** (mọi catalogue và host built-in, so ba nguồn): [`commands-master-table.md`](commands-master-table.md) và `data/commands_master.csv`; bảng lệnh gọi sai đầy đủ: [`wrong-calls-table.md`](wrong-calls-table.md). *Lệnh gốc* = `holzschu/a-shell` master; *lệnh trên mã nguồn* = fork master và commit SwiftTerm ghim.

### 4.1 Kích thước catalogue (đếm trực tiếp từ plist)

| Catalogue | File | Gốc (upstream) | Fork | Pin SwiftTerm |
|---|---|---|---|---|
| full | `Resources/commandDictionary.plist` | 158 | 158 | 158 |
| mini | `Resources_mini/commandDictionary.plist` | 136 | 136 | 136 |
| extra | `Resources/extraCommandsDictionary.plist` | 8 | 8 | 8 |
| llvm | `Resources/llvmDictionary.plist` | 10 | 10 | 10 |
| tex | `Resources/texCommandsDictionary.plist` | 31 | 31 | 31 |
| luatex | `Resources/luatexCommandsDictionary.plist` | 7 | 7 | 7 |
| sshStock | `Resources_mini/sshStockCommands.plist` | 4 | 4 | 4 |

**Đối chiếu định nghĩa:** fork ≡ upstream cho **251/251** tên lệnh; pin ≡ fork cho **251/251**; lệnh do fork đưa lỗi vào: **0**. Về định nghĩa lệnh, fork không làm khác nhà sản xuất; khác biệt nằm ở build/test (mục 1 và 6).

### 4.2 Nguồn cung cấp lệnh

| Nguồn cung cấp | Số lệnh |
|---|---|
| xcfs-binaryTarget | 169 |
| host-builtin only | 39 |
| in-repo recipe | 15 |
| undeclared artifact | 12 |
| linked-prebuilt | 11 |
| downloadFrameworks.sh tarball | 3 |
| system-dylib | 2 |

### 4.3 Ma trận target × catalogue

| Target | Catalogue dùng | Số lệnh trong catalogue | Số mục framework/module nhúng (gồm module Python) | Framework catalogue cần nhưng KHÔNG nhúng |
|---|---|---|---|---|
| a-Shell | full | 158 | 529 | — |
| a-Shell-mini | mini | 136 | 237 | — |
| a-Shell-noPython | mini | 136 | 38 | Python, WasmKitCommand, blink, curl-impersonate, multimarkdown, openrsync, pico |

### 4.4 Lệnh có lỗi, rủi ro hoặc chưa xác minh (tĩnh)

**LỖI CẤU HÌNH (xác nhận được bằng tĩnh)** — 12 lệnh

| Mã | Mô tả | Số lệnh | Nguồn gốc | Lệnh |
|---|---|---|---|---|
| D01 | Target nhúng thiếu framework của lệnh nằm trong catalogue của chính target đó | 10 | upstream-original: 10 | blink, curl-impersonate, multimarkdown, openrsync, pico, python, python3, python3.13, rsync, wasmkit |
| D04 | Cùng một lệnh khai báo khác nhau giữa catalogue `full` và `mini` (argtype) | 2 | upstream-original: 2 | basename, dirname |
| D08 | Dòng catalogue sai dạng hoặc argtype ngoài tập nhà sản xuất dùng | 0 | — | — |

**KHOẢNG TRỐNG NGUỒN GỐC / CHUỖI CUNG ỨNG (rủi ro, chưa phải lỗi chạy)** — 8 lệnh

| Mã | Mô tả | Số lệnh | Nguồn gốc | Lệnh |
|---|---|---|---|---|
| D07 | Không truy được nguồn tái tạo framework (không có binaryTarget, không có công thức trong repo) | 5 | upstream-original: 5 | blink, cbc, curl-impersonate, multimarkdown, wasmkit |
| D10 | Framework lấy từ tarball tải về không kiểm checksum | 3 | upstream-original: 3 | python, python3, python3.13 |

**CHƯA XÁC MINH (cần nhị phân prebuilt hoặc thiết bị)** — 37 lệnh

| Mã | Mô tả | Số lệnh | Nguồn gốc | Lệnh |
|---|---|---|---|---|
| D05 | Đăng ký host `replaceCommand` trỏ vào symbol không định nghĩa trong mã nguồn repo | 37 | upstream-original: 37 | amstex, bibtex, cslatex, csplain, dvilualatex, dviluatex, dvipdfmx, eplain, etex, euptex, jadetex, latex, lualatex, luatex, … (+23) |

Tổng hợp: 12 lệnh có lỗi cấu hình, 8 lệnh có khoảng trống nguồn gốc, 37 lệnh TeX chưa xác minh symbol; **50** lệnh có mã lỗi đều là lỗi gốc của nhà sản xuất (xuất hiện y hệt ở upstream), **0** do fork; 201 lệnh không có mã nào mà bộ phát hiện kiểm được.

D01 chỉ xảy ra ở target `a-Shell-noPython`: target dùng catalogue `mini` nhưng chỉ nhúng một phần framework; giống hệt upstream và có thể là chủ ý cho biến thể CI (cần chủ dự án xác nhận), nên không tính là lỗi của fork.

Giới hạn: kiểm tĩnh KHÔNG chứng minh lệnh chạy được. Với 169 lệnh nguồn `xcfs-binaryTarget` và 11 lệnh `SELF`, symbol nằm trong nhị phân prebuilt mà VM không tải được (release asset bị chặn); việc đối chiếu `[framework, symbol]` với symbol export thật chưa được làm (mục 6.5, việc 2).

### 4.5 Host built-in (đăng ký bằng `replaceCommand`)

- **93 lượt đăng ký / 80 tên**. Giống upstream: 93/93.
- **39 lệnh chỉ tồn tại dưới dạng host built-in** (không nằm trong plist): bookmark, call, clear, config, credits, d, deactivate, deletemark, downloadFile, downloadFolder, exit, g, help, herdr, hideKeyboard, hideToolbar, history, isForeground, jump, keepDirectoryAfterShortcut, l, newWindow, p, photos, pickFolder, play, progress, r, relay, renamemark, repeatCommand, s, showToolbar, showmarks, text, updateCommands, view, wasm, z.
- **13 tên đăng ký 2 lần** (`ShellWorkers/Worker.m`, `a-Shell/AppDelegate.swift`): bookmark, clear, codex, d, deletemark, g, jump, l, p, r, renamemark, s, showmarks.
- **37 lượt đăng ký TeX** trỏ vào symbol `luatex`, `tex` không định nghĩa trong repo (nằm trong framework tải theo nhu cầu): amstex, bibtex, cslatex, csplain, dvilualatex, dviluatex, dvipdfmx, eplain, etex, euptex, jadetex, latex, lualatex, luatex, makeindex, mex, mllatex, mltex, pdfcslatex, pdfcsplain, pdfetex, pdfjadetex, pdflatex, pdfmex, pdftex, pdfxmltex, tex, texlua, texluac, texsis, uplatex, uptex, utf8mex, xdvipdfmx, xelatex, xetex, xmltex.

### 4.6 Lệnh gọi sai (script / tài liệu / CI / cấu hình) — trước và sau khi sửa

| Loại | Mô tả | Mức | Trước (`1f7528c068`) | Sau | Ví dụ vị trí |
|---|---|---|---|---|---|
| `shebang-not-executable` | File có shebang nhưng git mode ≠ 100755 | LOW | 33 | 33 | `Tools/generate_kitty_parity_matrix.py`; `Tools/import-ghostty-fuzz-corpus.swift`; `scripts/esctest-known-good.py` |
| `wrong-domain-reference` | Tên miền sai `tooltop1.vip` (tên miền thật `toolvip1.top`) | MEDIUM | 19 | 0 | `.github/workflows/cloudflare-pages-web.yml:2`; `.github/workflows/cloudflare-pages-web.yml:3`; `.github/workflows/cloudflare-pages-web.yml:35` |
| `ps1-hardcoded-root` | PowerShell gắn cứng gốc repo `%USERPROFILE%\Documents\SwiftTerm` | MEDIUM | 12 | 0 | `scripts/serve-named-tunnel-domain.ps1:9`; `scripts/serve-named-tunnel-domain.ps1:22`; `scripts/serve-via-cloudflare-tunnel.ps1:5` |
| `workflow-unpinned-actions` | Action tham chiếu bằng tag, không ghim SHA | LOW | 7 | 7 | `.github/workflows/cloudflare-pages-web.yml`; `.github/workflows/docc.yml`; `.github/workflows/web-wasm.yml` |
| `broken-doc-link` | Liên kết markdown hỏng | LOW | 6 | 6 | `Docs/osc7501-delta.md:5`; `Docs/osc7501-delta.md:122`; `Docs/osc7501-delta.md:148` |
| `broken-doc-path` | Tài liệu nêu đường dẫn không tồn tại | LOW | 4 | 4 | `Apps/README.md:17`; `Docs/security-audit-egress-2026-11-26.md:180`; `Docs/system-comparison-report-2026-11-26.md:239` |
| `workflow-permissions` | Workflow không khai báo `permissions:` | LOW | 2 | 0 | `.github/workflows/web-wasm.yml`; `.github/workflows/xcode.yml` |
| `ps1-no-bom` | PowerShell: thiếu UTF-8 BOM (PowerShell 5.1 đọc ANSI) | LOW | 1 | 0 | `scripts/serve-via-cloudflare-tunnel.ps1` |

Tổng: trước **84**, sau **50**. Chi tiết từng dòng (cả phần đã khắc phục): [`wrong-calls-table.md`](wrong-calls-table.md).

Đã kiểm và **không phát hiện** lỗi ở các nhóm (detector có đối chứng dương trong `test_audit.py`): gọi script không tồn tại, `swift run/build` sai tên product, `npm run` sai script, `make` sai target, `gh workflow run` sai file, tham số hàm helper PowerShell sai, `--filter` của CI không khớp test, đường dẫn/exclude/resource sai trong `Package.swift`.

## 5. Cầu nối HostHelpers (SwiftTerm ⇄ a-Shell)

`AppleTerminalView+HostHelpers.swift` khai báo **21** thành viên public (bao bởi `#if os(iOS) || os(visionOS)`); a-Shell gọi **19**, 2 không ai dùng, 17 API a-Shell dùng nhưng SwiftTerm không có test. Script E2E liệt kê 21 tên nhưng nhãn ghi "20 APIs" (lỗi thời).

| API | Loại | Trạng thái | Số chỗ a-Shell gọi | Số tham chiếu test SwiftTerm | Vị trí gọi đầu tiên |
|---|---|---|---|---|---|
| `getTerminal` | func | a-Shell dùng, SwiftTerm không test | 26 | 0 | a-Shell/ContentView.swift:938 |
| `isCurrentBufferAlternate` | var | a-Shell dùng + có test SwiftTerm | 4 | 7 | a-Shell/SceneDelegate+TerminalView.swift:1625 |
| `getLastLine` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate.swift:2850 |
| `getLastPrompt` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1616 |
| `setPromptEnd` | func | a-Shell dùng, SwiftTerm không test | 5 | 0 | a-Shell/SceneDelegate+TerminalView.swift:926 |
| `getNewContent` | func | a-Shell dùng, SwiftTerm không test | 2 | 0 | a-Shell/SceneDelegate.swift:6146 |
| `saveCursorPosition` | func | a-Shell dùng, SwiftTerm không test | 21 | 0 | a-Shell/SceneDelegate+TerminalView.swift:562 |
| `restoreCursorPosition` | func | a-Shell dùng, SwiftTerm không test | 17 | 0 | a-Shell/SceneDelegate+TerminalView.swift:564 |
| `setCursorPosition` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1687 |
| `getCurrentChar` | func | không ai dùng | 0 | 0 | — |
| `moveUpIfNeeded` | func | a-Shell dùng, SwiftTerm không test | 6 | 0 | a-Shell/SceneDelegate+TerminalView.swift:776 |
| `moveDownIfNeeded` | func | a-Shell dùng, SwiftTerm không test | 2 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1067 |
| `atTheEndOfTheLine` | func | không ai dùng | 0 | 0 | — |
| `moveToBeginningOfLine` | func | a-Shell dùng, SwiftTerm không test | 17 | 0 | a-Shell/SceneDelegate+TerminalView.swift:854 |
| `moveToEndOfLine` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1268 |
| `clearToEndOfLine` | func | a-Shell dùng, SwiftTerm không test | 21 | 0 | a-Shell/SceneDelegate+TerminalView.swift:489 |
| `wipeContents` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate.swift:4207 |
| `setCursorStyle` | func | a-Shell dùng + có test SwiftTerm | 4 | 3 | a-Shell/SceneDelegate.swift:3029 |
| `moveToEndOfSelection` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1036 |
| `moveToBeginningOfSelection` | func | a-Shell dùng, SwiftTerm không test | 1 | 0 | a-Shell/SceneDelegate+TerminalView.swift:1005 |
| `deleteSelection` | func | a-Shell dùng, SwiftTerm không test | 2 | 0 | a-Shell/SceneDelegate+TerminalView.swift:771 |

## 6. Kiểm thử chức năng: cái gì đạt, cái gì chưa, cái gì đang được dùng

### 6.1 Thang độ mạnh của bằng chứng (để không gọi "ĐẠT" khi chỉ có grep)

| Mức | Ý nghĩa | Ví dụ trong dự án |
|---|---|---|
| L0 | Hiện diện tĩnh (grep/đọc plist/đọc mã) | mục HostHelpers của `e2e_acceptance_host.sh`; các detector của báo cáo này |
| L1 | Chạy script host thật (không cần Apple) | `tests/ssh-stock-registration.sh`, `tests/worker-binding.sh` qua shim `plutil`; E2E host |
| L2 | Test đơn vị thực thi | CI `linux-headless`: XCTest + Swift Testing |
| L3 | Biên dịch trên nền tảng Apple | workflow `Swift` (`xcode.yml`): `swift build`, `xcodebuild` MacTerminal/iOSTerminal (mục 6.3) |
| L4 | Chạy thật trên thiết bị | 158 lệnh a-Shell: `PENDING_USER_DEVICE` |

### 6.2 Kết quả chạy thật (lệnh + kết quả)

| Nguồn | Bộ test | Kết quả | Chi tiết |
|---|---|---|---|
| upstream | `a-Shell tests/ssh-stock-registration.sh catalog` | PASS | Stock SSH catalog check passed |
| upstream | `a-Shell tests/ssh-stock-registration.sh project` | PASS | Stock SSH project check passed |
| upstream | `a-Shell tests/ssh-stock-registration.sh activation-wiring` | PASS | Stock SSH activation-wiring check passed |
| upstream | `a-Shell tests/worker-binding.sh` | PASS | PASS generated host binding and all ten worker source references |
| fork | `a-Shell tests/ssh-stock-registration.sh catalog` | PASS | Stock SSH catalog check passed |
| fork | `a-Shell tests/ssh-stock-registration.sh project` | PASS | Stock SSH project check passed |
| fork | `a-Shell tests/ssh-stock-registration.sh activation-wiring` | PASS | Stock SSH activation-wiring check passed |
| fork | `a-Shell tests/worker-binding.sh` | FAIL | FAIL worker targets do not compile the generated Worker.swift |
| pin | `a-Shell tests/ssh-stock-registration.sh catalog` | PASS | Stock SSH catalog check passed |
| pin | `a-Shell tests/ssh-stock-registration.sh project` | PASS | Stock SSH project check passed |
| pin | `a-Shell tests/ssh-stock-registration.sh activation-wiring` | PASS | Stock SSH activation-wiring check passed |
| pin | `a-Shell tests/worker-binding.sh` | FAIL | FAIL worker targets do not compile the generated Worker.swift |
| swiftterm | `SwiftTerm scripts/e2e_acceptance_host.sh (static greps + dry-run)` | PASS | {"pass": 67, "warn": 1, "fail": 0, "skip": 2} |
| swiftterm | `scripts/audit/test_audit.py (bộ phát hiện, đối chứng dương/âm)` | PASS | Ran 56 tests |

Chạy lại: `python3 scripts/audit/run_audit.py --ashell <a-shell> --run-tests`. Đối chứng: `worker-binding.sh` upstream PASS; fork FAIL; pin FAIL ⇒ nguyên nhân nằm ở trạng thái fork (xem phát hiện về fork tụt hậu), không phải ở môi trường chạy.

### 6.3 CI thật của fork (SwiftTerm)

- Job `linux-headless` (id 140070606717, run 45866514883, commit `140ef93809`, `ubuntu-latest`): **78 XCTest** đạt, 0 lỗi + **1190 test Swift Testing / 94 suite** đạt. Log: `Executed 78 tests, with 0 failures (0 unexpected) in 1.351 (1.351) seconds` · `✔ Test run with 1190 tests in 94 suites passed after 68.377 seconds.`.
- Job macOS (`xcode-27`) của 8 run gần nhất của workflow `Swift`: 37/40 đã được runner nhận (chờ 5–199 phút), 37 xong sau khi có runner (success=37), 0 đang chạy, 0 còn `queued`, 3 kết thúc khi chưa có runner.
- Workflow `Swift` (run 45866514883, commit `140ef93809`, `completed`/`success`). Cây mã Apple của commit này so với bản kiểm toán: `Package.swift`, `Sources`, `Tests`, `TerminalApp` giống hệt `HEAD` (so tree hash) ⇒ kết quả áp dụng cho mã đang kiểm.

| Job | Nhãn runner | Trạng thái | Kết luận | Bước đạt | Bắt đầu | Liên kết |
|---|---|---|---|---|---|---|
| `linux-headless` | ubuntu-latest | completed | success | 9/9 | 00:17 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606717 |
| `esctest` | xcode-27 | completed | success | 9/9 | 00:51 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606760 |
| `thread-sanitizer` | xcode-27 | completed | success | 5/5 | 00:50 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606770 |
| `build` | xcode-27 | completed | success | 13/13 | 00:56 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606772 |
| `swiftpm-strict-concurrency` | xcode-27 | completed | success | 5/5 | 00:54 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606796 |
| `swift6-tools` | xcode-27 | completed | success | 7/7 | 00:51 (UTC+7) | https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514883/job/140070606938 |

- Log job `swiftpm-strict-concurrency` (`swift build --target SwiftTerm -Xswiftc -strict-concurrency=complete`): image `xcode-27-arm64`, macOS 27.0.1 (build 26A434), Xcode 27.1; kết quả `Build complete! (75.52 sec)`; 3 cảnh báo biên dịch: `Sources/SwiftTerm/Mac/MacTerminalView.swift:1388:16`; `Sources/SwiftTerm/Mac/MacTerminalView.swift:1400:16`; `Sources/SwiftTerm/Mac/MacTerminalView.swift:4915:45`.

- Log job `build` (`xcodebuild` + `swift build -v` + `swift test`): `** BUILD SUCCEEDED **` ×2 (MacTerminal, iOSTerminal), `** BUILD FAILED **` ×0, `swift build` "Build complete!" ×4; `AppleTerminalView+HostHelpers.swift` có dòng `SwiftCompile` trong: `MacTerminal.xcodeproj`, `iOSTerminal.xcodeproj`; kết quả test: `Executed 15 tests, with 0 failures (0 unexpected) in 0.018 (0.021) seconds` · `Executed 159 tests, with 0 failures (0 unexpected) in 2.265 (2.296) seconds` · `Executed 159 tests, with 0 failures (0 unexpected) in 2.265 (2.298) seconds` · `✔ Test run with 2270 tests in 203 suites passed after 132.819 seconds.`.

- Script Windows (`scripts/*.ps1`) chạy thật bằng Windows PowerShell 5.1 trên runner Windows (workflow `Windows scripts`, `scripts/tests/windows-tunnel-common.tests.ps1`):

| Phiên bản script | Hệ điều hành | PowerShell | Check đạt | Check lỗi | Kết luận của bộ test | Lỗi làm dừng |
|---|---|---|---|---|---|---|
| script đã sửa (HEAD) | Microsoft Windows Server 2025 | 5.1.26100.33822 | 52 | 0 | ALL PASSED | — |
| script trước khi sửa (đối chứng đột biến) | Microsoft Windows Server 2025 | 5.1.26100.33822 | 29 | 7 | bộ test dừng giữa chừng | Get-SwiftTermRoot : The term 'Get-SwiftTermRoot' is not recognized as the name of a cmdlet, function, script file, or |

  Check lỗi trên bản trước khi sửa: `no Documents-based repo root in serve-named-tunnel-domain.ps1`; `bom serve-via-cloudflare-tunnel.ps1`; `no Documents-based repo root in serve-via-cloudflare-tunnel.ps1`; `no Documents-based repo root in windows-bringup-toolvip1.ps1`; `no Documents-based repo root in windows-install-persistent-tunnel.ps1`; `no Documents-based repo root in windows-persistent-e2e.ps1`; `no Documents-based repo root in windows-start-my-machine-and-tunnel.ps1`. Bộ test **đỏ trên bản lỗi và xanh trên bản đã sửa** nên phân biệt được hai trạng thái.

  Run trên commit CI đã chọn: `completed`/`success` — https://github.com/jiaomeimei0-prog/SwiftTerm/actions/runs/45866514950

- Số test khai báo tĩnh trong `Tests/` (regex; `@Test` có tham số tính 1) — không so trực tiếp với số đã chạy:

| Test target | File | XCTest (khai báo) | @Test (khai báo) |
|---|---|---|---|
| SwiftTermTests | 210 | 876 | 2.291 |
| SwiftTermWebWasmTests | 3 | 22 | 0 |
| SwiftTermEmbeddedTests | 1 | 0 | 11 |

### 6.4 Ma trận chức năng: đạt / chưa / đang được dùng

| Chức năng | Ai dùng | Bằng chứng hiện có | Mức | Kết luận |
|---|---|---|---|---|
| Lõi emulator (parser, buffer, headless) | a-Shell, Web/WASM, TerminalApp | CI `linux-headless`: 78 XCTest (0 lỗi) + 1190 Swift Testing (passed) | L2 | ĐẠT (phần chạy trên Linux) |
| View/renderer macOS (AppKit) | TerminalApp macOS | workflow Swift: `swiftpm-strict-concurrency` đạt; bước `Xcode Mac Build` đạt | L3 | BIÊN DỊCH ĐẠT (Xcode 27.1); chưa chạy |
| View/renderer iOS (UIKit) | a-Shell iOS | workflow Swift: bước `Xcode iOS Build` đạt | L3 | BIÊN DỊCH ĐẠT; chưa chạy |
| Test trên macOS (`swift test`) | SwiftTerm | workflow Swift: bước `Run tests` đạt | L2 | ĐẠT (macOS) |
| HostHelpers (21 API) | a-Shell | bước `Xcode iOS Build` đạt, log có dòng `SwiftCompile … AppleTerminalView+HostHelpers.swift` trong `iOSTerminal.xcodeproj` (biên dịch cả phần `os(iOS)`); 17 API a-Shell dùng nhưng SwiftTerm không test | L3 | BIÊN DỊCH ĐẠT; hành vi chưa kiểm |
| Định nghĩa catalogue (158/136 lệnh) | a-Shell | plist đọc được; fork≡upstream≡pin: 251/251 lệnh; `ssh-stock-registration.sh`: upstream PASS; fork PASS; pin PASS | L1 | ĐẠT |
| Chạy thật các lệnh | Người dùng cuối | Chưa có | L4 | PENDING_USER_DEVICE |
| Gắn Worker A–J (`worker-binding.sh`) | a-Shell | upstream PASS; fork FAIL; pin FAIL | L1 | KHÔNG ĐẠT (fork, pin) |
| Build Web/WASM | Người dùng web | CI `WebAssembly browser API`: completed/success | L2 | ĐẠT (build) |
| Deploy Cloudflare Pages | Công chúng | Workflow cố ý thất bại khi thiếu secrets | — | CHƯA (thiếu `CLOUDFLARE_*`) |
| Tunnel Windows (PowerShell): cú pháp, mã hoá, hàm helper | Máy người dùng | workflow `Windows scripts` (PowerShell 5.1): completed/success | L2 | ĐẠT (cú pháp + helper) |
| Tunnel Windows: chạy thật (cloudflared + tên miền) | Máy người dùng | Không có `cloudflared` và tên miền trong CI | — | Chưa chạy thật |
| Tên miền `toolvip1.top` | Công chúng | Probe từ VM không hợp lệ (egress allowlist) | — | CHƯA XÁC MINH từ bên ngoài |

Về "đang được sử dụng": với HostHelpers, mức dùng đo được bằng số chỗ a-Shell gọi (mục 5). Với từng lệnh a-Shell, mức dùng thật chỉ đo được trên thiết bị — không có telemetry.

### 6.5 Việc kiểm thử còn thiếu và cách đóng

1. **Biên dịch macOS/iOS** — đã có sẵn trong workflow `Swift` gốc (`xcode.yml`, nhãn `xcode-27`): `xcodebuild` MacTerminal/iOSTerminal + `swift build` + `swift test` (phủ `HostHelpers`), không cần workflow riêng. Cả ba kết quả đã có (mục 6.3).
2. **Symbol nhị phân prebuilt** — đối chiếu `[framework, symbol]` của plist với `nm -gU` sau khi kiểm SHA-256 (chưa làm; cần job riêng).
3. **158 lệnh trên thiết bị** — `scripts/verify_command_catalogue_158.sh` trong app; ma trận chờ ở `Docs/command-158-device-matrix-PENDING.csv`.
4. **Tên miền** — probe từ GitHub Actions hoặc máy người dùng, không dùng VM.

## 7. Rà soát an ninh

### 7.1 Workflow

| Repo | Workflow | permissions | Action tag/SHA | Secrets |
|---|---|---|---|---|
| swiftterm | `cloudflare-pages-web.yml` | per-job | 2 tag / 0 SHA | CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_API_TOKEN |
| swiftterm | `docc.yml` | top-level | 4 tag / 0 SHA | - |
| swiftterm | `web-wasm.yml` | top-level | 4 tag / 0 SHA | - |
| swiftterm | `windows-scripts.yml` | top-level | 0 tag / 1 SHA | - |
| swiftterm | `xcode.yml` | top-level | 8 tag / 0 SHA | - |
| ashell | `app-build.yml` | top-level | 0 tag / 2 SHA | - |
| ashell | `native-frameworks.yml` | top-level | 13 tag / 0 SHA | GITHUB_TOKEN |
| ashell | `openrsync.yml` | top-level | 5 tag / 0 SHA | GITHUB_TOKEN |
| ashell | `pico-framework.yml` | top-level | 4 tag / 0 SHA | GITHUB_TOKEN |

### 7.2 Quét bí mật (giá trị luôn bị che)

| Repo | Loại | Mức heuristic | Vị trí | Giá trị (đã che) | Ghi chú / phát hiện liên quan |
|---|---|---|---|---|---|
| ashell | private-key-block | CRITICAL | `localCertificateKey.pem:1` | PRIVATE KEY block header | → F-006 |
| ashell | key-or-certificate-file | INFO | `cacert.pem` | 200116 bytes | tracked key/cert material; verify purpose and key type |
| ashell | key-or-certificate-file | INFO | `localCertificate.pem` | 1302 bytes | tracked key/cert material; verify purpose and key type |
| ashell | key-or-certificate-file | INFO | `localCertificate.pfx` | 2517 bytes | tracked key/cert material; verify purpose and key type |
| ashell | key-or-certificate-file | INFO | `localCertificateKey.pem` | 1675 bytes | tracked key/cert material; verify purpose and key type |

Mức "heuristic" là mức của detector; đánh giá cuối cùng nằm ở danh sách phát hiện (mục 9). Không phát hiện token GitHub/AWS/Slack/Stripe/Google hay `CLOUDFLARE_API_TOKEN` dạng literal ở HEAD của hai repo (quét theo mẫu, không kiểm tra hiệu lực).

### 7.3 Phát hiện đọc mã (không chạy được trên VM)

- **Chấp nhận mọi chứng chỉ trong WebView** — `a-Shell/SceneDelegate.swift:6338-6342`: `webView(_:didReceive:)` dựng `URLCredential(trust: challenge.protectionSpace.serverTrust!)` rồi gọi `completionHandler(.useCredential, cred)` cho mọi challenge (không kiểm host/`authenticationMethod`).
- **Server HTTPS WASM** — `a-Shell/AppDelegate.swift:44-75`: `LocalHTTPServer` bind `127.0.0.1`, chỉ `GET`, chặn path traversal (`resolvingSymlinksInPath` + `hasPrefix(base)`), nhưng nạp `localCertificate.pfx` bằng passphrase `"password"` và khoá riêng nằm trong repo công khai.
- **Relay (lệnh từ xa)** — `a-Shell/Relay.swift`: opt-in, mặc định `127.0.0.1`, TLS bật, token 32–256 ký tự so sánh hằng thời gian, mTLS tuỳ chọn. Rủi ro khi `bind=0.0.0.0` mà không bật mTLS.
- **WebTerminal (PTY qua WebSocket)** — `TerminalApp/WebTerminal/.../HTTPServer.swift:98` bind `127.0.0.1`; WebSocket yêu cầu `Host` loopback và `Origin` khớp. Hệ quả: không thể phơi server này qua Cloudflare tunnel (đúng thiết kế an toàn).
- **Tunnel Windows** — các script chỉ phơi `python -m http.server <port> --bind 127.0.0.1` phục vụ thư mục site tĩnh qua `cloudflared`; không có PTY. Rủi ro còn lại: nếu thư mục phục vụ trỏ nhầm vào gốc repo thì lộ cả `.git`.

## 8. Tài liệu lỗi thời / tuyên bố sai so với thực tế

| Vị trí | Tuyên bố | Đã nêu | Thực tế (tính bằng mã) | Kết luận |
|---|---|---|---|---|
| `Docs/command-catalogue-full-2026-11-26.md:22` | ¦ Host builtins (app) ¦ ~10 ¦ `help`, `config`, `pkg`, `relay`… — khôn | 10 | 80 tên / 93 lượt đăng ký | SAI/LỖI THỜI |
| `Docs/e2e-acceptance-results.md:17` | ## 2. HostHelpers bridge (20 APIs) | 20 | 21 thành viên public | SAI/LỖI THỜI |
| `Docs/functional-test-report-2026-11-26.md:10` | ¦ ST-02 ¦ HostHelpers 20 API ¦ static scan ¦ PASS ¦ ĐẠT host ¦ | 20 | 21 thành viên public | SAI/LỖI THỜI |
| `Docs/system-comparison-report-2026-11-26.md:89` | ¦ `AppleTerminalView+HostHelpers.swift` ¦ **Thêm mới** ¦ Port ~20 API | 20 | 21 thành viên public | SAI/LỖI THỜI |

Tham chiếu a-Shell SHA trong tài liệu không còn là pin hiện tại:

| Vị trí | SHA | Commit | Quan hệ với pin hiện tại |
|---|---|---|---|
| `Docs/command-catalogue-full-2026-11-26.md:3` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/command-parity-vs-ashell-2026-11-26.md:17` | `17b01a4d` | Merge pull request #1126 from demrom/feature/openssh-client-registrati | nhánh khác / không liên quan pin |
| `Docs/command-parity-vs-ashell-2026-11-26.md:17` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/e2e-acceptance-results.md:11` | `ef3ee37115` | Unify nested SwiftTerm pin to fork SoT main tip | nhánh khác / không liên quan pin |
| `Docs/feature-status-report-2026-11-26.md:8` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/feature-status-report-2026-11-26.md:9` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/feature-status-report-2026-11-26.md:30` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/final-monorepo-audit-2026-11-26.md:3` | `b4488692` | Bump SwiftTerm submodule to fork main tip | nhánh khác / không liên quan pin |
| `Docs/host-capabilities-gap-2026-11-26.md:4` | `0c9b11b6` | Port Stock SSH tip wiring for command parity with holzschu (#6) | cũ hơn pin hiện tại (đã bị thay thế) |
| `Docs/system-comparison-report-2026-11-26.md:17` | `17b01a4d` | Merge pull request #1126 from demrom/feature/openssh-client-registrati | nhánh khác / không liên quan pin |
| `Docs/system-comparison-report-2026-11-26.md:22` | `f47f284c` | Stop calling internal TerminalView.updateDisplay (#5) | cũ hơn pin hiện tại (đã bị thay thế) |

Các báo cáo cũ (`Docs/*-2026-11-26.md`) viết ở các thời điểm pin khác nhau trong cùng ngày; coi `Docs/audit/` là nguồn số liệu hiện hành (sinh lại bằng một lệnh).

## 9. Danh sách phát hiện (theo mức độ)

| ID | Mức | Repo | Tiêu đề |
|---|---|---|---|
| F-001 | CAO | ashell | Fork a-Shell tụt hậu upstream 31 commit và không qua bài test `worker-binding.sh` của nhà sản xuất (trên fork, pin) |
| F-002 | TRUNG BÌNH | swiftterm | Pin `Apps/a-Shell` trỏ vào commit của PR chưa merge, không thuộc `master` của a-shell |
| F-003 | TRUNG BÌNH | ashell | Target `a-Shell-noPython` dùng catalogue có 10 lệnh mà framework của chúng không được nhúng (giống upstream; có thể là chủ ý cho biến thể CI) |
| F-004 | TRUNG BÌNH | ashell | Không truy được nguồn tái tạo của framework được Xcode nhúng (không có binaryTarget trong xcfs/Package.swift, không có công thức trong repo theo 4 quy |
| F-005 | TRUNG BÌNH | ashell | Python.framework lấy từ tarball tải bằng `curl -fOL` không kiểm checksum (downloadFrameworks.sh:8): 3 lệnh (python, python3, python3.13) |
| F-006 | TRUNG BÌNH | ashell | Private key + PKCS#12 (mật khẩu `password` viết cứng) commit trong repo public (di sản upstream) |
| F-007 | TRUNG BÌNH | ashell | `webView(_:didReceive:)` chấp nhận mọi server-trust (không kiểm tra host/phương thức xác thực) — phát hiện tĩnh, chưa kiểm chứng tính tiếp cận |
| F-008 | TRUNG BÌNH | swiftterm | Tài liệu chứa 4 số liệu sai/lỗi thời và 11 tham chiếu pin cũ |
| F-009 | THẤP | swiftterm | Biên dịch macOS (Xcode 27.1, `-strict-concurrency=complete`) phát 3 cảnh báo trong `MacTerminalView.swift` |
| F-010 | THẤP | ashell | Cùng một lệnh khai báo khác nhau giữa catalogue full và mini: basename, dirname |
| F-011 | THẤP | ashell | CHƯA XÁC MINH: 37 đăng ký `replaceCommand` (TeX) trỏ vào symbol `luatex`, `tex` nằm trong framework tải theo nhu cầu |
| F-012 | THẤP | swiftterm | Tài liệu nêu đường dẫn không tồn tại (4 chỗ) |
| F-013 | THẤP | swiftterm | Liên kết markdown hỏng (6 chỗ) |
| F-014 | THẤP | ashell+swiftterm | Action bên thứ ba tham chiếu bằng tag thay vì SHA commit (7 chỗ) |
| F-015 | THẤP | swiftterm | Hai bản SwiftTerm: a-Shell build bằng bản lồng `SwiftTerm/` (XCLocalSwiftPackageReference), không phải SoT ở gốc |
| F-016 | THẤP | ashell | 3 chỗ nội suy chuỗi Swift vào JS của WebView mà không escape đầy đủ (giống hệt upstream) |
| F-017 | THẤP | swiftterm | Bằng chứng HostHelpers ở mức L3 (bước `Xcode iOS Build` đạt; log có dòng biên dịch `AppleTerminalView+HostHelpers.swift`, nhưng chưa có test hành vi). |
| F-018 | THÔNG TIN | ashell+swiftterm | File có shebang nhưng git mode không phải 100755 (33 chỗ) |
| F-019 | THÔNG TIN | ashell | Gói CA (cacert.pem, ~200 KB) commit trong repo (di sản upstream, dữ liệu công khai của curl.se) |
| F-020 | THÔNG TIN | swiftterm | Điểm tốt: WebTerminal (PTY qua WebSocket) chỉ bind 127.0.0.1 và yêu cầu Host + Origin loopback khớp |
| F-021 | THÔNG TIN | ashell | Điểm tốt: Relay chạy lệnh từ xa là opt-in, mặc định bind 127.0.0.1, TLS luôn bật, token ≥32 ký tự so sánh hằng thời gian, mTLS tuỳ chọn |
| F-022 | THÔNG TIN | swiftterm | Egress VM thực tế là allowlist (github.com/api.github.com) trái với mô tả của công cụ; bằng chứng probe tên miền từ VM không có giá trị |

#### F-001 · CAO · Fork a-Shell tụt hậu upstream 31 commit và không qua bài test `worker-binding.sh` của nhà sản xuất (trên fork, pin)

- **Vị trí:** `a-Shell.xcodeproj/project.pbxproj; tests/worker-binding.sh`
- **Bằng chứng:** fork ahead 7 / behind 31 so với holzschu/a-shell master (merge-base 34e0ae0141); 31 commit upstream chưa có trong fork. a-Shell tests/worker-binding.sh trên fork: FAIL worker targets do not compile the generated Worker.swift; a-Shell tests/worker-binding.sh trên pin: FAIL worker targets do not compile the generated Worker.swift. Đối chứng: cùng script trên upstream = PASS.
- **Khuyến nghị:** Merge `upstream/master` vào fork rồi chạy lại `tests/worker-binding.sh`; xem nhánh đồng bộ upstream.
- **Kiểm tra bằng:** `bash tests/worker-binding.sh (plutil shim) trên cây fork; kết quả hiện có: upstream PASS; fork FAIL; pin FAIL`

#### F-002 · TRUNG BÌNH · Pin `Apps/a-Shell` trỏ vào commit của PR chưa merge, không thuộc `master` của a-shell

- **Vị trí:** `.gitmodules / Apps/a-Shell`
- **Bằng chứng:** pin=d63526ba82; GitHub compare master...pin: status=ahead, ahead_by=2, behind_by=0 (merge-base 4f039cdb70) — PR #8 (open, nhánh cursor/accept-catalogue-158-45fd). Nếu nhánh bị xoá hoặc squash-merge rồi GC, `git submodule update --init` trên bản clone mới sẽ hỏng.
- **Khuyến nghị:** Merge PR a-shell tương ứng rồi bump pin về commit nằm trên master (hoặc dùng merge-commit/rebase, không squash).
- **Kiểm tra bằng:** `gh api repos/jiaomeimei0-prog/a-shell/compare/master...<pin>`

#### F-003 · TRUNG BÌNH · Target `a-Shell-noPython` dùng catalogue có 10 lệnh mà framework của chúng không được nhúng (giống upstream; có thể là chủ ý cho biến thể CI)

- **Vị trí:** `a-Shell.xcodeproj (a-Shell-noPython) + Resources_mini/commandDictionary.plist`
- **Bằng chứng:** Framework thiếu: Python;WasmKitCommand;blink;curl-impersonate;multimarkdown;openrsync;pico. Lệnh bị ảnh hưởng: blink, curl-impersonate, multimarkdown, openrsync, pico, python, python3, python3.13, rsync, wasmkit. Giống hệt upstream: True.
- **Khuyến nghị:** Nếu biến thể này được phát hành: dùng catalogue riêng hoặc nhúng framework; nếu chỉ dùng cho CI thì ghi rõ trong tài liệu.
- **Kiểm tra bằng:** `audit_commands.target_catalogues + PBXNativeTarget embedded frameworks`

#### F-004 · TRUNG BÌNH · Không truy được nguồn tái tạo của framework được Xcode nhúng (không có binaryTarget trong xcfs/Package.swift, không có công thức trong repo theo 4 quy tắc tra cứu): 5 lệnh (blink, cbc, curl-impersonate, multimarkdown, wasmkit)

- **Vị trí:** `xcfs/Package.swift; downloadFrameworks.sh`
- **Bằng chứng:** Framework: WasmKitCommand.framework/WasmKitCommand, blink.framework/blink, cbc.framework/cbc, curl-impersonate.framework/curl-impersonate, multimarkdown.framework/multimarkdown. Giống hệt upstream (lỗi gốc nhà sản xuất): True.
- **Khuyến nghị:** Khai báo binaryTarget có checksum hoặc thêm công thức dựng vào `ci/native-frameworks.sh`.
- **Kiểm tra bằng:** `audit_commands.framework_provenance (D07)`

#### F-005 · TRUNG BÌNH · Python.framework lấy từ tarball tải bằng `curl -fOL` không kiểm checksum (downloadFrameworks.sh:8): 3 lệnh (python, python3, python3.13)

- **Vị trí:** `xcfs/Package.swift; downloadFrameworks.sh`
- **Bằng chứng:** Framework: Python.framework/Python. Giống hệt upstream (lỗi gốc nhà sản xuất): True.
- **Khuyến nghị:** Ghim SHA-256 của `pythonInstall.tar.gz` và kiểm trước khi `tar xzf` (xcfs đã làm vậy cho 65 binaryTarget).
- **Kiểm tra bằng:** `audit_commands.framework_provenance (D10)`

#### F-006 · TRUNG BÌNH · Private key + PKCS#12 (mật khẩu `password` viết cứng) commit trong repo public (di sản upstream)

- **Vị trí:** `localCertificateKey.pem:1`
- **Bằng chứng:** AppDelegate.swift:45-47 nạp `localCertificate.pfx` với passphrase "password" cho server HTTPS loopback 127.0.0.1 (WASM). Khoá riêng của chứng chỉ localhost là công khai.
- **Khuyến nghị:** Sinh chứng chỉ per-install khi chạy lần đầu; không commit khoá. Rủi ro thực tế giới hạn ở loopback nhưng khoá công khai nghĩa là bất kỳ tiến trình cục bộ nào cũng mạo danh được nếu WebView tin chứng chỉ.
- **Kiểm tra bằng:** `audit_security.secret_scan`

#### F-007 · TRUNG BÌNH · `webView(_:didReceive:)` chấp nhận mọi server-trust (không kiểm tra host/phương thức xác thực) — phát hiện tĩnh, chưa kiểm chứng tính tiếp cận

- **Vị trí:** `a-Shell/SceneDelegate.swift:6338-6342`
- **Bằng chứng:** Handler dựng `URLCredential(trust: challenge.protectionSpace.serverTrust!)` rồi gọi `completionHandler(.useCredential, cred)` cho mọi challenge → vô hiệu hoá kiểm tra chứng chỉ cho WebView dùng delegate này (cần cho chứng chỉ localhost tự ký). Suy ra từ mã (chưa chạy): `serverTrust` là nil với challenge không phải server-trust (ví dụ HTTP Basic), nên dấu `!` có thể làm app crash thay vì chỉ từ chối.
- **Khuyến nghị:** Chỉ chấp nhận khi `protectionSpace.host` là 127.0.0.1/localhost và đúng cổng WASM; còn lại `performDefaultHandling`.
- **Kiểm tra bằng:** `audit_security.sink_inventory rule=tls-trust-bypass; đọc mã`

#### F-008 · TRUNG BÌNH · Tài liệu chứa 4 số liệu sai/lỗi thời và 11 tham chiếu pin cũ

- **Vị trí:** `Docs/*.md`
- **Bằng chứng:** Docs/command-catalogue-full-2026-11-26.md:22 (10 ≠ 80 tên / 93 lượt đăng ký); Docs/e2e-acceptance-results.md:17 (20 ≠ 21 thành viên public); Docs/functional-test-report-2026-11-26.md:10 (20 ≠ 21 thành viên public); Docs/system-comparison-report-2026-11-26.md:89 (20 ≠ 21 thành viên public)
- **Khuyến nghị:** Dùng `Docs/audit/` (sinh tự động) làm nguồn số liệu; thêm biểu ngữ 'đã thay thế' vào các báo cáo cũ.
- **Kiểm tra bằng:** `run_audit.doc_claims`

#### F-009 · THẤP · Biên dịch macOS (Xcode 27.1, `-strict-concurrency=complete`) phát 3 cảnh báo trong `MacTerminalView.swift`

- **Vị trí:** `Sources/SwiftTerm/Mac/MacTerminalView.swift:1388:16`
- **Bằng chứng:** MacTerminalView.swift:1388:16: immutable value 'terminal' was never used; consider replacing with '_' or removing it; MacTerminalView.swift:1400:16: immutable value 'terminal' was never used; consider replacing with '_' or removing it; MacTerminalView.swift:4915:45: 'init(cString:)' is deprecated: Use String(decoding: array, as: UTF8.self) instead, after truncating the null termination.. Kết quả build: `Build complete! (75.52 sec)` (không lỗi).
- **Khuyến nghị:** Thay `let terminal` không dùng bằng `_`/xoá; thay `String(cString:)` đã deprecated bằng `String(decoding:as:)` sau khi cắt ký tự null.
- **Kiểm tra bằng:** `log job swiftpm-strict-concurrency (cursor-github get_job_logs)`

#### F-010 · THẤP · Cùng một lệnh khai báo khác nhau giữa catalogue full và mini: basename, dirname

- **Vị trí:** `Resources/commandDictionary.plist vs Resources_mini/commandDictionary.plist`
- **Bằng chứng:** basename: full='file'; mini='none'; dirname: full='file'; mini='none' (argtype `file` ở full nhưng `none` ở mini — lỗi gốc nhà sản xuất)
- **Khuyến nghị:** Thống nhất argtype giữa hai catalogue.
- **Kiểm tra bằng:** `audit_commands tables diff`

#### F-011 · THẤP · CHƯA XÁC MINH: 37 đăng ký `replaceCommand` (TeX) trỏ vào symbol `luatex`, `tex` nằm trong framework tải theo nhu cầu

- **Vị trí:** `a-Shell/AppDelegate+TeX.swift:39-79`
- **Bằng chứng:** Symbol không được định nghĩa trong mã nguồn repo, nên chỉ kiểm chứng được bằng nhị phân prebuilt (VM không tải được). Nếu framework không export symbol này, `replaceCommand` chỉ ghi NSLog và không làm gì. Giống upstream (di sản TeX). Đây là khoảng trống kiểm chứng, chưa phải lỗi đã xác nhận.
- **Khuyến nghị:** Xác minh bằng `nm -gU` trên framework `tex`/`luatex` (job CI trên macOS) hoặc kiểm trên thiết bị: chạy `pdftex --version`.
- **Kiểm tra bằng:** `audit_commands.locate_symbols + ios_system.m replaceCommand semantics`

#### F-012 · THẤP · Tài liệu nêu đường dẫn không tồn tại (4 chỗ)

- **Vị trí:** `Apps/README.md:17`
- **Bằng chứng:** Apps/README.md:17; Docs/security-audit-egress-2026-11-26.md:180; Docs/system-comparison-report-2026-11-26.md:239; Sources/SwiftTerm/Documentation.docc/Embedding.md:34
- **Khuyến nghị:** Sửa hoặc xoá tham chiếu.
- **Kiểm tra bằng:** `audit_scripts/audit_invocations kind=broken-doc-path`

#### F-013 · THẤP · Liên kết markdown hỏng (6 chỗ)

- **Vị trí:** `Docs/osc7501-delta.md:5`
- **Bằng chứng:** Docs/osc7501-delta.md:5; Docs/osc7501-delta.md:122; Docs/osc7501-delta.md:148; PERFORMANCE.md:156; PERFORMANCE.md:203; PERFORMANCE.md:206
- **Khuyến nghị:** Sửa liên kết.
- **Kiểm tra bằng:** `audit_scripts/audit_invocations kind=broken-doc-link`

#### F-014 · THẤP · Action bên thứ ba tham chiếu bằng tag thay vì SHA commit (7 chỗ)

- **Vị trí:** `.github/workflows/cloudflare-pages-web.yml`
- **Bằng chứng:** .github/workflows/cloudflare-pages-web.yml; .github/workflows/docc.yml; .github/workflows/web-wasm.yml; .github/workflows/xcode.yml; .github/workflows/native-frameworks.yml; .github/workflows/openrsync.yml; .github/workflows/pico-framework.yml
- **Khuyến nghị:** Ghim SHA (a-Shell của nhà sản xuất đã ghim SHA).
- **Kiểm tra bằng:** `audit_scripts/audit_invocations kind=workflow-unpinned-actions`

#### F-015 · THẤP · Hai bản SwiftTerm: a-Shell build bằng bản lồng `SwiftTerm/` (XCLocalSwiftPackageReference), không phải SoT ở gốc

- **Vị trí:** `Apps/a-Shell/SwiftTerm (submodule lồng)`
- **Bằng chứng:** nested=633a592ee9 chậm 37 commit so với HEAD nhưng `Sources/SwiftTerm` GIỐNG HỆT (so tree hash). Đồ thị phụ thuộc vòng: SwiftTerm → a-Shell → SwiftTerm.
- **Khuyến nghị:** Chạy `Sources/SwiftTerm` tree-hash check trong CI mỗi khi bump; hoặc để a-Shell trỏ vào SoT.
- **Kiểm tra bằng:** `git rev-parse HEAD:Sources/SwiftTerm vs <nested>:Sources/SwiftTerm`

#### F-016 · THẤP · 3 chỗ nội suy chuỗi Swift vào JS của WebView mà không escape đầy đủ (giống hệt upstream)

- **Vị trí:** `a-Shell/SceneDelegate+TerminalView.swift:697`
- **Bằng chứng:** a-Shell/SceneDelegate+TerminalView.swift:697 [js-interpolation-unescaped]; a-Shell/SceneDelegate.swift:1134 [js-escape-missing-quote]; a-Shell/SceneDelegate.swift:4629 [js-interpolation-unescaped]. Các chỗ cùng loại ở `SceneDelegate+TerminalView.swift` (nhập stdin cho lệnh WebAssembly tương tác) và `SceneDelegate.swift` (xuất stdout vào editor web) đã escape `\`, `'`/`"`, xuống dòng; ba chỗ này thì không nhất quán. Hệ quả suy ra từ mã (chưa kiểm chứng động): nhập dấu `'` rồi Ctrl-D khi lệnh WASM đang đọc stdin làm câu JS lỗi cú pháp (EOF không tới lệnh); nội dung có `"` trong nút bàn phím phụ gây lỗi tương tự trong editor web.
- **Khuyến nghị:** Dùng cùng hàm escape cho cả ba chỗ (hoặc truyền qua JSON/base64 như các chỗ khác).
- **Kiểm tra bằng:** `audit_security.js_escape_checks`

#### F-017 · THẤP · Bằng chứng HostHelpers ở mức L3 (bước `Xcode iOS Build` đạt; log có dòng biên dịch `AppleTerminalView+HostHelpers.swift`, nhưng chưa có test hành vi). Nhãn '20 APIs' đã lỗi thời: file khai báo 21 API (script liệt kê 21); 17 API được a-Shell gọi nhưng SwiftTerm không có test; 2 API không ai dùng

- **Vị trí:** `scripts/e2e_acceptance_host.sh:77`
- **Bằng chứng:** Không có test trong SwiftTerm: getTerminal, getLastLine, getLastPrompt, setPromptEnd, getNewContent, saveCursorPosition, restoreCursorPosition, setCursorPosition, moveUpIfNeeded, moveDownIfNeeded, moveToBeginningOfLine, moveToEndOfLine, clearToEndOfLine, wipeContents, moveToEndOfSelection, moveToBeginningOfSelection, deleteSelection; không ai dùng: getCurrentChar, atTheEndOfTheLine. HostHelpers bị bao bởi `os(iOS) || os(visionOS)` nên không bao giờ biên dịch trên Linux; chỉ bước `Xcode iOS Build` của workflow `Swift` (macOS) biên dịch nó — trạng thái: đạt.
- **Khuyến nghị:** Khi bước `Xcode iOS Build` đạt thì HostHelpers mới có bằng chứng biên dịch; thêm test cho các API chưa được phủ.
- **Kiểm tra bằng:** `audit_hostapi.analyse`

#### F-018 · THÔNG TIN · File có shebang nhưng git mode không phải 100755 (33 chỗ)

- **Vị trí:** `Tools/generate_kitty_parity_matrix.py`
- **Bằng chứng:** Tools/generate_kitty_parity_matrix.py; Tools/import-ghostty-fuzz-corpus.swift; scripts/esctest-known-good.py; scripts/ios_input_ssh_server.py; scripts/regen_unicode_width_data.py; ODR/forbidden_2023.sh; ShellWorkers/resources.sh; ci/audit-artifact.py ...
- **Khuyến nghị:** Chạy qua interpreter hoặc `chmod +x`.
- **Kiểm tra bằng:** `audit_scripts/audit_invocations kind=shebang-not-executable`

#### F-019 · THÔNG TIN · Gói CA (cacert.pem, ~200 KB) commit trong repo (di sản upstream, dữ liệu công khai của curl.se)

- **Vị trí:** `cacert.pem`
- **Bằng chứng:** Không phải bí mật; cần cập nhật định kỳ.
- **Khuyến nghị:** Cập nhật theo lịch.
- **Kiểm tra bằng:** `audit_security.secret_scan`

#### F-020 · THÔNG TIN · Điểm tốt: WebTerminal (PTY qua WebSocket) chỉ bind 127.0.0.1 và yêu cầu Host + Origin loopback khớp

- **Vị trí:** `TerminalApp/WebTerminal/Sources/WebTerminalServer/HTTPServer.swift:4-20,98`
- **Bằng chứng:** isAllowedWebSocketOrigin từ chối Origin vắng/không khớp; do đó KHÔNG thể phơi server PTY qua tunnel công khai (Host/Origin sẽ bị từ chối). Các script tunnel chỉ phơi `python -m http.server` tĩnh trên 127.0.0.1.
- **Khuyến nghị:** Giữ nguyên; không tunnel WebTerminalServer.
- **Kiểm tra bằng:** `đọc mã HTTPServer.swift + scripts/*.ps1`

#### F-021 · THÔNG TIN · Điểm tốt: Relay chạy lệnh từ xa là opt-in, mặc định bind 127.0.0.1, TLS luôn bật, token ≥32 ký tự so sánh hằng thời gian, mTLS tuỳ chọn

- **Vị trí:** `a-Shell/Relay.swift:140-225`
- **Bằng chứng:** Rủi ro còn lại: bind 0.0.0.0 + token lộ ⇒ thực thi lệnh từ xa; `relay status` in token khi mTLS tắt (có cảnh báo).
- **Khuyến nghị:** Khuyến nghị mTLS khi bind ngoài loopback.
- **Kiểm tra bằng:** `đọc mã Relay.swift`

#### F-022 · THÔNG TIN · Egress VM thực tế là allowlist (github.com/api.github.com) trái với mô tả của công cụ; bằng chứng probe tên miền từ VM không có giá trị

- **Vị trí:** `VM egress`
- **Bằng chứng:** TLS tới host khác bị reset; tải release asset (release-assets.githubusercontent.com) trả 302 rồi bị chặn.
- **Khuyến nghị:** Probe `toolvip1.top` từ ngoài VM (GitHub Actions hoặc máy người dùng).
- **Kiểm tra bằng:** `curl thử nghiệm trong phiên audit`

## 10. Giới hạn trung thực và việc cần làm tiếp

**Không thể làm trên VM này** (không bịa kết quả): không có `swift`/`xcodebuild`/thiết bị iOS ⇒ biên dịch/test Apple chỉ có qua CI của fork (mục 6.3), không chạy 158 lệnh; không có `pwsh` ⇒ script PowerShell được chạy qua CI Windows (mục 6.3), không chạy cục bộ; egress là allowlist (github.com, api.github.com) ⇒ không tải được framework prebuilt, không probe được `toolvip1.top`, và các kết luận "FAIL" tên miền chạy từ VM trong báo cáo cũ **không có giá trị**.

**Việc tiếp theo, theo thứ tự giá trị:**

1. Merge PR a-shell chứa commit đang được ghim (#8) rồi bump pin về commit nằm trên `master`.
2. Đồng bộ `upstream/master` vào fork (31 commit chưa có) để `worker-binding.sh` PASS.
3. Chạy `verify_command_catalogue_158.sh` trên iPhone/iPad và điền ma trận.
4. Cấu hình `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`, tắt Access cho hostname demo công khai, probe `toolvip1.top` từ ngoài VM.
5. Với upstream a-Shell: thu hẹp `didReceive challenge`, sinh chứng chỉ localhost theo máy, thống nhất escape JS (đề xuất, ngoài phạm vi repo này).

## Phụ lục — tái lập

```bash
python3 -m unittest discover -s scripts/audit -v      # test đối chứng của bộ phát hiện
python3 scripts/audit/run_audit.py --ashell /path/to/a-shell --out Docs/audit --run-tests --online --ci-sha <sha> --swift-sha <sha-có-kết-quả-macOS> \
    --linux-log <log> --swift-log <log> --build-log <log> --windows-log <log> --windows-mutation-log <log> \
    --baseline-dir Docs/audit/data/baseline --baseline-ref <sha-trước-khi-sửa>
```

Dữ liệu thô: `Docs/audit/data/*.csv|json`; baseline trước khi sửa: `Docs/audit/data/baseline/`. Mọi bảng trong báo cáo này được sinh từ các file đó.