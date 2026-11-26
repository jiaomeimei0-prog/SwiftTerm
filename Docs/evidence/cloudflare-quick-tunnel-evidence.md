# Evidence log — Cloudflare Quick Tunnel

- Created: **2026-11-26 18:42:11 Asia/Bangkok** (`2026-11-26T11:42:11Z`)
- Curl index via CF: **2026-11-26 18:43:02 Asia/Bangkok** (`2026-11-26T11:43:02Z`)

## Tunnel process
```
pid=28779
alive=yes
log=/tmp/cf-tunnel.log
```

## URL from cloudflared log
```
https://folks-assumed-met-engine.trycloudflare.com
```

## Command A — index via Cloudflare
```
curl -sS -D- -o /tmp/cf_idx.html -w "exit_http=%{http_code}\n" --connect-timeout 25 https://folks-assumed-met-engine.trycloudflare.com/
```
### Result
```
HTTP/2 200 
date: Thu, 26 Nov 2026 11:43:02 GMT
content-type: text/html
cf-ray: a608a21a8ccce762-IAD
cf-cache-status: DYNAMIC
last-modified: Thu, 26 Nov 2026 09:43:27 GMT
server: cloudflare
x-robots-tag: none
x-robots-tag: none


exit_http=200
```
### Body head
```
<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwiftTerm WASM (Cloudflare)</title>
<style>body{margin:2rem;background:#17191d;color:#eee;font:16px system-ui}.terminal{position:relative;width:max-con
```

## Command B — WASM via Cloudflare
```
curl -sS -o /tmp/cf_wasm -w "http=%{http_code} size=%{size_download} type=%{content_type}\n" --connect-timeout 40 https://folks-assumed-met-engine.trycloudflare.com/pkg/swiftterm-embedded.wasm
```
### Result
```
http=200 size=909857 type=application/wasm
/tmp/cf_wasm: WebAssembly (wasm) binary module version 0x1 (MVP)
```

## Command C — local still up
```
local_index http=200
```

## Note — bot fetch vs curl/browser
- `curl` to the trycloudflare URL: **HTTP 200** (commands A/B above).
- Some automated HTML fetchers may see **403** from Cloudflare challenge; that is not a site failure when curl/browser return 200.

## Honesty boundary
- This proves: SwiftTerm WASM demo is reachable over Cloudflare Quick Tunnel in a real browser/network path.
- This does NOT prove: a-Shell 158 ios_system commands executed on device.
- Sessions left running: python http.server :8765 + cloudflared (pid above).
## Live process check 2026-11-26T11:45:10Z
```
    PID     ELAPSED CMD
  28011       03:49 python3 -m http.server 8765 --bind 127.0.0.1
  28779       03:01 /tmp/cloudflared tunnel --url http://127.0.0.1:8765
local=200 cf=200
```
