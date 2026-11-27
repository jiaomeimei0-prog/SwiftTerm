# BỘ NHỚ DỰ ÁN — SwiftTerm + a-Shell

Cập nhật 2026-11-28 00:15 giờ Việt Nam (UTC+7). Dùng để gửi cho người hoặc agent khác. Chỉ coi một việc là đạt khi có lệnh và kết quả. Chưa chạy trên thiết bị thì ghi `PENDING_USER_DEVICE`.

Transcript đầy đủ của phiên điều tra: https://cursor.com/agents/bc-f6952eae-1f31-41cd-9b9d-525cc43645fd  
Phiên thuộc tài khoản Cursor `jiaomeimei0@gmail.com`. Liên kết không công khai.

Báo cáo số liệu: `Docs/audit/AUDIT-REPORT-2026-11-27.md` (sinh 16:25 giờ Việt Nam ngày 27 tháng 11 năm 2026). Dữ liệu thô: `Docs/audit/data/`.

---

## 1. Mục tiêu cuối (chưa đạt)

Phải có cùng lúc:

1. 158 lệnh a-Shell chạy thật trên thiết bị người dùng, khớp catalogue nhà sản xuất.
2. SwiftTerm-core có bằng chứng E2E (host đã có; biên dịch Apple đã có trên CI; hành vi HostHelpers chưa có test).
3. Cloudflare bền trên **`toolvip1.top`**. `tooltop1.vip` là tên sai, chưa đăng ký.
4. Trình duyệt bên ngoài VM thấy trang SwiftTerm, không phải Error 1033, Hello World, hay tường đăng nhập Cloudflare Access.
5. Người dùng đối chiếu kết quả với nhà sản xuất trước khi gọi là hoàn tất.

## 2. Hai nguồn lõi

| Nguồn | Vị trí | Remote | Ref lúc ghi | Commit |
|---|---|---|---|---|
| SwiftTerm, nguồn sự thật | `/workspace` | `jiaomeimei0-prog/SwiftTerm` | nhánh `cursor/audit-command-inventory-45fd` | `5231d04` |
| a-Shell fork | `/agent/repos/a-shell` | `jiaomeimei0-prog/a-shell` | `master` | `4f039cdb` |
| a-Shell nhà sản xuất | cùng clone, remote `upstream` | `holzschu/a-shell` | `master` | `17b01a4d36` (lúc sinh báo cáo) |
| Pin `Apps/a-Shell` | submodule của SwiftTerm | — | `d63526ba824f37d4d378cc4293e7dfe555e754d9` | master fork + 2 commit |

Đồ thị vòng: SwiftTerm → `Apps/a-Shell` → SwiftTerm lồng `633a592e`. Cây `Sources/SwiftTerm` của bản lồng giống HEAD khi sinh báo cáo; bản lồng chậm 36 commit. a-Shell build bằng bản lồng, không bằng bản ở gốc repo.

Fork so với nhà sản xuất (GitHub compare): `diverged`, ahead 7, behind 31, merge-base `34e0ae0141`. Đếm `git rev-list` trên VM không dùng được vì clone a-Shell nông.

## 3. Pull request

- SwiftTerm [#29](https://github.com/jiaomeimei0-prog/SwiftTerm/pull/29) đang mở. Nhánh `cursor/audit-command-inventory-45fd`, base `cursor/fix-named-tunnel-ps1-45fd` (PR #28). Tip `5231d04`. Đây là PR kiểm kê lệnh, sửa lời gọi sai, và báo cáo `Docs/audit/`.
- SwiftTerm [#28](https://github.com/jiaomeimei0-prog/SwiftTerm/pull/28) đang mở: script tunnel Windows cho PowerShell 5.1.
- a-Shell [#8](https://github.com/jiaomeimei0-prog/a-shell/pull/8) đang mở, chưa merge. Pin `d63526ba` nằm trên nhánh của PR này. Nếu nhánh bị xoá, `git submodule update` trên clone mới sẽ hỏng.

## 4. Kết quả đã đo

Sinh bằng `scripts/audit/run_audit.py` từ git objects, script test của nhà sản xuất, và log CI. Bộ phát hiện có 57 test đơn vị sau commit `5231d04` (báo cáo đã xuất ghi 56, vì commit đó chỉ đổi cách kết luận catalogue tải theo nhu cầu và không đổi số liệu).

| Hạng mục | Kết quả | Mức |
|---|---|---|
| Tên lệnh | 251. Catalogue full 158, mini 136, extra 8, llvm 10, tex 31, luatex 7, sshStock 4. Host built-in: 93 lượt đăng ký, 80 tên, 39 chỉ có trên host | tĩnh |
| So với nhà sản xuất và pin | 251/251 giống nhau. 0 lỗi do fork đưa vào | tĩnh |
| Lỗi cấu hình | 12 lệnh (gồm D01 trên target `a-Shell-noPython`, D04 `basename`/`dirname`) | di sản upstream |
| Nguồn gốc framework | 8 lệnh (D07: blink, cbc, curl-impersonate, multimarkdown, wasmkit; D10: python, python3, python3.13) | di sản upstream |
| Symbol TeX | 37 đăng ký chưa xác minh trong mã nguồn | chưa phải lỗi đã xác nhận |
| Lời gọi sai | 84 trước sửa → 50 còn lại: 33 shebang không executable, 7 action chưa ghim SHA, 6 link hỏng, 4 đường dẫn tài liệu hỏng | đã sửa gốc repo PowerShell, tên miền, `permissions` |
| Linux CI run `45866514883` | 78 XCTest, 0 lỗi; 1190 Swift Testing / 94 suite | L2, đạt |
| macOS `xcodebuild` cùng run, Xcode 27.1 | MacTerminal và iOSTerminal `BUILD SUCCEEDED`. HostHelpers được `SwiftCompile` trong cả hai `.xcodeproj` | L3, biên dịch đạt |
| `swift test` macOS | 159 XCTest, 0 lỗi; 2270 Swift Testing / 203 suite | L2, đạt |
| WebAssembly cùng commit `140ef938` | workflow success | L2, đạt build |
| PowerShell 5.1, Windows Server 2025 | 52 check đạt trên script đã sửa. Bản trước sửa: 7 check lỗi rồi dừng vì không có `Get-SwiftTermRoot` | L2, cú pháp và helper |
| `ssh-stock-registration.sh` | upstream, fork, pin đều PASS | L1 |
| `worker-binding.sh` | upstream PASS; fork FAIL; pin FAIL (`worker targets do not compile the generated Worker.swift`) | L1, không đạt |
| Host E2E `scripts/e2e_acceptance_host.sh` | PASS 67, WARN 1, FAIL 0, SKIP 2 | L1, grep và dry-run |
| 158 lệnh trên thiết bị | chưa chạy | `PENDING_USER_DEVICE` |
| `toolvip1.top` từ bên ngoài VM | chưa xác minh. Probe từ VM không có giá trị | chưa đạt |
| Tunnel Windows thật (`cloudflared` + tên miền) | chưa chạy trong CI | chưa đạt |

Run Swift `45866514883` kết thúc 01:20 giờ Việt Nam ngày 27 tháng 11 năm 2026, cả 6 job success. Ba cảnh báo biên dịch trong `Sources/SwiftTerm/Mac/MacTerminalView.swift` (dòng 1388, 1400, 4915).

HostHelpers: 21 API public. a-Shell gọi 19. 17 API được gọi nhưng SwiftTerm không có test. 2 API không ai dùng (`getCurrentChar`, `atTheEndOfTheLine`). File bị `#if os(iOS) || os(visionOS)` nên Linux không biên dịch nó.

## 5. An ninh đã đọc, chưa khai thác

- Khoá riêng localhost và PKCS#12 commit trong a-Shell. `AppDelegate.swift` nạp `localCertificate.pfx` với passphrase viết cứng cho HTTPS loopback. Di sản upstream.
- `SceneDelegate.swift` khoảng 6338–6342: `webView(_:didReceive:)` gọi `completionHandler(.useCredential, URLCredential(trust: serverTrust!))` cho mọi challenge. Suy ra từ mã, chưa chạy: `serverTrust` nil có thể làm crash với challenge không phải server-trust.
- 3 chỗ nội suy chuỗi Swift vào JavaScript không escape, giống upstream.
- WebTerminal chỉ bind `127.0.0.1` và kiểm Host/Origin. Relay opt-in, TLS, token. Đây là điểm tốt.
- Quét mẫu không thấy token GitHub, AWS, Slack, Stripe, Google hay `CLOUDFLARE_API_TOKEN` dạng literal. Quét không kiểm tra hiệu lực.
- SonarQube Cloud, nhận lúc 23:59 giờ Việt Nam ngày 27 tháng 11: Quality Gate của PR #29 thất bại. Điều kiện đỏ: Reliability Rating trên mã mới = C (yêu cầu từ A), Security Rating trên mã mới = D (yêu cầu từ A). Danh sách issue chưa lấy được: `sonarcloud.io` bị cắt TLS từ VM và không có comment inline. Chưa sửa.

Phát hiện trong báo cáo: 0 nghiêm trọng, 1 cao (fork tụt hậu và trượt `worker-binding.sh`), 7 trung bình, 9 thấp, 5 thông tin.

## 6. Tên miền và Cloudflare

- Tên thật: `toolvip1.top`. Tên sai đã gỡ khỏi workflow, `wrangler.toml` và `scripts/cloudflare-connect-domain.sh`: `tooltop1.vip`.
- Script Windows suy gốc repo từ vị trí script (`Get-SwiftTermRoot`, có thể ghi đè bằng `SWIFTTERM_ROOT`). Không còn gắn `%USERPROFILE%\Documents\SwiftTerm`.
- Thiếu secret `CLOUDFLARE_API_TOKEN` và `CLOUDFLARE_ACCOUNT_ID`. Workflow Pages cố ý thất bại khi thiếu secret.
- VM chỉ ra được github.com và api.github.com, dù công cụ mô tả egress là allow-all. Không dùng kết quả probe tên miền chạy từ VM.

## 7. Việc tiếp theo, theo giá trị

1. Merge a-Shell PR #8, rồi đổi pin `Apps/a-Shell` về commit nằm trên `master`.
2. Đưa `upstream/master` vào fork (31 commit) để `worker-binding.sh` PASS.
3. Chạy `verify_command_catalogue_158.sh` trên iPhone hoặc iPad và điền `Docs/command-158-device-matrix-PENDING.csv`.
4. Cấu hình secret Cloudflare, tắt Access cho hostname demo, probe `toolvip1.top` từ máy ngoài VM.
5. Đọc issue SonarQube của PR #29 (Reliability C, Security D) và sửa mã mới trước khi merge.
6. Với upstream a-Shell, ngoài phạm vi repo này: thu hẹp `didReceive challenge`, sinh chứng chỉ localhost theo máy, thống nhất escape JavaScript.

## 8. Cách tái lập báo cáo

```bash
python3 -m unittest discover -s scripts/audit -v
python3 scripts/audit/run_audit.py --ashell /path/to/a-shell --out Docs/audit --run-tests --online \
    --ci-sha 140ef9380929b9c61cbdfdf608b80b6ba5dfbd08 \
    --swift-sha 140ef9380929b9c61cbdfdf608b80b6ba5dfbd08 \
    --linux-log <log> --swift-log <log> --build-log <log> \
    --windows-log <log> --windows-mutation-log <log> \
    --baseline-dir Docs/audit/data/baseline --baseline-ref 1f7528c0683162a9a44e6d4cb1ff8a7701651a09
```

Commit `140ef938` là commit có log CI đã dùng. `5231d04` chỉ đổi điều kiện kết luận: dòng catalogue 158/136 chỉ thất bại khi `full` hoặc `mini` không đọc được.
