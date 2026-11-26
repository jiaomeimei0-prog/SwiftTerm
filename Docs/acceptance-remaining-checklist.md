# Checklist nghiệm thu còn lại — cập nhật 2026-11-26 21:38 Asia/Bangkok

## Đã đạt (có lệnh/evidence)

| Hạng mục | Trạng thái | Evidence |
|----------|------------|----------|
| Catalogue 158 identity (plist) | PASS source | `Docs/command-158-device-matrix-PENDING.csv` |
| Host E2E SwiftTerm / HostHelpers | PASS host | `Docs/e2e-acceptance-results.md` |
| Quick Tunnel + browser WASM | PASS (agent) | `Docs/evidence/cloudflare-quick-tunnel-evidence.md` |
| Windows PS1 tunnel fixes | PR #28 OPEN | https://github.com/jiaomeimei0-prog/SwiftTerm/pull/28 |
| One-shot bring-up PC | Có script | `scripts/windows-bringup-toolvip1.ps1` |

## Chưa đạt (cần PC Windows / dashboard)

| Hạng mục | Blocker | Cách đóng |
|----------|---------|-----------|
| `https://toolvip1.top` bền vững | Error 1033 khi `cloudflared` tắt; từng Hello World (Worker); từng Access | Chạy bring-up; giữ HTTP+tunnel mở; DNS CNAME -> `swiftterm-web` không Worker |
| Cloudflare Pages deploy CI | GitHub secrets `CLOUDFLARE_*` trống | Thêm secrets + workflow_dispatch |
| 158 lệnh runtime a-Shell | Không có iOS device trong agent | User chạy `verify_command_catalogue_158.sh` trên máy, điền CSV |
| Agent gõ lệnh trên PC bạn | Không có self-hosted worker | `agent worker start` trên Windows |

## Lệnh đóng domain trên PC (bắt buộc giữ cửa sổ)

```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git fetch origin
git checkout cursor/fix-named-tunnel-ps1-45fd
git pull origin cursor/fix-named-tunnel-ps1-45fd
powershell -ExecutionPolicy Bypass -File .\scripts\windows-bringup-toolvip1.ps1
```

PASS domain khi:

```powershell
$r = Invoke-WebRequest https://toolvip1.top/ -UseBasicParsing
$r.StatusCode
$r.Content.Substring(0, [Math]::Min(200, $r.Content.Length))
```

Body có `SwiftTerm WASM` — không 1033 / Hello World / Sign in.

## Verdict trung thực

- **Không** gọi hoàn thành tuyệt đối (158 + domain bền + Pages) cho đến khi checklist trên đóng và bạn đối chiếu.
- Domain từng hiện SwiftTerm khi tunnel chạy; Error 1033 = tunnel đã dừng — không phải lỗi code repo.

## Browser recheck (agent) — 2026-11-26 21:39 Asia/Bangkok

**FAIL** public `https://toolvip1.top/`: Chrome `ERR_CONNECTION_CLOSED` (not SwiftTerm). Evidence: `Docs/evidence/toolvip1-top-browser-fail-2026-11-26.md`.

PC must re-run `scripts/windows-bringup-toolvip1.ps1` and keep both windows open.
