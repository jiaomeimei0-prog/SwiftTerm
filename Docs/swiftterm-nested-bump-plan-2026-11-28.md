# A5 — Nested SwiftTerm bump plan (STOPPED)

**Range:** `633a592ee9dd9585a0536314d26e906154ac43db` → `5345160eab8a4b787bc7f8ff1278f84c8f19bd83`  
**Commit count:** **31** (`git rev-list --count`)  
**Stop rule:** `>30` → **DỪNG**, không bump 1-shot, không fork thêm, báo user.  
**Pin nested:** **`633a592e` unchanged**.

## Checklist A5 gốc — đủ / thiếu

| # | Mục A5 | Đủ? | Ghi chú |
|---|--------|-----|--------|
| 1 | Enumerate `633a592e..5345160e` | **Có** | 31 SHA liệt kê bên dưới |
| 2 | Tag: keyboard, HostHelpers, prompt, pickFolder, PR #42 | **Có** | Bảng tags; 4 mục UI = không có commit trong range; PR #42 có |
| 3 | Patch Package.swift (version + checksum) | **N/A** | Nested = `XCLocalSwiftPackageReference` path `SwiftTerm/` — không phải `.binaryTarget` |
| 4 | Test plan thủ công trên device | **Có** | Mục Manual test plan |
| 5 | `>30` → chia PR nhỏ / build fail → ROLLBACK | **Có** | Stop đã kích hoạt; rollback = giữ/`633a592e` |

## Tree evidence (quan trọng)

```
git rev-parse 633a592e:Sources/SwiftTerm
# cd66deb1671e233c3bcf32c0bfd6c4d5bcddebc5
git rev-parse 5345160e:Sources/SwiftTerm
# cd66deb1671e233c3bcf32c0bfd6c4d5bcddebc5  (identical)
```

`Sources/SwiftTerm` **giống hệt** giữa pin và tip → bump nested **không** đổi emulator/HostHelpers runtime; chỉ kéo monorepo docs/CI/metadata.

## Trạng thái

| Item | Value |
|------|--------|
| Nested pin (Xcode) | `633a592e` — **giữ nguyên** |
| Tip SoT `main` | `5345160e` |
| Package.swift binary checksum patch | **Không áp dụng** cho nested SwiftTerm |
| Rollback | Pin chưa đổi — không cần rollback code |

## Enumeration (`633a592e..5345160e`)

```
5345160 Merge PR #42 handoff memory
bb0ac1e Add AI handoff memory export
20b6307 Merge PR #41 Workers Builds evidence
f47bf4b Record Workers Builds disconnect evidence
d8b28ca Merge PR #40 Workers Builds disconnect
8e5fc1c Disconnect Workers Builds triggers
37666cf Merge PR #39 a-Shell pin L4 cleanup
fc716f0 Bump a-Shell pin after #8; L4 runbook
1715bba Merge PR #38 toolvip1 verify evidence
284848d Record user verification toolvip1.top SwiftTerm WASM
19272c3 Merge PR #37 pages domain dns
89d754d Rebind Pages domains when Zone DNS API denied
79dfb05 Merge PR #36 cf pages dns
f9a2cad Ensure apex/www CNAME
ab7c90d Merge PR #35 claim hostname
8948b70 Fix claim-hostname empty DELETE
f027211 Merge PR #34 claim pages domain
f0cb896 Claim toolvip1.top for Pages; remove Worker Hello World
0c17ecd Merge PR #33 pages domain api
081bb66 Attach Pages custom domains via API
6d84854 Merge PR #32 pages symlink
fb61c99 Fix ELOOP pkg/dist symlink
96f1438 Merge PR #31 cf pages auth
b46b5db Fix Pages auth Account ID resolve
64d37cb Audit command inventory (#29)
87436c2 Fix named-tunnel PowerShell (#28)
38df8b8 Supreme E2E evidence + 158 PENDING (#27)
f74a917 Fix Quick Tunnel PowerShell (#26)
d5a0ff6 Fail Pages when secrets missing (#25)
b7cb7a8 Bump Apps/a-Shell to SoT-pin master (#24)
eb204ce Complete SoT↔a-Shell architecture lock (#23)
```

## Tags (5 mục)

| Tag | Trong range? | Commits / notes |
|-----|--------------|-----------------|
| **keyboard** | Không | 0 file `Sources/SwiftTerm/iOS/` / keyboard trong diff Sources |
| **HostHelpers** | Không | `AppleTerminalView+HostHelpers.swift` unchanged (tree hash identical) |
| **prompt** | Không | Không commit đụng prompt/line-editor APIs |
| **pickFolder** | Không (SoT) | Thuộc a-Shell host (`ExtraCommands`), không phải SwiftTerm SoT |
| **PR #42** | Có | `5345160` / `bb0ac1e` — handoff docs only |

## Đề xuất nếu user vẫn muốn bump (sau khi duyệt)

1. Vì `Sources/SwiftTerm` identical → bump tip chỉ để đồng bộ gitlink; **không** bắt buộc cho 158 runtime.  
2. Nếu bump: một PR riêng ≤30 commit slice **hoặc** single submodule SHA update + chứng minh tree hash.  
3. Build Mac `a-Shell-noPython`; fail → rollback `633a592e`, **không** fork thêm.

## Manual test plan (khi được phép bump)

1. Trong repo a-shell: cập nhật submodule `SwiftTerm` → `5345160e`  
2. `scripts/build_noPython.sh` trên Mac  
3. Device: launch, gõ lệnh, prompt/cursor, `pickFolder`  
4. `validate_catalogue.sh` + `verify_command_catalogue_158.sh` (device)  
5. Fail build → submodule về `633a592e`, báo user
