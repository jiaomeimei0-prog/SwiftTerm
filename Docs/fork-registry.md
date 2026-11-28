# Fork registry — a-Shell / SwiftTerm

**Updated:** 2026-11-28 (Asia/Saigon)  
**Assert:** git submodules trong `Apps/a-Shell` = **đúng 2** (`SwiftTerm`, `cpython`) — **không** phải ~20 repo C dạng submodule.

## Pins

| Pin | Value |
|-----|--------|
| Monorepo `Apps/a-Shell` gitlink | `e95741b8e59bef75cec490528f8f36a498555bcf` |
| Nested SwiftTerm (Xcode link) | **`633a592ee9dd9585a0536314d26e906154ac43db`** (hiện tại) |
| Tip SoT SwiftTerm `main` | `5345160eab8a4b787bc7f8ff1278f84c8f19bd83` |
| Nested bump `633a592e` → `5345160e` | **STOPPED** — range = **31** commits (>30); xem `Docs/swiftterm-nested-bump-plan-2026-11-28.md` |
| Binary SPM (`xcfs/Package.swift`) | **65** `.binaryTarget` (canonical count; checksum-pinned) |

## Quyết định keep / fork / bump

| Thành phần | Action | Lý do |
|------------|--------|--------|
| `jiaomeimei0-prog/a-shell` (host app) | **fork** | SoT app: SceneDelegate, Intents, ExtraCommands, catalogues |
| Nested `SwiftTerm` submodule | **fork** + **bump** (có kế hoạch) | URL đã trỏ fork SoT; pin lồng chậm tip — bump theo PR nhỏ (range >30 đã dừng 1-shot) |
| `cpython` submodule | **keep** | Vẫn `holzschu/cpython` `3.13`; full Python cần artifact unpublished |
| `ios_system` + 64 binary khác trong `xcfs` | **keep** | Checksum release holzschu; tránh fork lung tung mất rebase |
| FMake (`Package.swift` dependency) | **keep** | Tooling resolve binary |
| Local ports (`node/`, `fd/`, `fzf/`, …) | **keep** (build Mac khi cần) | Không phải git submodule; không fork trừ khi patch |
| Monorepo SwiftTerm SoT (`/workspace`) | **fork** | Emulator + HostHelpers + WASM; không thay ios_system |

## Lịch rebase

| Sự kiện | Hành động |
|---------|-----------|
| Mỗi **iOS major** (T9 / WWDC → GM) | Rebase/merge `holzschu/a-shell` → fork; chạy CI `a-Shell-noPython`; smoke device |
| Mỗi **Xcode major** | Rebuild unsigned `a-Shell-noPython`; chỉnh `IPHONEOS_DEPLOYMENT_TARGET` nếu SDK reject (vd. 27.1 cần ≥15.0) |
| Mỗi bump nested SwiftTerm | Host E2E + manual terminal smoke (prompt/HostHelpers); không đổi runtime CSV 158 |

## Machine-readable

```yaml
# Docs/fork-registry.yaml (canonical copy also embedded here)
schema_version: 1
updated: "2026-11-28T08:56:00+07:00"
assert:
  git_submodule_count: 2
  git_submodules:
    - path: SwiftTerm
      url: https://github.com/jiaomeimei0-prog/SwiftTerm.git
      pin: 633a592ee9dd9585a0536314d26e906154ac43db
      tip_sot_main: 5345160eab8a4b787bc7f8ff1278f84c8f19bd83
      action: fork
      bump_status: stopped_gt_30_commits
    - path: cpython
      url: https://github.com/holzschu/cpython.git
      branch: "3.13"
      action: keep
  binary_target_count: 65
  binary_targets_source: Apps/a-Shell/xcfs/Package.swift
  podfile: false
monorepo:
  apps_a_shell_gitlink: e95741b8e59bef75cec490528f8f36a498555bcf
rebase_schedule:
  - trigger: ios_major
    actions: [merge_upstream_ashell, ci_noPython, device_smoke]
  - trigger: xcode_major
    actions: [rebuild_noPython, fix_deployment_target]
decisions:
  - id: ios_system_ecosystem
    action: keep
    reason: checksum-pinned holzschu binaries; fork breaks rebase
  - id: swiftterm_sot
    action: fork
    reason: emulator + HostHelpers owned by jiaomeimei0-prog/SwiftTerm
  - id: ashell_host
    action: fork
    reason: commands/Shortcuts/file UX live in a-shell host
```

Canonical YAML file: [`Docs/fork-registry.yaml`](fork-registry.yaml).
