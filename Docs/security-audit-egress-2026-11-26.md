# Kiểm toán bảo mật egress — SwiftTerm

**Repo:** `jiaomeimei0-prog/SwiftTerm`  
**Commit tham chiếu:** `92cbebc`  
**Ngày báo cáo:** 2026-11-26 (Asia/Saigon)  
**Câu hỏi chủ hệ thống:** Codebase có cơ chế kết nối mạng, telemetry, rò rỉ dữ liệu, hoặc điều hướng I/O trái phép sang bên thứ ba hay không?

---

## 1. Kết luận tổng quan (Verdict)

**`[CÓ CẢNH BÁO]`**

- Thư viện lõi `Sources/SwiftTerm` **không** có telemetry, không gọi `URLSession`/`NWConnection`, không hardcode endpoint bên thứ ba để “phone home”.
- Luồng I/O mặc định khớp bản đồ PTY ↔ engine ↔ UI; `LocalProcessTerminalView.send` chỉ ghi PTY.
- Có **kênh phụ theo giao thức terminal** (OSC 52 clipboard, mở link, Kitty đọc file local khi bật policy) và **mẫu app có mạng chủ đích** (SSH iOS, WebTerminal loopback) — không phải backdoor ẩn, nhưng có thể đưa dữ liệu ra ngoài process nếu host bật/cấu hình sai.

---

## 2. Bảng kiểm kê điểm giao tiếp ngoài (Egress Points)

| Điểm | Vị trí | Phân loại | Dữ liệu đi đâu |
|------|--------|-----------|----------------|
| PTY write | `LocalProcess.send` → `DispatchIO.write` | Hợp lệ | Master PTY / child process |
| `TerminalViewDelegate.send` (Mac local) | `MacLocalTerminalView.swift:521-524` | Hợp lệ | `process.send` → PTY only |
| `sendResponse` / OSC-CSI replies | `Terminal.swift:7971+` → `tdel.send` | Hợp lệ | Cùng kênh host (PTY/SSH/WS), không fork mạng riêng |
| OSC 52 clipboard **read** | `Terminal.swift:4058-4065` | Cảnh báo (protocol) | Clipboard → base64 → `sendResponse` → peer đang kết nối |
| OSC 52 clipboard **write** | `Terminal.swift:4066-4071` | Hợp lệ / host | Peer → pasteboard (local) |
| Pasteboard Mac local default | `MacLocalTerminalView.swift:412-424` | Cảnh báo khi SSH/remote | `clipboardRead` trả `NSPasteboard` → peer |
| Default `clipboardRead` | `Terminal.swift:10699-10700`, `MacTerminalView.swift:4912-4913` | An toàn mặc định | `nil` (từ chối đọc) |
| Mở hyperlink | `TerminalLinkOpening.swift:139`, `MacTerminalView.swift:4780` | Cảnh báo UX | User/delegate → `NSWorkspace.open` (trình duyệt/app) |
| Kitty local file `t=f`/`t=t` | `KittyGraphics.swift:1429+`; default policy `[]` tại `TerminalOptions.swift:154` | Cảnh báo nếu bật | Đọc file local vào engine (hiển thị); mặc định **tắt** |
| `setHostLogging` | `LocalProcess.swift:797-850` | Cảnh báo (opt-in debug) | Tee inbound PTY → file trên đĩa |
| `termcast` ghi `.cast` | `Sources/Termcast/TermcastRecorder.swift:64-70` | Hợp lệ (công cụ) | Session → file local do user chỉ định |
| Parser `dump()` ghi `/tmp` | `EscapeSequenceParser.swift:884-898` | Dead code | **Không có caller** trong repo |
| `Buffer.dump()` path Miguel | `Buffer.swift:1951-1979` | Dead / debug | Chỉ còn comment gọi `//buffer.dump()` (`Terminal.swift:8885`) |
| iOS SSH sample | `TerminalApp/iOSTerminal/UIKitSshTerminalView.swift` | Hợp lệ (sample) | User nhập host → NIO SSH |
| WebTerminal WS | `HTTPServer.swift:98` bind `127.0.0.1` | Hợp lệ (sample local) | Browser ↔ loopback ↔ local PTY |
| WASM `fetch(wasmURL)` | `Web/src/loader.ts:95` | Hợp lệ | Host tải artifact WASM do app cung cấp |
| CI `curl download.swift.org` | `.github/workflows/web-wasm.yml` | Hợp lệ (build) | Chỉ CI, không runtime app |
| `regen_unicode_width_data.py` | `scripts/` → unicode.org | Hợp lệ (dev) | Chỉ khi regen data, không runtime |

**Không tìm thấy trong `Sources/`:** `URLSession`, `NWConnection`, `NWListener`, Sentry/Firebase/analytics, `sendBeacon`, endpoint telemetry hardcode.

---

## 3. Phân tích bất thường / kênh phụ

### 3.1 Không phát hiện rò rỉ sang bên thứ ba (telemetry)

Quét `Sources/` không có client HTTP/telemetry. `Package.swift` chỉ phụ thuộc:

- `apple/swift-argument-parser`
- `apple/swift-docc-plugin`
- `tayloraswift/swift-png`
- Transitive `rarestype/h` = thư viện hash/Base64 cho PNG — không phải mạng

### 3.2 Invariant luồng send (khớp bản đồ)

```swift
// Sources/SwiftTerm/Mac/MacLocalTerminalView.swift:521-524
open func send(source: TerminalView, data: ArraySlice<UInt8>)
{
    process.send (data: data)
}
```

Không thấy tee/mirror sang socket hay URL thứ hai trong đường này.

### 3.3 OSC 52 — kênh exfil theo thiết kế protocol (không phải backdoor ẩn)

```swift
// Sources/SwiftTerm/Terminal.swift:4058-4065
if payload.count == 1 && payload[payload.startIndex] == UInt8(ascii: "?") {
    if tdel?.clipboardReadRequest(source: self, selection: selectionChars) == true { return }
    guard let content = tdel?.clipboardRead(source: self) else {
        return
    }
    let base64 = terminalBase64Encode(content)
    sendResponse(cc.OSC, "52;\(selectionChars);\(base64)", cc.ST)
```

- Default delegate: `clipboardRead` → `nil` (chặn).
- `LocalProcessTerminalView` **bật** đọc pasteboard → nếu peer là SSH remote, clipboard có thể ra máy khác qua cùng kênh SSH (không phải domain lạ riêng).

### 3.4 Kitty đọc file local — mặc định tắt

```swift
// Sources/SwiftTerm/TerminalOptions.swift:152-156
public init(
    storageLimitBytesPerScreen: UInt32 = 10_000_000,
    localMediaPolicy: LocalMediaPolicy = [],
    trustedTemporaryDirectory: TerminalTemporaryDirectory? = nil
```

Chỉ khi host set `.regularFiles`/`.temporaryFiles` thì remote sequence mới đọc được path local vào buffer đồ họa.

### 3.5 `setHostLogging` — fork inbound ra đĩa (opt-in)

```swift
// Sources/SwiftTerm/LocalProcess.swift:843-849
if let path = delivery.logPath {
    let ownedData = Data(data.copiedBytes())
    do {
        try ownedData.write(to: URL(fileURLWithPath: path))
```

Chỉ khi gọi `setHostLogging(directory:)`. Đây là tee khỏi trục “chỉ feed UI”, nhưng local disk, không mạng.

### 3.6 Render lock / dirty

`TerminalRenderOwner.feedTransaction` lấy `terminalLock`; `prepareFrame` gọi `clearUpdateRange()` sau khi lấy dirty range (`TerminalRenderOwner.swift:642-643`). Precondition chặn send/input khi đang giữ lock. Không thấy nhánh exfil từ FrameDriver.

### 3.7 Sample mạng (không nằm trong library embed mặc định)

| Sample | Egress |
|--------|--------|
| iOS SSH | Kết nối host user chỉ định |
| WebTerminal | Chỉ `127.0.0.1` + Origin check |

---

## 4. Khuyến nghị kiểm chứng động (Runtime)

Khi chạy app thật (MacTerminal / app nhúng SwiftTerm):

```bash
# 1) Process đang nghe/kết nối gì (thay PID)
lsof -nP -iTCP -a -p <PID>
lsof -nP -p <PID> | egrep 'TCP|UDP|PIPE|unix'

# 2) macOS: theo dõi kết nối theo process
nettop -p <PID> -L 1
# hoặc: sudo tcpdump -i any -n host not 127.0.0.1 and not ::1

# 3) Xác nhận không gọi setHostLogging
# (grep binary / audit log) — nếu có, kiểm tra thư mục log

# 4) Nếu dùng SSH: coi OSC 52 như exfil clipboard
# Tắt bằng cách clipboardRead luôn trả nil (default TerminalView)

# 5) Kitty local media: giữ localMediaPolicy = [] (mặc định)
```

Firewall: deny egress cho binary terminal trừ đích SSH/user-intended; WebTerminal chỉ cần loopback.

---

## Tóm tắt một câu

**Không có cơ chế telemetry/exfil ẩn sang bên thứ ba trong lõi SwiftTerm; có các kênh protocol và mẫu app có thể đưa dữ liệu ra peer/đĩa/trình duyệt nếu host bật hoặc user chủ đích kết nối — cần cứng hóa OSC 52 / Kitty local media / không gọi `setHostLogging` trên bản production.**
