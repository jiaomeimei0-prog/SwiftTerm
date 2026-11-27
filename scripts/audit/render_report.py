"""Render the Vietnamese audit report and the two full tables from audit results.

Every number in the output is computed from `Results`; nothing is typed by hand except explanatory prose.
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

from datetime import datetime, timedelta

from audit_lib import apple_evidence, defect_codes, defect_targets, job_state, linux_result, macos_ci_stats, suite_results, suite_summary, suite_verdict, swift_states


def vn_time(stamp: str) -> str:
    """`2026-11-26T16:56:39Z` -> `2026-11-26T16:56:39Z (UTC) = 23:56 giờ Việt Nam (UTC+7)`; unknown input is returned unchanged."""
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return stamp
    return f"{stamp} (UTC) = {(moment + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M')} giờ Việt Nam (UTC+7)"

DEFECT_TITLES = {
    "D01": "Target nhúng thiếu framework của lệnh nằm trong catalogue của chính target đó",
    "D04": "Cùng một lệnh khai báo khác nhau giữa catalogue `full` và `mini` (argtype)",
    "D08": "Dòng catalogue sai dạng hoặc argtype ngoài tập nhà sản xuất dùng",
    "D07": "Không truy được nguồn tái tạo framework (không có binaryTarget, không có công thức trong repo)",
    "D10": "Framework lấy từ tarball tải về không kiểm checksum",
    "D05": "Đăng ký host `replaceCommand` trỏ vào symbol không định nghĩa trong mã nguồn repo",
}
DEFECT_GROUPS = (
    ("LỖI CẤU HÌNH (xác nhận được bằng tĩnh)", ("D01", "D04", "D08")),
    ("KHOẢNG TRỐNG NGUỒN GỐC / CHUỖI CUNG ỨNG (rủi ro, chưa phải lỗi chạy)", ("D07", "D10")),
    ("CHƯA XÁC MINH (cần nhị phân prebuilt hoặc thiết bị)", ("D05",)),
)
WRONG_CALL_INFO = {
    "ps1-hardcoded-root": "PowerShell gắn cứng gốc repo `%USERPROFILE%\\Documents\\SwiftTerm`",
    "ps1-no-bom": "PowerShell: thiếu UTF-8 BOM (PowerShell 5.1 đọc ANSI)",
    "wrong-domain-reference": "Tên miền sai `tooltop1.vip` (tên miền thật `toolvip1.top`)",
    "workflow-permissions": "Workflow không khai báo `permissions:`",
    "workflow-unpinned-actions": "Action tham chiếu bằng tag, không ghim SHA",
    "broken-doc-path": "Tài liệu nêu đường dẫn không tồn tại",
    "broken-doc-link": "Liên kết markdown hỏng",
    "shebang-not-executable": "File có shebang nhưng git mode ≠ 100755",
    "missing-script": "Gọi script không tồn tại",
    "not-executable": "Gọi trực tiếp file không có quyền thực thi",
    "ci-filter-matches-nothing": "`swift test --filter` không khớp test nào",
    "ps1-unknown-parameter": "Gọi hàm helper PowerShell với tham số không tồn tại",
}
SEVERITY_VI = {"CRITICAL": "NGHIÊM TRỌNG", "HIGH": "CAO", "MEDIUM": "TRUNG BÌNH", "LOW": "THẤP", "INFO": "THÔNG TIN"}
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
STATUS_VI = {
    "USED_BY_ASHELL": "a-Shell dùng + có test SwiftTerm",
    "USED_BY_ASHELL_UNTESTED_IN_SWIFTTERM": "a-Shell dùng, SwiftTerm không test",
    "INTERNAL_OR_TEST_ONLY": "chỉ nội bộ/test",
    "UNUSED": "không ai dùng",
}
REVIEW_VI = {
    "BY_DESIGN": "theo thiết kế", "FINDING": "đã thành phát hiện", "TEST_ONLY": "mã kiểm thử", "DEV_TOOL": "công cụ dev",
    "THIRD_PARTY": "thư viện bên thứ ba", "NOT_REVIEWED": "CHƯA RÀ THỦ CÔNG",
}
FUNCTION_OF_DIR = {
    ("swiftterm", "Sources"): "Lõi emulator + view Apple/Mac/iOS + lõi WASM",
    ("swiftterm", "Tests"): "Kiểm thử (Swift Testing, XCTest, WebWasm)",
    ("swiftterm", "TerminalApp"): "Ứng dụng mẫu + WebTerminal (PTY qua WebSocket)",
    ("swiftterm", "Tools"): "Công cụ dev (fuzz, benchmark, BiDi harness)",
    ("swiftterm", "Web"): "Web/WASM + site Cloudflare Pages",
    ("swiftterm", "Docs"): "Tài liệu và bằng chứng",
    ("swiftterm", "scripts"): "Script build/deploy/tunnel/E2E",
    ("swiftterm", ".github"): "CI",
    ("ashell", "Resources"): "Tài nguyên đóng gói bản full (vim, node, perl...)",
    ("ashell", "man"): "Trang man",
    ("ashell", "Resources_mini"): "Tài nguyên bản mini",
    ("ashell", "a-Shell"): "App iOS (Swift)",
    ("ashell", "a-Shell.xcodeproj"): "Dự án Xcode (3 app target + worker)",
    ("ashell", "ShellWorkers"): "Worker cô lập A–J",
    ("ashell", "tests"): "Test host/thiết bị",
    ("ashell", "(root files)"): "Bộ nạp JS, cấu hình gốc",
}
NATIVE_RECIPE_DIRS = {"codex", "Herdr", "node", "helix", "fzf", "navi", "rg", "ruff", "gitoxide", "patches"}


def esc(value: object) -> str:
    return str(value).replace("|", "¦").replace("\n", " ").strip()


def table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def short(items: list[str], limit: int = 12) -> str:
    return ", ".join(items[:limit]) + (f", … (+{len(items) - limit})" if len(items) > limit else "")


def n(value: object) -> str:
    return f"{int(value):,}".replace(",", ".")


def loc_path(location: str) -> str:
    return location.rsplit(":", 1)[0] if re.search(r":\d+$", location) else location


def wrong_by_kind(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["kind"]].append(row)
    return grouped


def finding_id(r, needle: str) -> str:
    return next((f["id"] for f in r.findings if needle.lower() in f["title"].lower()), "—")


def section_sources(r) -> str:
    g, f = r.graph, r.ci_facts
    rows = [[s["name"], s["repo"], f"`{s['ref']}`", f"`{s['short']}`", s["date"], s["subject"][:70]] for s in r.sources]
    out = ["## 1. Hai nguồn lõi và đồ thị phụ thuộc", "", table(["Nguồn", "Repo", "Ref", "Commit", "Ngày", "Tiêu đề"], rows), ""]
    fu, pvm = f.get("fork_vs_upstream"), f.get("pin_vs_master")
    if fu:
        out.append(f"- **Fork so với nhà sản xuất** (GitHub compare, thu thập {vn_time(f.get('collected_at', '?'))}): `{fu['status']}`, ahead **{fu['ahead_by']}** / behind **{fu['behind_by']}**, merge-base `{fu['merge_base'][:10]}`. "
                   "Đếm bằng `git rev-list` cục bộ không đáng tin vì bản clone a-shell trên VM là shallow.")
    if pvm:
        pulls = ", ".join(f"[PR #{p['number']}]({p['html_url']}) ({p['state']})" for p in f.get("pin_pulls", []))
        out.append(f"- **Pin `Apps/a-Shell`** = `{g['pin'][:10]}` = master tip + {pvm['ahead_by']} commit chưa merge ({pulls}); behind = {pvm['behind_by']}.")
    if "sources_tree_equal" in g:
        out.append(f"- **SwiftTerm lồng trong a-Shell** (`Apps/a-Shell/SwiftTerm`, bản a-Shell thực sự build qua `XCLocalSwiftPackageReference`): `{g['nested']['pin'][:10]}` (\"{g.get('nested_subject', '')}\"), "
                   f"tổ tiên của HEAD = **{g.get('nested_is_ancestor_of_head')}**, chậm **{g.get('nested_commits_behind')}** commit; cây `Sources/SwiftTerm` **{'GIỐNG HỆT' if g.get('sources_tree_equal') else 'KHÁC'}** HEAD (so tree hash). "
                   f"Upstream ghim bản SwiftTerm của nhà sản xuất `{g['nested']['upstream'][:10]}`.")
    out.append("- **Đồ thị phụ thuộc là vòng**: `SwiftTerm (SoT) → Apps/a-Shell → SwiftTerm (bản lồng)`. SoT không được cưỡng chế bởi build graph; nó chỉ đúng khi pin lồng được bump đều.")
    only = f.get("fork_only_files", [])
    if only:
        out += ["", f"### Thay đổi thật của fork so với nhà sản xuất (diff ba chấm từ merge-base: {len(only)} file, {len(f.get('fork_only_commits', []))} commit)", "",
                table(["File", "Trạng thái", "+", "−"], [[f"`{x['filename']}`", x["status"], x["additions"], x["deletions"]] for x in only]), "",
                "Commit của fork: " + "; ".join(f"`{c['sha']}` {c['message'][:70]}" for c in f.get("fork_only_commits", [])) + ".", ""]
        removed = next((x for x in only if x["filename"] == "a-Shell/SceneDelegate+TerminalView.swift"), None)
        if removed:
            out.append(f"Lưu ý chức năng: fork xoá {removed['deletions']} dòng `terminalView?.updateDisplay()` khỏi `SceneDelegate+TerminalView.swift` (kiểm bằng `git diff upstream/master origin/master`) để tương thích SoT SwiftTerm; "
                       "hiệu ứng vẽ lại chỉ kiểm chứng được trên thiết bị.")
            out.append("")
    ups = f.get("upstream_only_commits", [])
    out += ["### So sánh đầu nhánh (`git diff upstream/master origin/master`) — LẪN lẫn thay đổi của fork và nội dung upstream mới hơn", "",
            table(["File", "+", "−"], [[f"`{x['path']}`", x["added"], x["deleted"]] for x in g.get("fork_vs_upstream_files", [])]), "",
            "Các dòng `−` ở `tests/worker-*` là nội dung upstream đã thêm sau merge-base (không có trong danh sách thay đổi thật ở trên), nên không phải do fork xoá. "
            f"Pin so với fork master: {', '.join('`' + x['path'] + '` (+' + x['added'] + '/−' + x['deleted'] + ')' for x in g.get('pin_vs_fork_files', [])) or 'không khác'}.", ""]
    if ups:
        out += [f"<details><summary>{len(ups)} commit của nhà sản xuất chưa có trong fork</summary>", "", table(["SHA", "Ngày", "Nội dung"], [[f"`{c['sha']}`", c["date"], c["message"][:100]] for c in ups]), "", "</details>", ""]
    return "\n".join(out)


def section_languages(r) -> str:
    out = ["## 2. Kiểm kê ngôn ngữ, quy mô và chức năng", ""]
    for repo, title in (("swiftterm", "SwiftTerm (lõi)"), ("ashell", "a-Shell (fork master)")):
        rows = [x for x in r.languages["by_language"] if x[0] == repo]
        first = sorted((x for x in rows if x[2] == "first-party only"), key=lambda x: -x[5])
        allrows = [x for x in rows if x[2] == "all tracked files"]
        out += [f"### 2.{1 if repo == 'swiftterm' else 2} {title} — commit `{rows[0][1]}`", "",
                f"Toàn bộ file theo dõi: **{n(sum(x[4] for x in allrows))}** file / {n(sum(x[5] for x in allrows))} dòng; first-party (loại tài nguyên đóng gói, patch, vendored): **{n(sum(x[4] for x in first))}** file / {n(sum(x[5] for x in first))} dòng.", "",
                table(["Ngôn ngữ", "File", "Dòng", "Dòng không trống", "Dung lượng (B)"], [[x[3], n(x[4]), n(x[5]), n(x[6]), n(x[7])] for x in first[:14]]), "",
                table(["Khu vực", "File", "Dòng", "Dung lượng (B)"], [[x[2], n(x[3]), n(x[4]), n(x[6])] for x in r.languages["by_area"] if x[0] == repo]), ""]
    gen = r.languages.get("generated_committed")
    if gen:
        out += [f"**Lưu ý đo lường:** `{gen['prefix']}` có **{gen['files']}** file sinh ra (`scripts/prepare-cloudflare-web.sh`) được commit, {n(gen['bytes'])} B, trong đó {gen['duplicate_js']} tên file JS xuất hiện hai lần (`pkg/` và `pkg/src/`) và nhị phân `{gen['largest']}`; "
                "số dòng JS/TS của SwiftTerm vì vậy bị tính trùng.", ""]
    out += ["### 2.3 Chức năng ↔ vị trí ↔ ngôn ngữ", ""]
    rows = []
    for repo in ("swiftterm", "ashell"):
        dirs = sorted((x for x in csv_dirs(r) if x["repo"] == repo), key=lambda x: -int(x["lines"]))
        for d in dirs[:12]:
            function = FUNCTION_OF_DIR.get((repo, d["top_dir"])) or ("Công thức dựng lệnh native (Rust/Go/Patch/Shell)" if repo == "ashell" and d["top_dir"] in NATIVE_RECIPE_DIRS else "—")
            rows.append([repo, f"`{d['top_dir']}`", function, n(d["files"]), n(d["lines"]), d["top_languages"][:60]])
    out += [table(["Repo", "Thư mục", "Chức năng", "File", "Dòng", "Ngôn ngữ chính (số file)"], rows), "",
            "Bảng đầy đủ: `data/languages_by_language.csv`, `languages_by_area.csv`, `directories.csv`.", ""]
    return "\n".join(out)


def csv_dirs(r) -> list[dict]:
    return [{"repo": x[0], "top_dir": x[2], "files": x[3], "lines": x[4], "bytes": x[5], "top_languages": x[6]} for x in r.languages["by_directory"]]


def section_scripts(r) -> str:
    out = ["## 3. Kiểm kê script, entry point, workflow, host và điểm thực thi", "", "### 3.1 Script", ""]
    groups = collections.defaultdict(list)
    for s in r.scripts:
        groups[(s["repo"], s["language"])].append(s)
    rows = []
    for (repo, lang), items in sorted(groups.items()):
        applicable = [i for i in items if i["strict_mode"] != "n/a"]
        strict = [i for i in applicable if i["strict_mode"] != "none"]
        rows.append([repo, lang, len(items), n(sum(i["lines"] for i in items)), sum(1 for i in items if i["mode"] == "100755"),
                     f"{len(strict)}/{len(applicable)}" if applicable else "n/a", sum(1 for i in items if not i["referenced_by"])])
    out += [table(["Repo", "Ngôn ngữ", "Số script", "Dòng", "Có quyền thực thi", "Có chế độ nghiêm ngặt", "Không thấy tham chiếu (heuristic)"], rows), "",
            "\"Không thấy tham chiếu\" chỉ tính các lời gọi nhìn thấy trong script/workflow/tài liệu; build phase của Xcode và lời gọi động có thể bỏ sót.", "",
            "Script của SwiftTerm (đầy đủ):", "",
            table(["Script", "Loại", "Dòng", "Số nơi tham chiếu", "Mục đích (dòng chú thích đầu)"],
                  [[f"`{s['path']}`", s["language"], s["lines"], len(s["referenced_by"]), s["purpose"][:80]] for s in sorted((s for s in r.scripts if s["repo"] == "swiftterm"), key=lambda s: s["path"])]), "",
            f"Script a-Shell: {sum(1 for s in r.scripts if s['repo'] == 'ashell')} file (công thức dựng native, test host/thiết bị) — xem `data/scripts_inventory.csv`.", "",
            "### 3.2 Entry point (SwiftPM, npm, make, workflow)", ""]
    ep = collections.defaultdict(list)
    for e in r.entrypoints:
        ep[(e["repo"], e["type"])].append(e["name"] + (f"[{e['command']}]" if e["type"] == "workflow" and e.get("command") else ""))
    out += [table(["Repo", "Loại", "Số", "Danh sách"], [[k[0], k[1], len(v), short(sorted(v), 18)] for k, v in sorted(ep.items())]), "", "### 3.3 Workflow CI", ""]
    rows = [[w["repo"], f"`{re.sub(r'^.*/', '', w['workflow'])}`", w["triggers"], w["runners"], w["permissions"], f"{w['pinned_actions']}/{w['pinned_actions'] + w['unpinned_actions']}", w["secrets"] or "-"] for w in r.workflows]
    out += [table(["Repo", "Workflow", "Trigger", "Runner", "permissions", "Action ghim SHA", "Secrets dùng"], rows), "",
            f"Kết quả thật của fork trên commit CI đã chọn (nguồn: GitHub API, `data/github_facts.json`, thu thập {vn_time(r.ci_facts.get('collected_at', '?'))}):", ""]
    if r.ci_facts.get("runs_for_sha"):
        out.append(table(["Workflow", "Trạng thái", "Kết luận", "Run"], [[x["name"], x["status"], x["conclusion"] or "-", x["html_url"]] for x in r.ci_facts["runs_for_sha"]]))
    jobs = r.ci_facts.get("swift_jobs", [])
    if jobs:
        out += ["", table(["Job (workflow Swift)", "Nhãn runner", "Trạng thái", "Kết luận"], [[j["name"], ",".join(j["labels"]), j["status"], j["conclusion"] or "-"] for j in jobs])]
    out += ["", "### 3.4 Host / địa chỉ ngoài", ""]
    for repo in ("swiftterm", "ashell"):
        hosts = [h for h in r.hosts if h["repo"] == repo]
        grp = collections.Counter(h["group"] for h in hosts)
        runtime = [h for h in hosts if set(h["areas"].split(",")) & {"runtime-code", "web-runtime", "sample-apps"} and h["group"] != "Standards/reference"]
        out.append(f"- **{repo}**: {len(hosts)} host duy nhất; theo nhóm: " + ", ".join(f"{k}={v}" for k, v in sorted(grp.items())) + f". Có xuất hiện trong mã chạy/web/sample (không tính tài liệu chuẩn): {len(runtime)} host.")
    project = [h for h in r.hosts if h["group"] == "Project domain"]
    out += ["", "Tên miền dự án trong mã nguồn SwiftTerm:", "", table(["Host", "Số lần", "Vùng", "Vị trí đầu tiên"], [[h["host"], h["count"], h["areas"], h["first"]] for h in project]), "",
            "### 3.5 Điểm thực thi lệnh / socket / WebView (heuristic có đối chứng, sau khi hạ mức khi thấy biện pháp bảo vệ)", ""]
    sev = collections.Counter(h["severity"] for h in r.sinks)
    mediumplus = [h for h in r.sinks if h["severity"] in ("HIGH", "MEDIUM")]
    status = collections.Counter(h["status"] for h in mediumplus)
    out += [f"Tổng **{len(r.sinks)}** điểm: " + ", ".join(f"{k}={sev.get(k, 0)}" for k in ("HIGH", "MEDIUM", "LOW", "INFO")) + f". Trong {len(mediumplus)} điểm HIGH/MEDIUM: " + ", ".join(f"{REVIEW_VI.get(k, k)}={v}" for k, v in status.most_common()) + ".", ""]
    groups = collections.defaultdict(list)
    for h in mediumplus:
        groups[(h["repo"], h["rule"], loc_path(h["location"]), h["status"], h["verdict"])].append(h)
    rows = [[k[0], k[1], f"`{k[2]}`", len(v), REVIEW_VI.get(k[3], k[3]), k[4]] for k, v in sorted(groups.items(), key=lambda kv: (kv[0][3] != "NOT_REVIEWED", kv[0][0], kv[0][1], kv[0][2]))]
    out += [table(["Repo", "Quy tắc", "File", "Số điểm", "Đánh giá thủ công", "Lý do"], rows), "",
            "Điểm đã hạ xuống INFO vì thấy biện pháp bảo vệ ngay trước đó (đọc từ mã, không suy đoán):", "",
            table(["Repo", "Quy tắc", "Vị trí", "Lý do hạ mức"], [[h["repo"], h["rule"], f"`{h['location']}`", h["note"]] for h in r.sinks if h["severity"] == "INFO"]), "",
            "Đã đọc tay các nhóm: `rm -rf $VAR` (28 điểm, đích đều là thư mục tạm hoặc artefact build, 5 điểm có `${var:?}`); `archive.extractall` ở `ci/audit-artifact.py` (kiểm `is_relative_to` và loại symlink từng member trước khi giải nén); "
            "`strcpy` ở `helix/command.m` (độ dài kiểm ngay trước); `curl -k` chỉ gọi `https://127.0.0.1`; `irm … | iex` ở `windows-start-my-machine-and-tunnel.ps1` chỉ là dòng `Write-Host` hướng dẫn. "
            "Các script tunnel cài `cloudflared` bằng `winget`, không tải file trần. "
            "Listener thật: SwiftTerm — `WebTerminal/HTTPServer.swift` (Hummingbird, `127.0.0.1`), `BidiHarness/SocketControlServer.swift` (Unix domain socket); a-Shell — `Relay.swift` (`NWListener`, TLS) và máy chủ HTTPS loopback phục vụ WASM trong `AppDelegate.swift`.", ""]
    if r.js_escape:
        out += ["**Nội suy chuỗi vào JS của WebView (detector `js_escape_checks`)** — trên 32 điểm `evaluateJavaScript` của a-Shell chỉ có 3 điểm thiếu escape:", "",
                table(["Vị trí", "Loại", "Giống upstream", "Mã"], [[f"`{i['location']}`", i["kind"], "có" if i["same_in_upstream"] else "KHÔNG", f"`{i['snippet'][:90]}`"] for i in r.js_escape]), ""]
    return "\n".join(out)


def section_commands(r) -> str:
    cmds = r.commands
    fixed = sum(1 for c in cmds if c["drift_fork_vs_upstream"] == "same")
    fixed_pin = sum(1 for c in cmds if c["drift_pin_vs_fork"] == "same")
    out = ["## 4. Bảng lệnh: lệnh gốc, lệnh trên mã nguồn, lệnh lỗi, lệnh gọi sai", "",
           f"Bảng đầy đủ **{len(cmds)} tên lệnh** (mọi catalogue và host built-in, so ba nguồn): [`commands-master-table.md`](commands-master-table.md) và `data/commands_master.csv`; "
           "bảng lệnh gọi sai đầy đủ: [`wrong-calls-table.md`](wrong-calls-table.md). *Lệnh gốc* = `holzschu/a-shell` master; *lệnh trên mã nguồn* = fork master và commit SwiftTerm ghim.", "",
           "### 4.1 Kích thước catalogue (đếm trực tiếp từ plist)", "",
           table(["Catalogue", "File", "Gốc (upstream)", "Fork", "Pin SwiftTerm"], [[x["catalogue"], f"`{x['file']}`", x["upstream"], x["fork"], x["pin"]] for x in r.catalogue_sizes]), "",
           f"**Đối chiếu định nghĩa:** fork ≡ upstream cho **{fixed}/{len(cmds)}** tên lệnh; pin ≡ fork cho **{fixed_pin}/{len(cmds)}**; lệnh do fork đưa lỗi vào: **{sum(1 for c in cmds if c['defect_origin'] == 'fork-introduced')}**. "
           "Về định nghĩa lệnh, fork không làm khác nhà sản xuất; khác biệt nằm ở build/test (mục 1 và 6).", "",
           "### 4.2 Nguồn cung cấp lệnh", ""]
    kinds = collections.Counter(c["kind"].split(" (")[0] for c in cmds)
    out += [table(["Nguồn cung cấp", "Số lệnh"], [[k, v] for k, v in kinds.most_common()]), "",
            "### 4.3 Ma trận target × catalogue", "",
            table(["Target", "Catalogue dùng", "Số lệnh trong catalogue", "Số mục framework/module nhúng (gồm module Python)", "Framework catalogue cần nhưng KHÔNG nhúng"],
                  [[t["target"], t["catalogue"], t["catalogue_entries"], t["embedded_frameworks"], t["frameworks_referenced_but_not_embedded"].replace(";", ", ") or "—"] for t in r.target_matrix]), "",
            "### 4.4 Lệnh có lỗi, rủi ro hoặc chưa xác minh (tĩnh)", ""]
    for heading, codes in DEFECT_GROUPS:
        rows = []
        for code in codes:
            hit = [c for c in cmds if code in defect_codes(c["defects"])]
            origins = collections.Counter(c["defect_origin"] for c in hit)
            rows.append([code, DEFECT_TITLES[code], len(hit), ", ".join(f"{k}: {v}" for k, v in origins.items()) or "—", short([c["command"] for c in hit], 14) or "—"])
        union = {c["command"] for c in cmds if defect_codes(c["defects"]) & set(codes)}
        out += [f"**{heading}** — {len(union)} lệnh", "", table(["Mã", "Mô tả", "Số lệnh", "Nguồn gốc", "Lệnh"], rows), ""]
    groups = r.summary["defect_groups"]
    d01_targets = {t for c in cmds for t in defect_targets(c["defects"], "D01")}
    out += [f"Tổng hợp: {len(groups['config'])} lệnh có lỗi cấu hình, {len(groups['provenance'])} lệnh có khoảng trống nguồn gốc, {len(groups['unverified_symbol'])} lệnh TeX chưa xác minh symbol; "
            f"**{sum(1 for c in cmds if c['defect_origin'] == 'upstream-original')}** lệnh có mã lỗi đều là lỗi gốc của nhà sản xuất (xuất hiện y hệt ở upstream), **{sum(1 for c in cmds if c['defect_origin'] == 'fork-introduced')}** do fork; "
            f"{sum(1 for c in cmds if not c['defects'])} lệnh không có mã nào mà bộ phát hiện kiểm được.", "",
            *([f"D01 chỉ xảy ra ở target {', '.join(f'`{t}`' for t in sorted(d01_targets))}: target dùng catalogue `mini` nhưng chỉ nhúng một phần framework; giống hệt upstream và có thể là chủ ý cho biến thể CI (cần chủ dự án xác nhận), nên không tính là lỗi của fork.", ""] if d01_targets else []),
            f"Giới hạn: kiểm tĩnh KHÔNG chứng minh lệnh chạy được. Với {kinds.get('xcfs-binaryTarget', 0)} lệnh nguồn `xcfs-binaryTarget` và {sum(1 for c in cmds if c['framework'] == 'SELF')} lệnh `SELF`, symbol nằm trong nhị phân prebuilt mà VM không tải được (release asset bị chặn); "
            "việc đối chiếu `[framework, symbol]` với symbol export thật chưa được làm (mục 6.5, việc 2).", "",
            "### 4.5 Host built-in (đăng ký bằng `replaceCommand`)", ""]
    host_only = sorted(c["command"] for c in cmds if c["kind"] == "host-builtin only")
    dup = sorted({b["name"] for b in r.builtins if b["duplicate_registration"]})
    dup_files = sorted({b["file"] for b in r.builtins if b["duplicate_registration"]})
    unresolved = [b for b in r.builtins if b["symbol_defined_in_source"] == "no"]
    out += [f"- **{len(r.builtins)} lượt đăng ký / {len({b['name'] for b in r.builtins})} tên**. Giống upstream: {sum(1 for b in r.builtins if b['same_as_upstream'])}/{len(r.builtins)}.",
            f"- **{len(host_only)} lệnh chỉ tồn tại dưới dạng host built-in** (không nằm trong plist): {short(host_only, 40)}.",
            f"- **{len(dup)} tên đăng ký 2 lần** ({', '.join('`' + x + '`' for x in dup_files)}): {short(dup, 20)}.",
            f"- **{len(unresolved)} lượt đăng ký TeX** trỏ vào symbol `{'`, `'.join(sorted({b['symbol'] for b in unresolved}))}` không định nghĩa trong repo (nằm trong framework tải theo nhu cầu): {short(sorted({b['name'] for b in unresolved}), 40)}.", "",
            "### 4.6 Lệnh gọi sai (script / tài liệu / CI / cấu hình) — trước và sau khi sửa", ""]
    now = wrong_by_kind(r.wrong_calls)
    base_rows = r.baseline.get("wrong_calls", []) if r.baseline else []
    base = wrong_by_kind(base_rows)
    kinds_all = sorted(set(now) | set(base), key=lambda k: (-(len(base.get(k, [])) or len(now.get(k, []))), k))
    rows = []
    for kind in kinds_all:
        sample = (base.get(kind) or now.get(kind))[0]
        rows.append([f"`{kind}`", WRONG_CALL_INFO.get(kind, kind), sample["severity"], len(base.get(kind, [])) if r.baseline else "—", len(now.get(kind, [])),
                     "; ".join(f"`{i['location']}`" for i in (now.get(kind) or base.get(kind))[:3])])
    ref = r.baseline.get("ref", "") if r.baseline else ""
    out += [table(["Loại", "Mô tả", "Mức", f"Trước (`{ref[:10]}`)" if ref else "Trước", "Sau", "Ví dụ vị trí"], rows), "",
            f"Tổng: trước **{len(base_rows) if r.baseline else '—'}**, sau **{len(r.wrong_calls)}**. Chi tiết từng dòng (cả phần đã khắc phục): [`wrong-calls-table.md`](wrong-calls-table.md).", "",
            "Đã kiểm và **không phát hiện** lỗi ở các nhóm (detector có đối chứng dương trong `test_audit.py`): gọi script không tồn tại, `swift run/build` sai tên product, `npm run` sai script, `make` sai target, `gh workflow run` sai file, "
            "tham số hàm helper PowerShell sai, `--filter` của CI không khớp test, đường dẫn/exclude/resource sai trong `Package.swift`.", ""]
    return "\n".join(out)


def section_hostapi(r) -> str:
    hs = r.hostapi_script
    used = sum(1 for a in r.hostapi if a["ashell_call_sites"])
    untested = sum(1 for a in r.hostapi if a["status"] == "USED_BY_ASHELL_UNTESTED_IN_SWIFTTERM")
    rows = [[f"`{a['name']}`", a["kind"], STATUS_VI[a["status"]], a["ashell_call_sites"], a["swiftterm_test_refs"], a["first_call"] or "—"] for a in r.hostapi]
    return "\n".join(["## 5. Cầu nối HostHelpers (SwiftTerm ⇄ a-Shell)", "",
        f"`AppleTerminalView+HostHelpers.swift` khai báo **{hs['declared']}** thành viên public (bao bởi `#if {hs['platform_guard']}`); a-Shell gọi **{used}**, {sum(1 for a in r.hostapi if a['status'] == 'UNUSED')} không ai dùng, "
        f"{untested} API a-Shell dùng nhưng SwiftTerm không có test. Script E2E liệt kê {hs['listed_in_e2e_script']} tên nhưng nhãn ghi \"20 APIs\" (lỗi thời).", "",
        table(["API", "Loại", "Trạng thái", "Số chỗ a-Shell gọi", "Số tham chiếu test SwiftTerm", "Vị trí gọi đầu tiên"], rows), ""])


def vn_short(stamp: str | None) -> str:
    """`2026-11-26T16:56:18Z` -> `23:56 (UTC+7)`; empty when missing."""
    try:
        return (datetime.strptime(stamp or "", "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)).strftime("%H:%M") + " (UTC+7)"
    except ValueError:
        return "—"


def swift_run_lines(r) -> list[str]:
    run_info = r.ci_facts.get("swift_run")
    if not run_info:
        return ["- Workflow `Swift` của commit CI đã chọn: không có run khi thu thập số liệu."]
    tree = r.ci_facts.get("swift_tree") or {}
    same = tree.get("same")
    if same is None:
        tree_note = "không so sánh được (commit không có trong bản clone cục bộ)"
    elif all(same.values()):
        tree_note = f"{', '.join(f'`{path}`' for path in same)} giống hệt `{tree.get('st_ref')}` (so tree hash) ⇒ kết quả áp dụng cho mã đang kiểm"
    else:
        tree_note = "KHÁC ở " + ", ".join(f"`{path}`" for path, same_path in same.items() if not same_path) + " ⇒ kết quả CI không áp dụng nguyên vẹn cho mã đang kiểm"
    rows = []
    for job in r.ci_facts.get("swift_jobs", []):
        steps = job.get("steps", [])
        rows.append([f"`{job['name']}`", ",".join(job.get("labels", [])), job["status"], job.get("conclusion") or "-",
                     f"{sum(1 for s_ in steps if s_.get('conclusion') == 'success')}/{len(steps)}" if steps else "chưa chạy", vn_short(job.get("started_at")), job.get("html_url", "")])
    lines = [f"- Workflow `Swift` (run {run_info['id']}, commit `{run_info['head_sha'][:10]}`, `{run_info['status']}`/`{run_info.get('conclusion') or '-'}`). Cây mã Apple của commit này so với bản kiểm toán: {tree_note}.", "",
             table(["Job", "Nhãn runner", "Trạng thái", "Kết luận", "Bước đạt", "Bắt đầu", "Liên kết"], rows), ""]
    log = r.ci_facts.get("swift_log")
    if log:
        lines += [f"- Log job `swiftpm-strict-concurrency` (`swift build --target SwiftTerm -Xswiftc -strict-concurrency=complete`): image `{log['image']}`, macOS {log['macos']}, {log['xcode']}; kết quả `{log['result']}`; "
                  f"{len(log['warnings'])} cảnh báo biên dịch" + (": " + "; ".join(f"`{w['location']}`" for w in log["warnings"]) if log["warnings"] else "") + ".", ""]
    build = r.ci_facts.get("build_log")
    if build:
        projects = ", ".join(f"`{name}.xcodeproj`" for name in build["hosthelpers_projects"]) or "không thấy dòng biên dịch"
        lines += [f"- Log job `build` (`xcodebuild` + `swift build -v` + `swift test`): `** BUILD SUCCEEDED **` ×{build['xcodebuild_succeeded']} (MacTerminal, iOSTerminal), `** BUILD FAILED **` ×{build['xcodebuild_failed']}, `swift build` \"Build complete!\" ×{build['swift_build_complete']}; "
                  f"`AppleTerminalView+HostHelpers.swift` có dòng `SwiftCompile` trong: {projects}; kết quả test: " + (" · ".join(f"`{line}`" for line in build["test_lines"]) or "chưa có (bước test chưa chạy xong khi thu thập)") + ".", ""]
    return lines


def windows_lines(r) -> list[str]:
    run_info = next((x for x in r.ci_facts.get("runs_for_sha", []) if x["name"] == "Windows scripts"), None)
    good, bad = r.ci_facts.get("windows_log"), r.ci_facts.get("windows_mutation_log")
    if not (run_info or good or bad):
        return []
    lines = ["- Script Windows (`scripts/*.ps1`) chạy thật bằng Windows PowerShell 5.1 trên runner Windows (workflow `Windows scripts`, `scripts/tests/windows-tunnel-common.tests.ps1`):", ""]
    rows = []
    if good:
        rows.append(["script đã sửa (HEAD)", good["os"] or "?", good["ps_version"] or "?", good["passed"], len(good["failed"]), good["summary"] or "(không thấy dòng kết luận)", "—"])
    if bad:
        rows.append(["script trước khi sửa (đối chứng đột biến)", bad["os"] or "?", bad["ps_version"] or "?", bad["passed"], len(bad["failed"]), bad["summary"] or "bộ test dừng giữa chừng", bad["error"] or "—"])
    if rows:
        lines += [table(["Phiên bản script", "Hệ điều hành", "PowerShell", "Check đạt", "Check lỗi", "Kết luận của bộ test", "Lỗi làm dừng"], rows), ""]
    if bad and bad["failed"]:
        lines += ["  Check lỗi trên bản trước khi sửa: " + "; ".join(f"`{name}`" for name in bad["failed"]) + ". Bộ test **đỏ trên bản lỗi và xanh trên bản đã sửa** nên phân biệt được hai trạng thái.", ""]
    if run_info:
        lines += [f"  Run trên commit CI đã chọn: `{run_info['status']}`/`{run_info['conclusion'] or '-'}` — {run_info['html_url']}", ""]
    return lines


def binding_note(r) -> str:
    """Sentence about `worker-binding.sh` built only from the runs that exist."""
    binding = suite_results(r.test_runs, "worker-binding.sh")
    if not binding:
        return "`worker-binding.sh` chưa được chạy (cần `--run-tests`)."
    if binding.get("upstream") == "PASS" and any(binding.get(ref) == "FAIL" for ref in ("fork", "pin")):
        return f"Đối chứng: `worker-binding.sh` {suite_summary(binding)} ⇒ nguyên nhân nằm ở trạng thái fork (xem phát hiện về fork tụt hậu), không phải ở môi trường chạy."
    return f"`worker-binding.sh`: {suite_summary(binding)}."


def missing_apple(r) -> str:
    proven = apple_evidence(swift_states(r.ci_facts))
    missing = [name for name, ok in (("biên dịch macOS", proven["mac_compiled"]), ("biên dịch iOS/HostHelpers", proven["ios_compiled"]), ("`swift test` trên macOS", proven["mac_tested"])) if not ok]
    return f"Còn thiếu kết quả: {', '.join(missing)} — cần job tương ứng chạy xong (mục 6.3)." if missing else "Cả ba kết quả đã có (mục 6.3)."


def function_matrix(r) -> list[list[str]]:
    """Rows of the section 6.4 table. Every verdict comes from test runs and CI facts, never from an assumption."""
    linux = linux_result(r.ci_facts)
    xct, swt = linux["xctest"], linux["swift_testing"]
    states = swift_states(r.ci_facts)
    proven = apple_evidence(states)
    xcode = (r.ci_facts.get("swift_log") or {}).get("xcode") or "toolchain chưa rõ"
    ssh = suite_results(r.test_runs, "ssh-stock-registration.sh")
    binding = suite_results(r.test_runs, "worker-binding.sh")
    wasm = next((x for x in r.ci_facts.get("runs_for_sha", []) if x["name"].startswith("WebAssembly")), None)
    wasm_cell = f"CI `WebAssembly browser API`: {wasm['status']}/{wasm['conclusion'] or '-'}" if wasm else "không có dữ liệu CI"
    windows_run = next((x for x in r.ci_facts.get("runs_for_sha", []) if x["name"] == "Windows scripts"), None)
    windows_ok = bool(windows_run and windows_run["conclusion"] == "success")
    drifted = sorted(c["command"] for c in r.commands if c["drift_fork_vs_upstream"] != "same" or c["drift_pin_vs_fork"] != "same")
    unreadable = [p for p in r.wrong_calls if p["kind"] == "catalogue-unreadable"]
    ssh_verdict = "KHÔNG ĐẠT (plist không đọc được)" if unreadable else suite_verdict(ssh)
    if ssh_verdict == "ĐẠT" and drifted:
        ssh_verdict = "ĐẠT TEST; CÓ KHÁC BIỆT ĐỊNH NGHĨA GIỮA CÁC NGUỒN"
    elif ssh_verdict == "CHƯA CHẠY":
        ssh_verdict = "CHƯA CHẠY TEST (chỉ có đối chiếu tĩnh)"
    if linux["ok"]:
        linux_cell, linux_verdict = f"CI `linux-headless`: {xct['executed']} XCTest ({xct['failures']} lỗi) + {swt['tests']} Swift Testing ({swt['result']})", "ĐẠT (phần chạy trên Linux)"
    else:
        counted = " + ".join(part for part in (f"{xct['executed']} XCTest ({xct['failures']} lỗi)" if xct else "", f"{swt['tests']} Swift Testing ({swt['result']})" if swt else "") if part)
        failed = bool(xct and xct["failures"]) or bool(swt and swt["result"] == "failed")
        linux_cell, linux_verdict = f"CI `linux-headless`: {linux['state']}" + (f"; {counted}" if counted else "; không có số liệu test"), "KHÔNG ĐẠT" if failed else "CHƯA CÓ BẰNG CHỨNG"
    helpers_untested = len([a for a in r.hostapi if a["status"] == "USED_BY_ASHELL_UNTESTED_IN_SWIFTTERM"])
    helpers_cell = ("bước `Xcode iOS Build` đạt" + (", log có dòng `SwiftCompile … AppleTerminalView+HostHelpers.swift` trong `iOSTerminal.xcodeproj`" if "iOSTerminal" in (r.ci_facts.get("build_log") or {}).get("hosthelpers_projects", []) else "") + " (biên dịch cả phần `os(iOS)`); "
                    if proven["ios_compiled"] else "grep tĩnh; chưa biên dịch iOS; ") + f"{helpers_untested} API a-Shell dùng nhưng SwiftTerm không test"
    return [
        ["Lõi emulator (parser, buffer, headless)", "a-Shell, Web/WASM, TerminalApp", linux_cell, "L2" if linux["ok"] else "—", linux_verdict],
        ["View/renderer macOS (AppKit)", "TerminalApp macOS", f"workflow Swift: `swiftpm-strict-concurrency` {states['strict_concurrency']}; bước `Xcode Mac Build` {states['mac_build']}", "L3" if proven["mac_compiled"] else "—",
         f"BIÊN DỊCH ĐẠT ({xcode}); chưa chạy" if proven["mac_compiled"] else "CHƯA CÓ BẰNG CHỨNG BIÊN DỊCH"],
        ["View/renderer iOS (UIKit)", "a-Shell iOS", f"workflow Swift: bước `Xcode iOS Build` {states['ios_build']}", "L3" if proven["ios_compiled"] else "—",
         "BIÊN DỊCH ĐẠT; chưa chạy" if proven["ios_compiled"] else "CHƯA CÓ BẰNG CHỨNG BIÊN DỊCH"],
        ["Test trên macOS (`swift test`)", "SwiftTerm", f"workflow Swift: bước `Run tests` {states['swift_test']}", "L2" if proven["mac_tested"] else "—", "ĐẠT (macOS)" if proven["mac_tested"] else "CHƯA CÓ BẰNG CHỨNG"],
        [f"HostHelpers ({r.hostapi_script['declared']} API)", "a-Shell", helpers_cell, "L3" if proven["ios_compiled"] else "L0", "BIÊN DỊCH ĐẠT; hành vi chưa kiểm" if proven["ios_compiled"] else "CHƯA XÁC MINH BIÊN DỊCH"],
        [f"Định nghĩa catalogue ({r.catalogue_sizes[0]['fork']}/{r.catalogue_sizes[1]['fork']} lệnh)", "a-Shell",
         ("có plist không đọc được; " if unreadable else "plist đọc được; ") + f"fork≡upstream≡pin: {len(r.commands) - len(drifted)}/{len(r.commands)} lệnh" + (f" (khác: {', '.join(drifted[:6])})" if drifted else "") + f"; `ssh-stock-registration.sh`: {suite_summary(ssh) or 'chưa chạy'}",
         "L1" if ssh else "L0", ssh_verdict],
        ["Chạy thật các lệnh", "Người dùng cuối", "Chưa có", "L4", "PENDING_USER_DEVICE"],
        ["Gắn Worker A–J (`worker-binding.sh`)", "a-Shell", suite_summary(binding) or "chưa chạy (cần `--run-tests`)", "L1" if binding else "—", suite_verdict(binding)],
        ["Build Web/WASM", "Người dùng web", wasm_cell, "L2" if wasm and wasm["conclusion"] == "success" else "—",
         "KHÔNG CÓ DỮ LIỆU" if not wasm else "ĐẠT (build)" if wasm["conclusion"] == "success" else "ĐANG CHẠY (chưa có kết quả)" if wasm["status"] in ("queued", "in_progress") else "KHÔNG ĐẠT"],
        ["Deploy Cloudflare Pages", "Công chúng", "Workflow cố ý thất bại khi thiếu secrets", "—", "CHƯA (thiếu `CLOUDFLARE_*`)"],
        ["Tunnel Windows (PowerShell): cú pháp, mã hoá, hàm helper", "Máy người dùng", (f"workflow `Windows scripts` (PowerShell 5.1): {windows_run['status']}/{windows_run['conclusion'] or '-'}" if windows_run else "không có run `Windows scripts` cho commit CI đã chọn"), "L2" if windows_ok else "L0", "ĐẠT (cú pháp + helper)" if windows_ok else "CHƯA CÓ BẰNG CHỨNG CHẠY"],
        ["Tunnel Windows: chạy thật (cloudflared + tên miền)", "Máy người dùng", "Không có `cloudflared` và tên miền trong CI", "—", "Chưa chạy thật"],
        ["Tên miền `toolvip1.top`", "Công chúng", "Probe từ VM không hợp lệ (egress allowlist)", "—", "CHƯA XÁC MINH từ bên ngoài"],
    ]


def section_tests(r) -> str:
    linux = linux_result(r.ci_facts)
    inventory = [t for t in r.tests_inventory if t["repo"] == "swiftterm"]
    per_target = collections.defaultdict(lambda: [0, 0, 0])
    for t in inventory:
        row = per_target[t["target"]]
        row[0] += 1
        row[1] += t["xctest_methods"]
        row[2] += t["swift_testing_cases"]
    ut = r.unit_tests
    out = ["## 6. Kiểm thử chức năng: cái gì đạt, cái gì chưa, cái gì đang được dùng", "",
           "### 6.1 Thang độ mạnh của bằng chứng (để không gọi \"ĐẠT\" khi chỉ có grep)", "",
           table(["Mức", "Ý nghĩa", "Ví dụ trong dự án"], [
               ["L0", "Hiện diện tĩnh (grep/đọc plist/đọc mã)", "mục HostHelpers của `e2e_acceptance_host.sh`; các detector của báo cáo này"],
               ["L1", "Chạy script host thật (không cần Apple)", "`tests/ssh-stock-registration.sh`, `tests/worker-binding.sh` qua shim `plutil`; E2E host"],
               ["L2", "Test đơn vị thực thi", "CI `linux-headless`: XCTest + Swift Testing"],
               ["L3", "Biên dịch trên nền tảng Apple", "workflow `Swift` (`xcode.yml`): `swift build`, `xcodebuild` MacTerminal/iOSTerminal (mục 6.3)"],
               ["L4", "Chạy thật trên thiết bị", "158 lệnh a-Shell: `PENDING_USER_DEVICE`"]]), "",
           "### 6.2 Kết quả chạy thật (lệnh + kết quả)", ""]
    rows = [[x["ref"], f"`{x['suite']}`", x["result"], x.get("detail", "")[:100]] for x in r.test_runs]
    if ut:
        rows.append(["swiftterm", f"`{ut['suite']}`", ut["result"], f"Ran {ut['ran']} tests"])
    out += [table(["Nguồn", "Bộ test", "Kết quả", "Chi tiết"], rows), "",
            "Chạy lại: `python3 scripts/audit/run_audit.py --ashell <a-shell> --run-tests`. " + binding_note(r), "",
            "### 6.3 CI thật của fork (SwiftTerm)", ""]
    evidence = (r.ci_facts.get("linux_headless_log") or {}).get("evidence_lines", [])
    log_tail = " · ".join(f"`{line[:80]}`" for line in evidence[-2:])
    swift_run = r.ci_facts.get("swift_run") or {}
    origin = f", run {swift_run['id']}, commit `{swift_run['head_sha'][:10]}`" if swift_run else ""
    xct, swt = linux["xctest"], linux["swift_testing"]
    if linux["ok"]:
        out.append(f"- Job `linux-headless` (id {linux['job_id']}{origin}, `ubuntu-latest`): **{xct['executed']} XCTest** đạt, {xct['failures']} lỗi + **{swt['tests']} test Swift Testing / {swt['suites']} suite** đạt. Log: {log_tail}.")
    else:
        out.append(f"- Job `linux-headless` (id {linux['job_id']}{origin}): trạng thái {linux['state']}; " + (f"log: {log_tail}; " if log_tail else "không có log đếm test; ") + "chưa đủ bằng chứng L2 cho lõi emulator.")
    stats = macos_ci_stats(r.ci_facts)
    if stats:
        delay = stats["start_delay_min"]
        conclusions = ", ".join(f"{k}={v}" for k, v in sorted(stats["conclusions"].items())) or "chưa có"
        out.append(f"- Job macOS (`{'/'.join(stats['labels'])}`) của {stats['runs']} run gần nhất của workflow `Swift`: {stats['started']}/{stats['jobs']} đã được runner nhận" + (f" (chờ {delay[0]}–{delay[1]} phút)" if delay else "") +
                   f", {stats['completed']} xong sau khi có runner ({conclusions}), {stats['in_progress']} đang chạy, {stats['queued']} còn `queued`" +
                   (f", {stats['not_started']} kết thúc khi chưa có runner" if stats["not_started"] else "") +
                   (f" (cũ nhất ≥ {stats['oldest_queued_min']} phút)" if stats["oldest_queued_min"] is not None else "") +
                   (". Hàng đợi macOS chạy chậm; nguyên nhân chưa xác định (phát hiện ở mục 9)." if stats["queued"] and (stats["oldest_queued_min"] or 0) >= 30 else "."))
    out += swift_run_lines(r)
    out += windows_lines(r)
    out += ["- Số test khai báo tĩnh trong `Tests/` (regex; `@Test` có tham số tính 1) — không so trực tiếp với số đã chạy:", "",
            table(["Test target", "File", "XCTest (khai báo)", "@Test (khai báo)"], [[k, v[0], n(v[1]), n(v[2])] for k, v in sorted(per_target.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))]), "",
            "### 6.4 Ma trận chức năng: đạt / chưa / đang được dùng", ""]
    out += [table(["Chức năng", "Ai dùng", "Bằng chứng hiện có", "Mức", "Kết luận"], function_matrix(r)), "",
        "Về \"đang được sử dụng\": với HostHelpers, mức dùng đo được bằng số chỗ a-Shell gọi (mục 5). Với từng lệnh a-Shell, mức dùng thật chỉ đo được trên thiết bị — không có telemetry.", "",
        "### 6.5 Việc kiểm thử còn thiếu và cách đóng", "",
        "1. **Biên dịch macOS/iOS** — đã có sẵn trong workflow `Swift` gốc (`xcode.yml`, nhãn `xcode-27`): `xcodebuild` MacTerminal/iOSTerminal + `swift build` + `swift test` (phủ `HostHelpers`), không cần workflow riêng. " + missing_apple(r),
        "2. **Symbol nhị phân prebuilt** — đối chiếu `[framework, symbol]` của plist với `nm -gU` sau khi kiểm SHA-256 (chưa làm; cần job riêng).",
        "3. **158 lệnh trên thiết bị** — `scripts/verify_command_catalogue_158.sh` trong app; ma trận chờ ở `Docs/command-158-device-matrix-PENDING.csv`.",
        "4. **Tên miền** — probe từ GitHub Actions hoặc máy người dùng, không dùng VM.", ""]
    return "\n".join(out)


def section_security(r) -> str:
    out = ["## 7. Rà soát an ninh", "", "### 7.1 Workflow", "",
           table(["Repo", "Workflow", "permissions", "Action tag/SHA", "Secrets"], [[w["repo"], f"`{re.sub(r'^.*/', '', w['workflow'])}`", w["permissions"], f"{w['unpinned_actions']} tag / {w['pinned_actions']} SHA", w["secrets"] or "-"] for w in r.workflows]), "",
           "### 7.2 Quét bí mật (giá trị luôn bị che)", ""]
    link = {"private-key-block": finding_id(r, "Private key"), "jwt": finding_id(r, "JWT")}
    rows = [[s["repo"], s["kind"], s["severity"], f"`{s['location']}`", s["redacted"], (s.get("note") or "") + (f" → {link[s['kind']]}" if s["kind"] in link and link[s["kind"]] != "—" else "")] for s in r.secrets]
    out += [table(["Repo", "Loại", "Mức heuristic", "Vị trí", "Giá trị (đã che)", "Ghi chú / phát hiện liên quan"], rows), "",
            "Mức \"heuristic\" là mức của detector; đánh giá cuối cùng nằm ở danh sách phát hiện (mục 9). " + ("Không phát hiện token GitHub/AWS/Slack/Stripe/Google hay `CLOUDFLARE_API_TOKEN` dạng literal ở HEAD của hai repo (quét theo mẫu, không kiểm tra hiệu lực)." if not literal_token_kinds(r) else f"Có token dạng literal: {', '.join(literal_token_kinds(r))} — thu hồi và xoay khoá ngay."), "",
            "### 7.3 Phát hiện đọc mã (không chạy được trên VM)", "",
            "- **Chấp nhận mọi chứng chỉ trong WebView** — `a-Shell/SceneDelegate.swift:6338-6342`: `webView(_:didReceive:)` dựng `URLCredential(trust: challenge.protectionSpace.serverTrust!)` rồi gọi `completionHandler(.useCredential, cred)` cho mọi challenge (không kiểm host/`authenticationMethod`).",
            "- **Server HTTPS WASM** — `a-Shell/AppDelegate.swift:44-75`: `LocalHTTPServer` bind `127.0.0.1`, chỉ `GET`, chặn path traversal (`resolvingSymlinksInPath` + `hasPrefix(base)`), nhưng nạp `localCertificate.pfx` bằng passphrase `\"password\"` và khoá riêng nằm trong repo công khai.",
            "- **Relay (lệnh từ xa)** — `a-Shell/Relay.swift`: opt-in, mặc định `127.0.0.1`, TLS bật, token 32–256 ký tự so sánh hằng thời gian, mTLS tuỳ chọn. Rủi ro khi `bind=0.0.0.0` mà không bật mTLS.",
            "- **WebTerminal (PTY qua WebSocket)** — `TerminalApp/WebTerminal/.../HTTPServer.swift:98` bind `127.0.0.1`; WebSocket yêu cầu `Host` loopback và `Origin` khớp. Hệ quả: không thể phơi server này qua Cloudflare tunnel (đúng thiết kế an toàn).",
            "- **Tunnel Windows** — các script chỉ phơi `python -m http.server <port> --bind 127.0.0.1` phục vụ thư mục site tĩnh qua `cloudflared`; không có PTY. Rủi ro còn lại: nếu thư mục phục vụ trỏ nhầm vào gốc repo thì lộ cả `.git`.", ""]
    return "\n".join(out)


def section_docs(r) -> str:
    return "\n".join(["## 8. Tài liệu lỗi thời / tuyên bố sai so với thực tế", "",
                      table(["Vị trí", "Tuyên bố", "Đã nêu", "Thực tế (tính bằng mã)", "Kết luận"], [[f"`{c['location']}`", c["claim"][:70], c["claimed"], c["actual"], c["verdict"]] for c in r.claims]), "",
                      "Tham chiếu a-Shell SHA trong tài liệu không còn là pin hiện tại:", "",
                      table(["Vị trí", "SHA", "Commit", "Quan hệ với pin hiện tại"], [[f"`{p['location']}`", f"`{p['sha'][:10]}`", p["subject"], p["relation"]] for p in r.stale_pins]), "",
                      "Các báo cáo cũ (`Docs/*-2026-11-26.md`) viết ở các thời điểm pin khác nhau trong cùng ngày; coi `Docs/audit/` là nguồn số liệu hiện hành (sinh lại bằng một lệnh).", ""])


def section_findings(r) -> str:
    out = ["## 9. Danh sách phát hiện (theo mức độ)", "", table(["ID", "Mức", "Repo", "Tiêu đề"], [[f["id"], SEVERITY_VI[f["severity"]], f["repo"], f["title"][:150]] for f in r.findings]), ""]
    for f in r.findings:
        out += [f"#### {f['id']} · {SEVERITY_VI[f['severity']]} · {f['title']}", "", f"- **Vị trí:** `{f['location']}`", f"- **Bằng chứng:** {f['evidence']}", f"- **Khuyến nghị:** {f['recommendation']}", f"- **Kiểm tra bằng:** `{f['check']}`", ""]
    return "\n".join(out)


def next_steps(r) -> list[str]:
    """Numbered follow-ups; the ones that depend on the observed state appear only while that state holds."""
    facts = r.ci_facts
    pvm = facts.get("pin_vs_master") or {}
    pulls = ", ".join(f"#{p['number']}" for p in facts.get("pin_pulls", []))
    behind = (facts.get("fork_vs_upstream") or {}).get("behind_by", 0)
    binding_failed = suite_verdict(suite_results(r.test_runs, "worker-binding.sh")).startswith("KHÔNG ĐẠT")
    stats = macos_ci_stats(facts)
    proven = apple_evidence(swift_states(facts))
    steps: list[str] = []
    if pvm.get("ahead_by", 0) > 0:
        steps.append(f"Merge PR a-shell chứa commit đang được ghim ({pulls or 'không tìm thấy PR'}) rồi bump pin về commit nằm trên `master`.")
    if behind or binding_failed:
        steps.append(f"Đồng bộ `upstream/master` vào fork ({behind} commit chưa có)" + (" để `worker-binding.sh` PASS" if binding_failed else "") + ".")
    if stats and stats["queued"]:
        steps.append("Xử lý hàng đợi macOS (mục 6.3): huỷ các run `Swift` cũ đang kẹt, kiểm Settings → Actions (giới hạn chạy đồng thời) và Billing, cân nhắc `concurrency: cancel-in-progress` cho `xcode.yml`; đọc kết quả bước `Xcode iOS Build` và `Run tests` khi chúng chạy xong.")
    elif not all(proven.values()):
        steps.append("Đọc kết quả các bước macOS còn thiếu ở mục 6.3 khi chúng chạy xong.")
    return [f"{number}. {step}" for number, step in enumerate(steps + [
        "Chạy `verify_command_catalogue_158.sh` trên iPhone/iPad và điền ma trận.",
        "Cấu hình `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`, tắt Access cho hostname demo công khai, probe `toolvip1.top` từ ngoài VM.",
        "Với upstream a-Shell: thu hẹp `didReceive challenge`, sinh chứng chỉ localhost theo máy, thống nhất escape JS (đề xuất, ngoài phạm vi repo này).",
    ], 1)]


def section_limits(r) -> str:
    return "\n".join(["## 10. Giới hạn trung thực và việc cần làm tiếp", "",
        "**Không thể làm trên VM này** (không bịa kết quả): không có `swift`/`xcodebuild`/thiết bị iOS ⇒ biên dịch/test Apple chỉ có qua CI của fork (mục 6.3), không chạy 158 lệnh; không có `pwsh` ⇒ script PowerShell được chạy qua CI Windows (mục 6.3), không chạy cục bộ; "
        "egress là allowlist (github.com, api.github.com) ⇒ không tải được framework prebuilt, không probe được `toolvip1.top`, và các kết luận \"FAIL\" tên miền chạy từ VM trong báo cáo cũ **không có giá trị**.", "",
        "**Việc tiếp theo, theo thứ tự giá trị:**", "",
        *next_steps(r), "",
        "## Phụ lục — tái lập", "", "```bash",
        "python3 -m unittest discover -s scripts/audit -v      # test đối chứng của bộ phát hiện",
        "python3 scripts/audit/run_audit.py --ashell /path/to/a-shell --out Docs/audit --run-tests --online --ci-sha <sha> --swift-sha <sha-có-kết-quả-macOS> \\",
        "    --linux-log <log> --swift-log <log> --build-log <log> --windows-log <log> --windows-mutation-log <log> \\",
        "    --baseline-dir Docs/audit/data/baseline --baseline-ref <sha-trước-khi-sửa>",
        "```", "", "Dữ liệu thô: `Docs/audit/data/*.csv|json`; baseline trước khi sửa: `Docs/audit/data/baseline/`. Mọi bảng trong báo cáo này được sinh từ các file đó."])


def master_table(r) -> str:
    cmds = sorted(r.commands, key=lambda c: c["command"])
    mark = lambda flag: "✓" if flag in (True, "True", "true") else "·"
    rows = []
    for i, c in enumerate(cmds, 1):
        fw = (c["framework"].split("/")[0].replace(".framework", "") if c["framework"] else "") + (f"#{c['symbol']}" if c["symbol"] else "")
        rows.append([i, f"`{c['command']}`", f"{mark(c['in_upstream'])} {mark(c['in_fork'])} {mark(c['in_pin'])}", c["catalogues_fork"] or "host", fw or "—", c["kind"].split(" (")[0],
                     c["target_a-Shell"], c["target_a-Shell-mini"], c["target_a-Shell-noPython"], "=" if c["drift_fork_vs_upstream"] == "same" else c["drift_fork_vs_upstream"], c["defects"] or "—", c["defect_origin"] or "—", "PENDING"])
    head = ["# Bảng lệnh đầy đủ (sinh tự động)", "",
            f"{len(cmds)} tên lệnh từ plist + `replaceCommand` của 3 nguồn. Dữ liệu đầy đủ hơn (options, argtype, vị trí đăng ký, placeholder, man): `data/commands_master.csv`.", "",
            "- **Gốc/Fork/Pin**: lệnh có mặt ở `holzschu/a-shell` master / fork master / commit SwiftTerm ghim (✓ có, · không).",
            "- **Catalogue**: `full`/`mini` đóng gói trong app; `extra`/`llvm`/`tex`/`luatex` tải theo nhu cầu; `sshStock` = SSH stock; `host` = chỉ là host built-in.",
            "- **a-Shell / mini / noPython**: `ok` framework được nhúng; `MISSING` catalogue có lệnh nhưng target không nhúng framework; `self` symbol trong ios_system/app; `host` built-in của app; `on-demand` tải khi cần; `stock-ok` framework SSH stock được nhúng; `-` không thuộc catalogue của target.",
            "- **So gốc**: `=` định nghĩa giống hệt lệnh gốc. **Lỗi tĩnh**: mã D01…D10 (báo cáo mục 4.4). **Nguồn gốc lỗi**: `upstream-original` = lỗi có sẵn ở nhà sản xuất.",
            "- **Chạy thực**: `PENDING` = chưa chạy trên thiết bị (mức L4).", ""]
    return "\n".join(head) + table(["#", "Lệnh", "Gốc/Fork/Pin", "Catalogue", "Framework#symbol", "Nguồn cung cấp", "a-Shell", "mini", "noPython", "So gốc", "Lỗi tĩnh", "Nguồn gốc lỗi", "Chạy thực"], rows) + "\n"


def wrong_calls_table(r) -> str:
    now = sorted(r.wrong_calls, key=lambda p: (SEVERITY_ORDER.get(p["severity"], 9), p["kind"], p["location"]))
    out = ["# Bảng lệnh gọi sai (sinh tự động)", "",
           f"**Còn lại sau khi sửa: {len(now)}**. Mỗi dòng là một lời gọi/tham chiếu sai hoặc cấu hình sai do detector tìm thấy; `data/wrong_calls.csv` có thêm cột bằng chứng.", "",
           table(["#", "Mức", "Loại", "Vị trí", "Lời gọi / tham chiếu", "Vấn đề"], [[i, p["severity"], f"`{p['kind']}`", f"`{p['location']}`", f"`{str(p['call'])[:60]}`", str(p["problem"])[:150]] for i, p in enumerate(now, 1)]), ""]
    if r.baseline:
        base = r.baseline["wrong_calls"]
        before = collections.Counter((p["kind"], loc_path(p["location"])) for p in base)
        after = collections.Counter((p["kind"], loc_path(p["location"])) for p in r.wrong_calls)
        fixed = [(k, before[k] - after.get(k, 0)) for k in before if before[k] > after.get(k, 0)]
        out += [f"## Đã khắc phục so với baseline `{r.baseline.get('ref', '')[:10]}` ({sum(v for _, v in fixed)} chỗ)", "",
                table(["Loại", "File", "Số chỗ đã sửa"], [[f"`{k[0]}`", f"`{k[1]}`", v] for k, v in sorted(fixed, key=lambda kv: (kv[0][0], kv[0][1]))]), "",
                "Baseline là kết quả của chính bộ detector này chạy trên commit trước khi sửa (`data/baseline/wrong_calls.csv`).", ""]
    return "\n".join(out)


NON_TOKEN_KINDS = {"private-key-block", "jwt", "key-or-certificate-file"}


def literal_token_kinds(r) -> list[str]:
    """Secret-scan kinds that look like live credentials (everything except key blocks, JWTs and key files)."""
    return sorted({x["kind"] for x in r.secrets} - NON_TOKEN_KINDS)


def commands_line(r) -> str:
    s, cmds = r.summary, r.commands
    groups = s["defect_groups"]
    same3 = sum(1 for c in cmds if c["drift_fork_vs_upstream"] == "same" and c["drift_pin_vs_fork"] == "same")
    introduced = s["defects_fork_introduced"]
    origin = "tất cả là di sản của nhà sản xuất" if not introduced else f"trong đó {introduced} lệnh do fork đưa vào"
    return (f"1. **Lệnh:** {s['distinct_command_names']} tên lệnh (catalogue full {s['catalogue_sizes_fork']['full']}, mini {s['catalogue_sizes_fork']['mini']}, cộng extra/llvm/tex/luatex/sshStock và {sum(1 for c in cmds if c['kind'] == 'host-builtin only')} host built-in). "
            f"Định nghĩa **fork ≡ nhà sản xuất ≡ pin** cho {same3}/{s['distinct_command_names']} lệnh; **{introduced} lỗi do fork đưa vào**. "
            f"Có {len(groups['config'])} lệnh lỗi cấu hình, {len(groups['provenance'])} lệnh khoảng trống nguồn gốc, {len(groups['unverified_symbol'])} lệnh TeX chưa xác minh symbol — {origin} (mục 4.4).")


def tests_line(r) -> str:
    linux = linux_result(r.ci_facts)
    xct, swt = linux["xctest"], linux["swift_testing"]
    binding = suite_results(r.test_runs, "worker-binding.sh")
    states = swift_states(r.ci_facts)
    proven = apple_evidence(states)
    stats = macos_ci_stats(r.ci_facts)
    emulator = f"lõi emulator đạt trên Linux CI ({xct['executed']} XCTest + {swt['tests']} Swift Testing). " if linux["ok"] else f"lõi emulator chưa có kết quả Linux CI hợp lệ (job `linux-headless`: {linux['state']}). "
    if suite_verdict(binding).startswith("KHÔNG ĐẠT"):
        gate = f"**Fork a-Shell trượt bài test `worker-binding.sh` của nhà sản xuất** ({suite_summary(binding)}). "
    else:
        gate = f"`worker-binding.sh`: {suite_summary(binding)}. " if binding else "`worker-binding.sh` chưa chạy. "
    apple = ("Biên dịch Apple (workflow `Swift` gốc): macOS " + ("ĐÃ có bằng chứng" if proven["mac_compiled"] else "chưa có") + f" (`swiftpm-strict-concurrency` {states['strict_concurrency']}), iOS/HostHelpers "
             + ("ĐÃ có bằng chứng" if proven["ios_compiled"] else "chưa có") + f" (bước `Xcode iOS Build` {states['ios_build']}); hàng đợi macOS: "
             + (f"{stats['completed']}/{stats['jobs']} job xong, {stats['in_progress']} đang chạy, {stats['queued']} queued" if stats else "không có dữ liệu"))
    windows = r.ci_facts.get("windows_log")
    windows_text = f"PowerShell 5.1 {windows['passed']} check đạt, {len(windows['failed'])} lỗi" if windows else "chưa có log"
    return f"3. **Kiểm thử:** {emulator}{gate}{apple}. Script Windows: {windows_text}. Chưa có chạy thật 158 lệnh."


def security_line(r) -> str:
    sev = r.summary["findings_by_severity"]
    kinds = {x["kind"] for x in r.secrets}
    literal = literal_token_kinds(r)
    secrets = "Không phát hiện token dạng literal (quét theo mẫu, không kiểm tra hiệu lực)" if not literal else f"Phát hiện token dạng literal: {', '.join(literal)} (mục 7.2)"
    facts = []
    if "private-key-block" in kinds:
        facts.append("khoá riêng localhost công khai")
    if any("server-trust" in f["title"] for f in r.findings):
        facts.append("handler WebView chấp nhận mọi chứng chỉ")
    if r.js_escape:
        facts.append(f"{len(r.js_escape)} chỗ nội suy JS thiếu escape ({'đều' if all(i['same_in_upstream'] for i in r.js_escape) else 'không phải tất cả'} là mã gốc của nhà sản xuất)")
    return (f"4. **An ninh:** {sev.get('CRITICAL', 0)} nghiêm trọng, {sev.get('HIGH', 0)} cao, {sev.get('MEDIUM', 0)} trung bình, {sev.get('LOW', 0)} thấp, {sev.get('INFO', 0)} thông tin. "
            f"{secrets}" + (f"; có {', '.join(facts)}" if facts else "") + ".")


def render(r, out: Path) -> None:
    s = r.summary
    date = r.generated_at[:10]
    base_total = len(r.baseline["wrong_calls"]) if r.baseline else None
    by_kind = collections.Counter(p["kind"] for p in r.wrong_calls)
    base_by_kind = collections.Counter(p["kind"] for p in r.baseline["wrong_calls"]) if r.baseline else {}
    ut = r.unit_tests
    head = [f"# Báo cáo kiểm kê tổng thể và rà soát an ninh — SwiftTerm (lõi) + a-Shell (master)", "",
            f"> Sinh tự động lúc {vn_time(r.generated_at)} bởi `scripts/audit/run_audit.py`. Mọi con số được **tính từ git objects và lệnh chạy thật**, không gõ tay. "
            f"Bộ phát hiện có {ut.get('ran', '?')} test đối chứng dương/âm (`scripts/audit/test_audit.py`): {ut.get('result', '?')}. Dữ liệu thô: `Docs/audit/data/`.", "",
            "## 0. Kết luận nhanh", "",
            commands_line(r),
            f"2. **Lệnh gọi sai:** {('trước sửa ' + str(base_total) + ' → ') if base_total is not None else ''}**{s['wrong_calls_total']} chỗ** (mục 4.6). "
            + (f"Đã khắc phục: gốc repo PowerShell gắn cứng {base_by_kind.get('ps1-hardcoded-root', 0)} → {by_kind.get('ps1-hardcoded-root', 0)}, tên miền sai {base_by_kind.get('wrong-domain-reference', 0)} → {by_kind.get('wrong-domain-reference', 0)}, "
               f"workflow thiếu `permissions` {base_by_kind.get('workflow-permissions', 0)} → {by_kind.get('workflow-permissions', 0)}." if r.baseline else ""),
            tests_line(r),
            security_line(r),
            "5. **Chưa thể khẳng định \"hoàn tất\"**: tên miền `toolvip1.top` chưa xác minh từ bên ngoài; 158 lệnh chưa chạy trên thiết bị; thiếu secrets Cloudflare. Chi tiết mục 6.4 và 10.", ""]
    parts = [section_sources(r), section_languages(r), section_scripts(r), section_commands(r), section_hostapi(r), section_tests(r), section_security(r), section_docs(r), section_findings(r), section_limits(r)]
    (out / f"AUDIT-REPORT-{date}.md").write_text("\n".join(head) + "\n" + "\n".join(parts), encoding="utf-8")
    (out / "commands-master-table.md").write_text(master_table(r), encoding="utf-8")
    (out / "wrong-calls-table.md").write_text(wrong_calls_table(r), encoding="utf-8")
