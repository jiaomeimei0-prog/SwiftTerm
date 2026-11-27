# Domain connection probe — real commands

> Redaction note (2026-11-26): the signed `meta=` JWT values in the Cloudflare Access redirect URLs were replaced with `<JWT-REDACTED>` to keep token-shaped strings out of the repository. All other captured bytes are unchanged.

- Generated: 2026-11-26T11:59:20Z UTC / 2026-11-26 18:59:20 Asia/Bangkok

## Command 1 — dig tooltop1.vip @1.1.1.1
```
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 31440
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 1232
```

## Command 2 — RDAP tooltop1.vip
```
curl -sS -o /tmp/rdap_tt.json -w 'http=%{http_code}\n' https://rdap.nic.vip/domain/tooltop1.vip
http=404
errorCode= 404 title= Not found
```

## Command 3 — dig/curl toolvip1.top (existing CF zone)
```
104.21.95.42
172.67.142.251
jarred.ns.cloudflare.com.
raegan.ns.cloudflare.com.
HTTP/2 302 
date: Thu, 26 Nov 2026 11:59:23 GMT
content-type: text/html; charset=UTF-8
location: https://purple-frost-65fb.cloudflareaccess.com/cdn-cgi/access/login/toolvip1.top?kid=ef42951ccde0df96f503cbfb92e062fddd628173a381bcdafe21f8acf1c71e17&meta=<JWT-REDACTED>&redirect_url=%2F
set-cookie: CF_AppSession=d798d8d371e17b2b; Expires=Fri, 27 Nov 2026 11:59:23 GMT; Path=/; Secure; HttpOnly
access-control-allow-credentials: true
cache-control: private, max-age=0, no-store, no-cache, must-revalidate, post-check=0, pre-check=0
expires: Thu, 01 Jan 1970 00:00:01 GMT
www-authenticate: Cloudflare-Access resource_metadata="https://toolvip1.top/.well-known/cloudflare-access-protected-resource/"
speculation-rules: "/cdn-cgi/speculation"
report-to: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=bem11kI9mQFy1r4Okgb%2FiDxhoibEOp6Q99T4Z7M8cJFk4E4BcmidW5PKjhrYM7L30%2FnBOf9LJ4yJV6G5wc8nlVIsMnrvrsPE7Nd63Cpl%2Bq2Z3HrzH2Z7gJeoA%2BLglrQ%3D"}]}
nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
server: cloudflare
cf-ray: a608ba0969666825-IAD
alt-svc: h3=":443"; ma=86400

http=302 redirect=https://purple-frost-65fb.cloudflareaccess.com/cdn-cgi/access/login/toolvip1.top?kid=ef42951ccde0df96f503cbfb92e062fddd628173a381bcdafe21f8acf1c71e17&meta=<JWT-REDACTED>&redirect_url=%2F
```

## Command 4 — Access metadata
```
{
    "resource": "https://toolvip1.top",
    "protected": true,
    "team_domain": "purple-frost-65fb.cloudflareaccess.com",
    "authorization_servers": [
        "https://purple-frost-65fb.cloudflareaccess.com"
    ],
    "authentication_methods": [
        {
            "name": "cloudflared",
            "description": "Use `cloudflared access curl` to make the request to the protected resource. This will allow the user to authenticate interactively and authentication information will automatically be added to the request",
            "documentation": "https://developers.cloudflare.com/cloudflare-one/tutorials/cli/"
        }
    ]
}
```

## Command 5 — GitHub Actions last CF deploy secrets
```
CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID were EMPTY in run 45803275310 (deploy failed intentionally).
```

## Verdict (honest)
- **tooltop1.vip**: NXDOMAIN + RDAP HTTP 404 — domain **chưa đăng ký / không tồn tại** trên registry .vip. Không thể gắn Pages/Tunnel hostname cho domain chưa có.
- **toolvip1.top**: DNS Cloudflare OK nhưng **Cloudflare Access** chặn công khai (302 → purple-frost-65fb.cloudflareaccess.com Sign-in). Không phục vụ SwiftTerm WASM.
- **Pages deploy**: blocked — GitHub secrets CLOUDFLARE_* trống.
- Quick Tunnel đang chạy: https://folks-assumed-met-engine.trycloudflare.com (không phải custom domain).

## Command 6 — connect script without secrets
```
bash scripts/cloudflare-connect-domain.sh tooltop1.vip
exit=1
FAIL: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set in the environment.
Add them as GitHub Actions secrets, then re-run the Cloudflare Pages workflow.
```
