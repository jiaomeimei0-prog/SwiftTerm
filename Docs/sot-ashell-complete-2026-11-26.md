# Hoàn thành: SwiftTerm fork v2 (SoT) ↔ a-Shell iOS

**Ngày khóa:** 2026-11-26 (Asia/Saigon)  
**Trạng thái kiến trúc:** **HOÀN THÀNH** (host structure / SoT / pin / audit).  
**Ngoài phạm vi khóa này:** build Xcode trên Mac, CI macos runner, thử thiết bị thật.

---

## Định nghĩa “hoàn thành”

| Tiêu chí | Đạt? |
|----------|------|
| Một SoT emulator: `jiaomeimei0-prog/SwiftTerm` | Có — `Docs/source-of-truth.md` |
| a-Shell chỉ wiring host (`ios_system` + UI), không fork SoT thứ hai | Có |
| Nested Xcode submodule `SwiftTerm` → cùng fork, tip SoT | Có — pin `633a592` |
| Monorepo `Apps/a-Shell` → tip a-shell mang pin trên | Có (PR kèm theo) |
| HostHelpers 5 nhóm trên fork v2 | Có — `AppleTerminalView+HostHelpers.swift` |
| I/O: Pipe + `ios_fork` / `ios_system` (không LocalProcess iOS) | Có — `SceneDelegate` |
| Audit host + E2E host gate FAIL=0 | Có — `Docs/final-monorepo-audit-*`, `scripts/e2e_acceptance_host.sh` |

---

## Sơ đồ đã khóa

```text
jiaomeimei0-prog/SwiftTerm @ SoT tip
├── Sources/SwiftTerm (+ HostHelpers)     ← sửa emulator / security TẠI ĐÂY
└── Apps/a-Shell  ──submodule──►  jiaomeimei0-prog/a-shell
        └── SwiftTerm ──submodule──►  cùng fork @ SoT tip
            (Xcode relativePath = SwiftTerm)

Runtime iOS:
  TerminalView+HostHelpers  ↔  Pipe  ↔  ios_system / WASM loopback / Relay(opt-in)
```

---

## Việc còn lại (không chặn “hoàn thành cấu trúc”)

1. Mac/Xcode: `./downloadFrameworks.sh` + scheme `a-Shell-noPython` + Run  
2. Device: `sh scripts/verify_ashell_integrity.sh` + smoke tương tác  
3. (Tuỳ chọn) Codex/Stock SSH XCFramework khi cần artifact local  

---

## Cách xác nhận lại trên host

```sh
git submodule update --init Apps/a-Shell
cd Apps/a-Shell && git submodule update --init SwiftTerm
bash scripts/e2e_acceptance_host.sh
```
