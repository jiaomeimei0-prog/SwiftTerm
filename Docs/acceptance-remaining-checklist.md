# Checklist nghiem thu con lai — cap nhat 2026-11-26 21:53 Asia/Bangkok

## Da dat (co lenh/evidence)

| Hang muc | Trang thai | Evidence |
|----------|------------|----------|
| Catalogue 158 identity (plist) | PASS source | `Docs/command-158-device-matrix-PENDING.csv` |
| Host E2E SwiftTerm / HostHelpers | PASS host | `Docs/e2e-acceptance-results.md` |
| Quick Tunnel + browser WASM | PASS (agent) | `Docs/evidence/cloudflare-quick-tunnel-evidence.md` |
| Windows PS1 tunnel fixes | PR #28 OPEN (Bugbot 4 fixes) | https://github.com/jiaomeimei0-prog/SwiftTerm/pull/28 |
| One-shot bring-up + persistent + My Machines | Co script | `scripts/windows-start-my-machine-and-tunnel.ps1` |

## Chua dat (can PC Windows / dashboard)

| Hang muc | Blocker | Cach dong |
|----------|---------|-----------|
| `https://toolvip1.top` ben vung | Tunnel down (SSL EOF / 1033). Probe agent 21:53 ICT: FAIL | Chay one-shot; giu worker; tunnel detached |
| Cloudflare Pages deploy CI | GitHub secrets `CLOUDFLARE_*` trong | Them secrets + workflow_dispatch |
| 158 lenh runtime a-Shell | Khong co iOS device trong agent | User chay verify tren may, dien CSV |
| Agent go lenh tren PC ban | `list-self-hosted-workers` = `workers: []` | Cai tool chua du — phai `agent worker start` KEEP OPEN |

## One-shot tren PC (worker + tunnel)

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git fetch origin
git checkout cursor/fix-named-tunnel-ps1-45fd
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\windows-start-my-machine-and-tunnel.ps1
```

PASS domain khi body `https://toolvip1.top/` co `SwiftTerm` — khong 1033 / Hello World / Sign in.

## Verdict trung thuc

- **Khong** goi hoan thanh tuyet doi (158 + domain ben + Pages) cho den khi checklist dong va ban doi chieu.
- Agent **khong the** go lenh tren PC khi workers rong — cai Use my computer / CLI thoi chua bat worker.
- Public probe 2026-11-26T14:53Z: apex SSL_ERROR_SYSCALL; www NXDOMAIN. Evidence: `Docs/evidence/toolvip1-public-probe-2026-11-26-agent-vm.json`.
