# Workers Builds `swiftterm` disconnect — 2026-11-28

## Evidence (anti-fake)

| Commit | Check `Workers Builds: swiftterm` |
|--------|-----------------------------------|
| `37666cf` (PR #39) | **failure** (Build ID `ed90d8a4-…`, Worker still linked) |
| `d8b28ca` (PR #40) | **absent** after ≥90s poll of check-runs (no Cloudflare Workers app check) |

Pages job `46070836385` / claim step: **success** (script resolves `script_tag`, deletes Builds triggers, then Worker script).

Account (from prior check details_url): `a5cbbbbe8c9d28e7d63c63f4ef24def9`.

## Still optional for user

- If a later push revives the check: Dashboard → Workers → `swiftterm` → Settings → Builds → Disconnect (or Roll token with Workers Builds Configuration:Edit — see `Docs/cloudflare-token-dns-edit.md`).
- Zone DNS:Edit still needed for CI-managed CNAME (apex already live via manual DNS + user Safari verify).
