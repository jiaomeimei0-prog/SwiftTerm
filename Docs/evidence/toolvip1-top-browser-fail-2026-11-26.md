# toolvip1.top browser probe — FAIL

- Asia/Bangkok: 2026-11-26 21:40:00
- UTC: 2026-11-26T14:40:00Z
- Agent: Browser check toolvip1.top (bc-16259916-51f3-5919-810f-44381a4a2d0b)

## Result
- Chrome: **This site can't be reached** / `ERR_CONNECTION_CLOSED`
- Not Error 1033 page, not Hello World, not Access, not SwiftTerm
- curl from agent: SSL_ERROR_SYSCALL / http=000
- DNS still resolves to Cloudflare IPv6 (proxied)

## Interpretation
Tunnel origin not reachable from public edge — typically `cloudflared` / local HTTP not running on the Windows PC, or TLS terminated then connection reset.

## Recovery on PC
```powershell
cd $env:USERPROFILE\Documents\SwiftTerm
git pull origin cursor/fix-named-tunnel-ps1-45fd
powershell -ExecutionPolicy Bypass -File .\scripts\windows-bringup-toolvip1.ps1
```

Screenshot: /opt/cursor/artifacts/toolvip1-top-connection-closed.webp
