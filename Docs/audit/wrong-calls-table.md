# Bảng lệnh gọi sai (sinh tự động)

**Còn lại sau khi sửa: 50**. Mỗi dòng là một lời gọi/tham chiếu sai hoặc cấu hình sai do detector tìm thấy; `data/wrong_calls.csv` có thêm cột bằng chứng.

| # | Mức | Loại | Vị trí | Lời gọi / tham chiếu | Vấn đề |
|---|---|---|---|---|---|
| 1 | LOW | `broken-doc-link` | `Docs/osc7501-delta.md:122` | `spec-diffs.md` | markdown link target does not exist |
| 2 | LOW | `broken-doc-link` | `Docs/osc7501-delta.md:148` | `spec-diffs.md` | markdown link target does not exist |
| 3 | LOW | `broken-doc-link` | `Docs/osc7501-delta.md:5` | `spec-diffs.md` | markdown link target does not exist |
| 4 | LOW | `broken-doc-link` | `PERFORMANCE.md:156` | `Docs/performance-osc7501-storage-fix.patch` | markdown link target does not exist |
| 5 | LOW | `broken-doc-link` | `PERFORMANCE.md:203` | `Docs/performance-osc7501-fix-2026-10-08.json` | markdown link target does not exist |
| 6 | LOW | `broken-doc-link` | `PERFORMANCE.md:206` | `Docs/performance-osc7501-fix-2026-10-08-baselines.json.gz` | markdown link target does not exist |
| 7 | LOW | `broken-doc-path` | `Apps/README.md:17` | `Apps/a-Shell/SwiftTerm` | path named in docs does not exist at this ref |
| 8 | LOW | `broken-doc-path` | `Docs/security-audit-egress-2026-11-26.md:180` | `Sources/CSwiftTerm` | path named in docs does not exist at this ref |
| 9 | LOW | `broken-doc-path` | `Docs/system-comparison-report-2026-11-26.md:239` | `Apps/a-Shell/SwiftTerm` | path named in docs does not exist at this ref |
| 10 | LOW | `broken-doc-path` | `Sources/SwiftTerm/Documentation.docc/Embedding.md:34` | `Docs/io-baselines.md` | path named in docs does not exist at this ref |
| 11 | LOW | `shebang-not-executable` | `ODR/forbidden_2023.sh` | `#! /bin/sh` | has a shebang but git mode is 100644 |
| 12 | LOW | `shebang-not-executable` | `ShellWorkers/resources.sh` | `#!/bin/bash` | has a shebang but git mode is 100644 |
| 13 | LOW | `shebang-not-executable` | `Tools/generate_kitty_parity_matrix.py` | `#!/usr/bin/env python3` | has a shebang but git mode is 100644 |
| 14 | LOW | `shebang-not-executable` | `Tools/import-ghostty-fuzz-corpus.swift` | `#!/usr/bin/env swift` | has a shebang but git mode is 100644 |
| 15 | LOW | `shebang-not-executable` | `ci/audit-artifact.py` | `#!/usr/bin/env -S uv run --script` | has a shebang but git mode is 100644 |
| 16 | LOW | `shebang-not-executable` | `fd/build.sh` | `#!/usr/bin/env bash` | has a shebang but git mode is 100644 |
| 17 | LOW | `shebang-not-executable` | `fd/tests/acceptance.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 18 | LOW | `shebang-not-executable` | `fd/tests/verify.sh` | `#!/usr/bin/env bash` | has a shebang but git mode is 100644 |
| 19 | LOW | `shebang-not-executable` | `fzf/tests/cold-shell.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 20 | LOW | `shebang-not-executable` | `fzf/tests/reentry.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 21 | LOW | `shebang-not-executable` | `gitoxide/acceptance.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 22 | LOW | `shebang-not-executable` | `navi/build.sh` | `#!/usr/bin/env bash` | has a shebang but git mode is 100644 |
| 23 | LOW | `shebang-not-executable` | `navi/tests/shell-route.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 24 | LOW | `shebang-not-executable` | `node/acceptance.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 25 | LOW | `shebang-not-executable` | `node/interactive.sh` | `#!/usr/bin/env sh` | has a shebang but git mode is 100644 |
| 26 | LOW | `shebang-not-executable` | `node/tests/acceptance.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 27 | LOW | `shebang-not-executable` | `ruff/build.sh` | `#!/bin/bash` | has a shebang but git mode is 100644 |
| 28 | LOW | `shebang-not-executable` | `ruff/tests/acceptance.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 29 | LOW | `shebang-not-executable` | `scripts/build-openrsync.sh` | `#!/bin/bash` | has a shebang but git mode is 100644 |
| 30 | LOW | `shebang-not-executable` | `scripts/esctest-known-good.py` | `#!/usr/bin/env python3` | has a shebang but git mode is 100644 |
| 31 | LOW | `shebang-not-executable` | `scripts/ios_input_ssh_server.py` | `#!/usr/bin/env python3` | has a shebang but git mode is 100644 |
| 32 | LOW | `shebang-not-executable` | `scripts/regen_unicode_width_data.py` | `#!/usr/bin/env python3` | has a shebang but git mode is 100644 |
| 33 | LOW | `shebang-not-executable` | `tests/cloud-download-wait.sh` | `#!/bin/bash` | has a shebang but git mode is 100644 |
| 34 | LOW | `shebang-not-executable` | `tests/cloud-files.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 35 | LOW | `shebang-not-executable` | `tests/fonts.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 36 | LOW | `shebang-not-executable` | `tests/openrsync/run.sh` | `#!/bin/bash` | has a shebang but git mode is 100644 |
| 37 | LOW | `shebang-not-executable` | `tests/photos-host.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 38 | LOW | `shebang-not-executable` | `tests/photos-link.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 39 | LOW | `shebang-not-executable` | `tests/photos-membership.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 40 | LOW | `shebang-not-executable` | `tests/photos.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 41 | LOW | `shebang-not-executable` | `tests/relay.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 42 | LOW | `shebang-not-executable` | `tests/url-logging/check.sh` | `#!/bin/sh` | has a shebang but git mode is 100644 |
| 43 | LOW | `shebang-not-executable` | `updatePythonFiles.sh` | `#! /bin/sh` | has a shebang but git mode is 100644 |
| 44 | LOW | `workflow-unpinned-actions` | `.github/workflows/cloudflare-pages-web.yml` | `actions/checkout@v4, actions/setup-node@v4` | third-party actions referenced by mutable tag instead of commit SHA |
| 45 | LOW | `workflow-unpinned-actions` | `.github/workflows/docc.yml` | `actions/checkout@v4, actions/configure-pages@v5, actions/dep` | third-party actions referenced by mutable tag instead of commit SHA |
| 46 | LOW | `workflow-unpinned-actions` | `.github/workflows/native-frameworks.yml` | `actions/checkout@v7, actions/download-artifact@v8, actions/s` | third-party actions referenced by mutable tag instead of commit SHA |
| 47 | LOW | `workflow-unpinned-actions` | `.github/workflows/openrsync.yml` | `actions/checkout@v7, actions/download-artifact@v8, actions/u` | third-party actions referenced by mutable tag instead of commit SHA |
| 48 | LOW | `workflow-unpinned-actions` | `.github/workflows/pico-framework.yml` | `actions/checkout@v7, actions/download-artifact@v8, actions/u` | third-party actions referenced by mutable tag instead of commit SHA |
| 49 | LOW | `workflow-unpinned-actions` | `.github/workflows/web-wasm.yml` | `actions/checkout@v4, actions/setup-node@v4, actions/upload-a` | third-party actions referenced by mutable tag instead of commit SHA |
| 50 | LOW | `workflow-unpinned-actions` | `.github/workflows/xcode.yml` | `actions/checkout@v4, actions/upload-artifact@v4` | third-party actions referenced by mutable tag instead of commit SHA |

## Đã khắc phục so với baseline `1f7528c068` (34 chỗ)

| Loại | File | Số chỗ đã sửa |
|---|---|---|
| `ps1-hardcoded-root` | `scripts/serve-named-tunnel-domain.ps1` | 2 |
| `ps1-hardcoded-root` | `scripts/serve-via-cloudflare-tunnel.ps1` | 2 |
| `ps1-hardcoded-root` | `scripts/windows-bringup-toolvip1.ps1` | 2 |
| `ps1-hardcoded-root` | `scripts/windows-install-persistent-tunnel.ps1` | 1 |
| `ps1-hardcoded-root` | `scripts/windows-persistent-e2e.ps1` | 4 |
| `ps1-hardcoded-root` | `scripts/windows-start-my-machine-and-tunnel.ps1` | 1 |
| `ps1-no-bom` | `scripts/serve-via-cloudflare-tunnel.ps1` | 1 |
| `workflow-permissions` | `.github/workflows/web-wasm.yml` | 1 |
| `workflow-permissions` | `.github/workflows/xcode.yml` | 1 |
| `wrong-domain-reference` | `.github/workflows/cloudflare-pages-web.yml` | 4 |
| `wrong-domain-reference` | `Docs/tooltop1-domain-check-and-guide.md` | 9 |
| `wrong-domain-reference` | `Docs/web-cloudflare-setup.md` | 2 |
| `wrong-domain-reference` | `Web/cloudflare/wrangler.toml` | 2 |
| `wrong-domain-reference` | `scripts/cloudflare-connect-domain.sh` | 2 |

Baseline là kết quả của chính bộ detector này chạy trên commit trước khi sửa (`data/baseline/wrong_calls.csv`).
