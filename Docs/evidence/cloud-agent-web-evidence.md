# Evidence log — Cloud Agent host 2026-11-26T11:41:21Z

## Command 1
```
curl -sS -D- -o /tmp/idx.html -w "\nexit=%{http_code}\n" http://127.0.0.1:8765/
```
### Result
```
HTTP/1.0 200 OK
Server: SimpleHTTP/0.6 Python/3.12.3
Date: Thu, 26 Nov 2026 11:41:21 GMT
Content-type: text/html
Content-Length: 1158
Last-Modified: Thu, 26 Nov 2026 09:43:27 GMT


exit_http=200
```
### Body head
```
<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwiftTerm WASM (Cloudflare)</title>
<style>body{margin:2rem;background:#17191d;color:#eee;font:16px system-ui}.terminal{position:relative;width:max-content;max-width:100%;outline:1px solid #777}canvas{display:block;max-width:100%}textarea{position:absolute;width:1px;heig
```

## Command 2
```
curl -sS -o /tmp/wasm -w "http=%{http_code} size=%{size_download} type=%{content_type}\n" http://127.0.0.1:8765/pkg/swiftterm-embedded.wasm
```
### Result
```
http=200 size=909857 type=application/wasm
/tmp/wasm: WebAssembly (wasm) binary module version 0x1 (MVP)
```

## Command 3
```
curl -sS -o /tmp/main.js -w "http=%{http_code} size=%{size_download}\n" http://127.0.0.1:8765/pkg/example/main.js
```
### Result
```
http=200 size=1450
import { loadSwiftTerm, TerminalInputController } from '../src/index.js';
import { CanvasTerminalRenderer } from './canvas2d.js';
const variant = new URL(location.href).searchParams.get('variant') ===
```

---

## Update — Cloudflare Quick Tunnel (same session, left running)

See `Docs/evidence/cloudflare-quick-tunnel-evidence.md`.

- URL: https://folks-assumed-met-engine.trycloudflare.com
- Index via CF: HTTP 200 (`cf-ray` present, `server: cloudflare`)
- WASM via CF: HTTP 200 size=909857 `application/wasm`
- Processes left open: `python -m http.server 8765` + `cloudflared tunnel --url http://127.0.0.1:8765`
