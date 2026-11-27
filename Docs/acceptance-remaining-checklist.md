# Checklist nghiem thu con lai — cap nhat 2026-11-28 04:35 Asia/Saigon

## Da dat (co lenh/evidence)

| Hang muc | Trang thai | Evidence |
|----------|------------|----------|
| Catalogue 158 identity (plist) | PASS source | `Docs/command-158-device-matrix-PENDING.csv` |
| Host E2E SwiftTerm / HostHelpers | PASS host | `Docs/e2e-acceptance-results.md` |
| Quick Tunnel + browser WASM | PASS (agent) | `Docs/evidence/cloudflare-quick-tunnel-evidence.md` |
| a-Shell pin sau #8 | PASS | `Apps/a-Shell` → `e95741b8` (PR #39) |
| `https://toolvip1.top` SwiftTerm WASM | PASS (user device) | `Docs/evidence/toolvip1-user-verify-swiftterm-2026-11-28.md` |
| Cloudflare Pages deploy CI | PASS | run `46070836385` success |
| Workers Builds `swiftterm` | PASS disconnect | `Docs/evidence/workers-builds-swiftterm-disconnect-2026-11-28.md` (check absent on `d8b28ca`) |
| L4 runbook + verify script | PASS prep | `Docs/l4-device-acceptance-runbook.md` + pin script |
| DNS/Builds token docs | PASS docs | `Docs/cloudflare-token-dns-edit.md` |

## Chua dat (can device / dashboard)

| Hang muc | Blocker | Cach dong |
|----------|---------|-----------|
| L4 — 158 lenh runtime tren device | Agent khong co iPhone/iPad | Chay `verify_command_catalogue_158.sh` trong a-Shell; dien CSV |
| Token DNS:Edit / Builds (neu DNS API van 403) | Secret GitHub do user Roll | `Docs/cloudflare-token-dns-edit.md` |
| Agent go lenh tren PC ban | `list-self-hosted-workers` = rong | `agent worker start` KEEP OPEN |

## L4 tren device (con thieu)

```sh
# Trong a-Shell (sau build pin e95741b8+):
sh verify_command_catalogue_158.sh
# Ky vong: ACCEPT: all 158 catalogue names present in help -l
```

Chi tiet: `Docs/l4-device-acceptance-runbook.md`.

## Verdict trung thuc

- Domain Pages + pin a-Shell + dọn Workers Builds: **dat** (evidence tren).
- **Chua** goi xong tuyet doi: L4 158 runtime van `PENDING_USER_DEVICE`.
- Agent VM co the SSL_ERROR_SYSCALL toi apex; nghiem thu domain lay tu user Safari + Pages CI, khong tu probe agent.
