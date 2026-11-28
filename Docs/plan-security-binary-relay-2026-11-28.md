# Phương án — 3 mục tiêu sửa (TLS/ATS · binary fork · Relay/sshd)

**Ngày:** 2026-11-28 (Asia/Saigon)  
**Phạm vi repo:** `jiaomeimei0-prog/a-shell` (+ monorepo pin sau)  
**Không thi công trong file này** — chỉ kế hoạch, thứ tự, stop rules, bằng chứng.

Giả định “**11 binary đem sẵn**” = bộ **ios_system v3.0.5** (không Auxiliary):

`ios_system` · `awk` · `curl_ios` · `files` · `shell` · `ssh_cmd` · `ssh_cmdA` · `ssh_agent` · `sshd` · `tar` · `text`

---

## Bản đồ vấn đề ↔ mục tiêu

| Mục tiêu | Finding / hiện trạng | File chính |
|----------|----------------------|------------|
| **#1 TLS/ATS/cert** | F: WebView chấp mọi `serverTrust`; ATS `NSAllowsArbitraryLoads=true`; `localCertificate.pfx` + key trong git, passphrase `"password"` | `SceneDelegate.swift` ~6338–6342; `Info.plist` / mini; `AppDelegate.swift` ~45–47; `localCertificate.*` |
| **#2 Binary fork+SHA** | 65 `.binaryTarget` holzschu; 11 lõi từ release ios_system | `xcfs/Package.swift` |
| **#3 Relay tắt + bỏ sshd** | Relay đã `enabled=false` mặc định; `sshd.xcframework` vẫn nhúng + UI “sshd on/off” | `Relay.swift`; Package.swift `sshd`; `ContentView` / `SceneDelegate` service toggles |

---

## Mục tiêu 1 — TLS / ATS / chứng chỉ localhost

### 1.1 Mục tiêu kỹ thuật

1. **Bỏ chấp nhận mọi chứng chỉ** trong `WKWebView` `didReceive challenge`.  
2. **ATS về mặc định an toàn** (không `NSAllowsArbitraryLoads` / WebContent = true toàn cục).  
3. **Tạo lại chứng chỉ localhost theo máy**; **không commit private key**.

### 1.2 Thiết kế đề xuất

| Thành phần | Hành động |
|------------|-----------|
| `webView(_:didReceive:)` | Chỉ `.useCredential` khi: `authenticationMethod == NSURLAuthenticationMethodServerTrust` **và** host ∈ `{127.0.0.1, localhost}` **và** pin/fingerprint khớp cert local (hoặc trust evaluation chỉ cho leaf đó). Mọi challenge khác → `.cancel` / `.performDefaultHandling`. Bỏ `serverTrust!` force-unwrap. |
| ATS (`Info.plist`, mini, noPython nếu có) | Xóa `NSAllowsArbitraryLoads` + `NSAllowsArbitraryLoadsInWebContent`. Giữ (nếu cần) **exception hẹp** chỉ `localhost` / `127.0.0.1` cho WASM HTTPS — hoặc không exception nếu dùng cert được trust tạm trong keychain app. |
| Cert WASM (`AppDelegate`) | Lần đầu launch (hoặc script Mac): sinh ECDSA/RSA self-signed SAN=`localhost,127.0.0.1` → lưu **Application Support** (không Bundle). Passphrase random trong Keychain. Migrate: nếu Bundle còn pfx cũ → bỏ qua, ưu tiên file máy. |
| Git | Xóa khỏi tracking: `localCertificate.pfx`, `localCertificateKey.pem` (và cân nhắc `localCertificate.pem` nếu chứa material nhạy). Thêm `.gitignore`. `cacert.pem` (CA store công khai) có thể giữ nếu chỉ là trust store Mozilla — ghi rõ trong registry. |
| CI | Job không cần private key trong repo; test Simulator sinh cert runtime. |

### 1.3 Pha thi công

| Pha | Việc | Done khi |
|-----|------|----------|
| 1A | Patch `didReceive` + unit/host test mô tả disposition | Challenge non-localhost → cancel; localhost đúng pin → allow |
| 1B | Sinh cert runtime + AppDelegate load path mới | WASM `https://127.0.0.1:<port>/` vẫn load; không đọc Bundle pfx |
| 1C | ATS plist về mặc định / exception hẹp | `plutil` / diff Info.plist; smoke HTTPS localhost |
| 1D | `git rm --cached` keys + HISTORY note (key đã lộ → rotate, coi là compromised) | `git ls-files` không còn pfx/key |

### 1.4 Rủi ro / stop

- WASM editor/`curl https://127.0.0.1` có thể fail nếu ATS + challenge quá chặt → stop, nới **chỉ** exception localhost, không bật lại ArbitraryLoads toàn cục.  
- Key đã từng public trên GitHub → **không tái dùng** material cũ.

### 1.5 Không làm trong #1

Sửa escape JS SceneDelegate (finding riêng). Đổi Relay mTLS (mục #3).

---

## Mục tiêu 2 — Thay 11 binary đem sẵn bằng fork + ghim SHA

### 2.1 Mục tiêu kỹ thuật

Tự **build từ source** (fork của bạn) → XCFramework → upload release **do bạn kiểm soát** → `Package.swift` URL + **checksum SHA256** mới. Bắt đầu: **`ios_system` → `sshd` → `curl_ios`**, rồi phần còn lại của bộ 11.

### 2.2 Danh sách 11 + thứ tự

| # | Binary | Wave | Ghi chú |
|---|--------|------|---------|
| 1 | `ios_system` | **W0** | Runtime lõi — làm trước |
| 2 | `curl_ios` | **W0** | Phụ thuộc toolchain ios_system |
| 3 | `sshd` | **W0** | Song song đánh giá mục #3 (có thể **không** ship nếu xóa) |
| 4–5 | `files`, `shell` | W1 | Lệnh catalogue lõi |
| 6–8 | `ssh_cmd`, `ssh_cmdA`, `ssh_agent` | W1 | Client SSH (giữ nếu còn dùng `ssh`/`scp`) |
| 9–11 | `awk`, `tar`, `text` | W2 | Catalogue |

Auxiliary (dash*, ffmpeg, …) và 65−11 còn lại: **keep holzschu** đến khi W0–W2 ổn.

### 2.3 Chuỗi cung ứng đề xuất

```text
holzschu/ios_system (upstream)
        │ fork
        ▼
jiaomeimei0-prog/ios_system   ← SoT build scripts, tag release
        │ xcodebuild / CI Mac → *.xcframework.zip
        │ sha256sum → cập nhật
        ▼
Apps/a-Shell/xcfs/Package.swift  binaryTarget url=…/jiaomeimei0-prog/... checksum=…
        │
        ▼
downloadFrameworks.sh / CI a-Shell-noPython
```

### 2.4 Pha thi công

| Pha | Việc | Done khi |
|-----|------|----------|
| 2A | Fork `holzschu/ios_system` → org bạn; ghi commit upstream tip; CI Mac build **một** `ios_system.xcframework` | Artifact + SHA256 tái lập được |
| 2B | Thay **chỉ** `ios_system` trong `Package.swift`; CI `a-Shell-noPython` | Link + launch Simulator |
| 2C | Build `curl_ios` cùng tree/tag; pin SHA | `curl --version` / smoke trong app |
| 2D | Quyết định `sshd` (xem §3): build+pin **hoặc** xóa target | Không còn URL holzschu cho 3 tên W0 |
| 2E | W1–W2 lần lượt; mỗi binary 1 PR | `fork-registry.yaml` cập nhật action=`fork` + sha |
| 2F | Script `scripts/verify_xcframework_checksums.sh` so khớp zip vs Package.swift | CI bắt mismatch |

### 2.5 Rủi ro / stop

- Build ios_system **bắt buộc Mac + Xcode** (đúng major với upstream README) — Cloud Agent Linux **không** thay.  
- Sai ABI / `replaceCommand` ↔ framework → catalogue 158 vỡ → **rollback** URL+checksum holzschu cho binary đó.  
- Không fork lung tung llvm/tex/vim trong cùng epic.  
- `sshd` nếu mục #3 xóa → **bỏ W0 sshd build** (tiết kiệm).

### 2.6 Liên hệ L4 / 158

Đổi binary có thể đổi hành vi lệnh — sau mỗi wave: `validate_catalogue.sh` (host) + smoke device tối thiểu; **không** tự PASS CSV runtime.

---

## Mục tiêu 3 — Relay tắt + xóa `sshd` nếu không dùng

### 3.1 Hiện trạng

| | |
|--|--|
| Relay | `RelayConfiguration.enabled` mặc định **`false`**; bind `127.0.0.1`; TLS + token; `Relay.shared.restore()` vẫn chạy lúc launch (idle nếu off) |
| sshd | Binary nhúng; UI/service “sshd on/off”; config `~/Documents/.ssh/sshd_config` |

### 3.2 Quyết định sản phẩm (chốt trước code)

| Lựa chọn | Khi nào |
|----------|---------|
| **A. Giữ mã Relay, mặc định off** (khuyến nghị ngắn hạn) | Cần `/run` lab sau này; chỉ siết docs + assert enabled=false trong E2E |
| **B. Strip Relay** (lâu hơn) | Không bao giờ ship remote exec — xóa command `relay`, UI, ports plist |
| **C. Xóa sshd** (khuyến nghị nếu không dùng daemon) | Không cần lắng nghe SSH vào app — gỡ binary + UI + fake bin |

**Đề xuất mặc định kế hoạch:** **A + C** — Relay giữ off (không strip ngay); **gỡ sshd** khỏi Package + project + Settings nếu user xác nhận không cần.

### 3.3 Pha thi công (A+C)

| Pha | Việc | Done khi |
|-----|------|----------|
| 3A | E2E/assert: `.relay.json` absent hoặc `enabled=false`; không listen port Relay khi off | Host script / unit |
| 3B | Document: cấm hướng dẫn bật Relay trên LAN không mTLS | README + handoff |
| 3C | Gỡ `sshd` `binaryTarget` + embed frameworks trong pbxproj | `downloadFrameworks` không kéo sshd |
| 3D | Gỡ UI `sshd on/off`, filter `ServiceStatus`, man/docs | `help -l` / Settings không còn sshd |
| 3E | Catalogue: nếu plist không có `sshd` như command name — OK; nếu có entry → xóa/đồng bộ | `validate_catalogue` vẫn 158 hoặc cập nhật số + parity doc |

### 3.4 Rủi ro / stop

- User còn workflow `sshd on` → **stop xóa**, chuyển sang pin binary fork (mục 2) thay vì delete.  
- Strip Relay cùng lúc với TLS/#1 → PR quá lớn — **tách PR**.

---

## Thứ tự epic (khuyến nghị)

```text
Week logic (không ước lịch tường):
  P0  Mục tiêu 1 (TLS/ATS/cert)          — PR a-shell riêng, rủi ro UX WASM
  P1  Mục tiêu 3C–3E (xóa sshd)          — sau xác nhận user; giảm 1/11 binary
  P2  Mục tiêu 2A–2C (ios_system, curl) — Mac CI; sshd skip nếu đã xóa
  P3  Mục tiêu 2E (files/shell/ssh_cmd…) 
  P4  Mục tiêu 3A–3B (siết Relay)        — có thể song song P0
```

Monorepo: sau merge a-shell → bump `Apps/a-Shell` pin + cập nhật `Docs/fork-registry.yaml`.

---

## Việc cần user xác nhận trước khi code

1. **sshd:** xóa hẳn (**C**) hay giữ và tự build (**mục 2**)?  
2. **Relay:** giữ mã + off (**A**) hay strip (**B**)?  
3. Org GitHub cho fork `ios_system` (mặc định `jiaomeimei0-prog/ios_system`)?  
4. Máy Mac / Xcode version cho W0 (26.3 CI vs 27.1 local)?

---

## Definition of Done (cả 3)

| # | DoD |
|---|-----|
| 1 | Không ArbitraryLoads toàn cục; challenge không trust-all; không private key localhost trong git; WASM loopback vẫn chạy với cert máy |
| 2 | ≥ `ios_system` + `curl_ios` (và `sshd` nếu giữ) trỏ release fork + checksum; CI noPython xanh |
| 3 | Relay mặc định off có assert; `sshd` binary/UI đã gỡ **hoặc** quyết định giữ có ghi registry |

**Anti-fake:** không ghi “đã thay 11 binary” khi mới đổi 1–2; không PASS 158 device từ PR security này.
