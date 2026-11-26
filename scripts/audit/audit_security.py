#!/usr/bin/env python3
"""Static security inventory: outbound hosts, command-execution sinks, listeners and secret scan.

Every value that looks like a credential is redacted in the output (prefix + length only).
"""
from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass, field

from audit_lib import TreeEntry, classify

URL_RE = re.compile(r"\b((?:https?|wss?|ssh|git|ftp)://[A-Za-z0-9._~:@%\-]+(?::\d+)?(?:/[^\s\"'<>)\]\\`,;]*)?)")
HOST_OF_RE = re.compile(r"^[a-z]+://(?:[^@/]+@)?([^/:]+)(?::(\d+))?")
BARE_DOMAIN_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:top|vip|dev|io|app|com|net|org))\b", re.I)
IGNORED_HOSTS = {"www.w3.org", "www.apple.com", "schemas.microsoft.com", "json-schema.org", "example.com", "example.org", "localhost", "127.0.0.1", "0.0.0.0", "::1"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

HOST_GROUPS = (
    (re.compile(r"(^|\.)github(usercontent)?\.com$|(^|\.)githubassets\.com$|(^|\.)ghcr\.io$"), "GitHub"),
    (re.compile(r"(^|\.)apple\.com$|(^|\.)swift\.org$|(^|\.)developer\.apple\.com$"), "Apple/Swift"),
    (re.compile(r"(^|\.)cloudflare\.com$|(^|\.)trycloudflare\.com$|(^|\.)pages\.dev$|(^|\.)workers\.dev$|(^|\.)cloudflarestorage\.com$"), "Cloudflare"),
    (re.compile(r"(^|\.)npmjs\.(org|com)$|(^|\.)unpkg\.com$|(^|\.)jsdelivr\.net$|(^|\.)nodejs\.org$"), "JS registries"),
    (re.compile(r"(^|\.)toolvip1\.top$|(^|\.)tooltop1\.vip$"), "Project domain"),
    (re.compile(r"(^|\.)sonarcloud\.io$|(^|\.)sonarsource\.com$"), "SonarCloud"),
    (re.compile(r"(^|\.)unicode\.org$|(^|\.)invisible-island\.net$|(^|\.)vt100\.net$|(^|\.)xfree86\.org$|(^|\.)x\.org$|(^|\.)gnu\.org$"), "Standards/reference"),
    (re.compile(r"(^|\.)crates\.io$|(^|\.)rust-lang\.org$|(^|\.)golang\.org$|(^|\.)go\.dev$|(^|\.)pypi\.org$|(^|\.)python\.org$|(^|\.)ctan\.org$"), "Package ecosystems"),
)

SECRET_PATTERNS = (
    ("private-key-block", "CRITICAL", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("aws-access-key-id", "HIGH", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", "CRITICAL", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("slack-token", "HIGH", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", "MEDIUM", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-live-key", "HIGH", re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b")),
    ("jwt", "MEDIUM", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("cloudflare-token-literal", "HIGH", re.compile(r"CLOUDFLARE_API_TOKEN\s*[=:]\s*['\"]?(?!\$|\{|<|YOUR|xxx|\*)[A-Za-z0-9_-]{30,}")),
    ("hardcoded-credential", "MEDIUM", re.compile(r"(?i)\b(?:api[_-]?key|secret|passwd|password|auth[_-]?token)\b\s*[:=]\s*[\"'](?!\$|\{|<|%|YOUR|xxx|\*+|changeme|example|password|secret|test)[^\"'\s]{14,}[\"']")),
)
SECRET_PATH_SKIP = re.compile(r"^scripts/audit/|(^|/)(Fixtures?|fixtures?|testdata|esctest|Tests/.*/Resources)/|\.(png|jpg|gif|ico|ttf|otf|woff2?|svg|pdf|plist|strings|xcscheme)$")
CERT_FILE_RE = re.compile(r"\.(pem|key|pfx|p12|p8|cer|crt|mobileprovision|keystore|jks)$", re.I)

@dataclass(frozen=True)
class SinkRule:
    """One heuristic. `veto` drops a known false positive on the same line; `guard` downgrades the hit to INFO
    when the mitigation is visible on the same line or in the preceding `lookback` lines."""

    language: str
    name: str
    severity: str
    pattern: re.Pattern
    veto: re.Pattern | None = None
    guard: re.Pattern | None = None
    lookback: int = 0
    guard_note: str = ""


def _r(language, name, severity, pattern, veto=None, guard=None, lookback=0, note=""):
    return SinkRule(language, name, severity, re.compile(pattern), re.compile(veto) if veto else None, re.compile(guard) if guard else None, lookback, note)


PS_PRINT = r"(?i)^\s*(?:Write-Host|Write-Output|Write-Warning|Write-Verbose|Write-Information|echo)\b"
LOOPBACK_URL = r"https?://(?:127\.0\.0\.1|localhost|\[::1\])"
SINK_RULES = (
    _r("Swift", "process-spawn", "MEDIUM", r"\b(?:posix_spawn|forkpty|execv[pe]?|execl[pe]?|fork\(\)|NSTask|Process\(\)|ios_system\(|ios_popen\(|ios_execv)"),
    _r("Swift", "dynamic-symbol", "MEDIUM", r"\bdlsym\(|\bdlopen\("),
    _r("Swift", "js-eval-in-webview", "MEDIUM", r"evaluateJavaScript\(|\.userScripts|addUserScript\(|loadHTMLString\(|WKScriptMessageHandler"),
    _r("Swift", "network-listener", "MEDIUM", r"\bNWListener\s*\(|\bDarwin\.listen\(|(?<![\w.])listen\(\s*\w+\s*,|\baddress:\s*\.hostname\(|\bServerBootstrap\b",
       guard=r"127\.0\.0\.1|\"localhost\"|AF_UNIX|sockaddr_un", lookback=40, note="listener chỉ loopback hoặc Unix domain socket"),
    _r("Swift", "wildcard-bind", "HIGH", r"INADDR_ANY|in6addr_any|\.hostname\(\s*\"(?:0\.0\.0\.0|::)\""),
    _r("Swift", "tls-trust-bypass", "HIGH", r"serverTrust|NSAllowsArbitraryLoads|didReceive challenge|\.useCredential"),
    _r("Swift", "unsafe-url-open", "LOW", r"UIApplication\.shared\.open\(|NSWorkspace\.shared\.open\("),
    _r("Swift", "keychain-or-defaults-secret", "LOW", r"SecItem(?:Add|CopyMatching)|kSecClass"),
    _r("Objective-C/C", "process-spawn", "MEDIUM", r"\b(?:posix_spawn|execv[pe]?|system\(|popen\(|fork\(\))"),
    _r("Objective-C/C", "unsafe-string", "MEDIUM", r"\b(?:strcpy|strcat|sprintf|gets)\(",
       guard=r"sizeof\(|strlen\(|strnlen\(|snprintf\(", lookback=4, note="độ dài đã được kiểm ngay trước đó"),
    _r("Shell", "curl-pipe-shell", "HIGH", r"(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"),
    _r("Shell", "eval", "MEDIUM", r"^\s*eval\s"),
    _r("Shell", "sudo", "LOW", r"^\s*sudo\s"),
    _r("Shell", "insecure-tls", "HIGH", r"--insecure|--no-check-certificate|\bcurl\b[^\n]*\s-k\b",
       guard=LOOPBACK_URL, note="chỉ gọi loopback (chứng chỉ tự ký)"),
    _r("Shell", "rm-rf-variable", "LOW", r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+[\"']?\$\{?\w+",
       guard=r"\$\{\w+:\?", note="biến có bảo vệ ${var:?}"),
    _r("Shell", "chmod-world-writable", "MEDIUM", r"chmod\s+(?:-R\s+)?(?:0?777|a\+w|o\+w)"),
    _r("PowerShell", "invoke-expression", "HIGH", r"(?i)\bInvoke-Expression\b|\biex\b\s*[\(\$]|\|\s*iex\b", veto=PS_PRINT),
    _r("PowerShell", "execution-policy-bypass", "MEDIUM", r"(?i)-ExecutionPolicy\s+Bypass|Set-ExecutionPolicy"),
    _r("PowerShell", "elevation", "MEDIUM", r"(?i)-Verb\s+RunAs|RunAsAdministrator"),
    _r("PowerShell", "persistence", "MEDIUM", r"(?i)Register-ScheduledTask|New-Service|schtasks|HKLM:|\\Run\\"),
    _r("PowerShell", "download-exec", "MEDIUM",
       r"(?i)\b(?:Invoke-WebRequest|Invoke-RestMethod|iwr|irm|Start-BitsTransfer)\b[^\n]*(?:-OutFile\b|\|\s*(?:iex|Invoke-Expression)\b)|\.DownloadFile\(|\.DownloadString\(", veto=PS_PRINT),
    _r("PowerShell", "firewall", "LOW", r"(?i)New-NetFirewallRule|netsh\s+advfirewall"),
    _r("Python", "shell-true", "HIGH", r"shell\s*=\s*True"),
    _r("Python", "os-system", "MEDIUM", r"\bos\.(?:system|popen)\("),
    _r("Python", "eval-exec", "HIGH", r"(?<![\w.])(?:eval|exec)\("),
    _r("Python", "unsafe-deserialise", "HIGH", r"\bpickle\.loads?\(|yaml\.load\((?!.*Loader)|marshal\.loads?\("),
    _r("Python", "archive-extractall", "MEDIUM", r"\.extractall\(",
       guard=r"is_relative_to|commonpath|\.resolve\(\)|realpath|filter\s*=", lookback=25, note="từng member được kiểm đường dẫn trước khi giải nén"),
    _r("Python", "tls-verify-off", "HIGH", r"verify\s*=\s*False|_create_unverified_context"),
    _r("Python", "subprocess", "LOW", r"\bsubprocess\.(?:run|Popen|call|check_output|check_call)\("),
    _r("JavaScript", "eval", "HIGH", r"(?<![\w.])eval\(|new Function\("),
    _r("JavaScript", "dom-injection", "MEDIUM", r"\.innerHTML\s*=|\.outerHTML\s*=|document\.write\(|insertAdjacentHTML\("),
    _r("JavaScript", "child-process", "MEDIUM", r"child_process|\bexecSync\(|\bspawnSync\(|\bexecFileSync\("),
    _r("JavaScript", "tls-verify-off", "HIGH", r"NODE_TLS_REJECT_UNAUTHORIZED|rejectUnauthorized\s*:\s*false"),
    _r("JavaScript", "postmessage-wildcard", "MEDIUM", r"postMessage\([^)]*,\s*[\"']\*[\"']\)"),
    _r("JavaScript", "websocket-open", "LOW", r"new WebSocket\("),
    _r("JavaScript", "http-listener", "MEDIUM", r"(?i)\b\w*(?:server|app|srv)\w*\.listen\(", guard=r"127\.0\.0\.1|localhost", note="listener chỉ loopback"),
    _r("TypeScript", "eval", "HIGH", r"(?<![\w.])eval\(|new Function\("),
    _r("TypeScript", "dom-injection", "MEDIUM", r"\.innerHTML\s*=|\.outerHTML\s*=|document\.write\(|insertAdjacentHTML\("),
    _r("TypeScript", "websocket-open", "LOW", r"new WebSocket\("),
    _r("TypeScript", "postmessage-wildcard", "MEDIUM", r"postMessage\([^)]*,\s*[\"']\*[\"']\)"),
)
LANGUAGE_ALIASES = {"Objective-C": "Objective-C/C", "C": "Objective-C/C", "C++": "Objective-C/C", "Objective-C++": "Objective-C/C"}


@dataclass
class HostRecord:
    repo: str
    host: str
    group: str
    schemes: set[str] = field(default_factory=set)
    count: int = 0
    areas: set[str] = field(default_factory=set)
    first: str = ""
    sample: str = ""


@dataclass
class SinkHit:
    repo: str
    language: str
    rule: str
    severity: str
    location: str
    area: str
    snippet: str
    note: str = ""
    status: str = ""
    verdict: str = ""


@dataclass
class SecretHit:
    repo: str
    kind: str
    severity: str
    location: str
    redacted: str
    note: str = ""


def host_group(host: str) -> str:
    for regex, name in HOST_GROUPS:
        if regex.search(host):
            return name
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return "IP literal"
    return "Other"


def path_area(path: str) -> str:
    if path.startswith("Docs/evidence/") or path.startswith("Docs/audit/"):
        return "docs-evidence"
    if path.endswith(".md") or path.startswith(("Docs/", "docs/")):
        return "documentation"
    if path.startswith((".github/", "scripts/", "ci/", "Tools/", "tests/")) or path.endswith(("Makefile", ".sh", ".ps1", ".cmd")):
        return "ci-dev-tooling"
    if path.startswith("Tests/") or "/Tests/" in path:
        return "tests"
    if path.startswith(("Web/", "web/")):
        return "web-runtime"
    if path.startswith("TerminalApp/") or path.startswith("Apps/"):
        return "sample-apps"
    return "runtime-code"


def redact(value: str) -> str:
    value = value.strip()
    return f"{value[:4]}...(len={len(value)})" if len(value) > 8 else "***"


def host_inventory(repo_label: str, texts: dict[str, str]) -> list[HostRecord]:
    records: dict[str, HostRecord] = {}
    for path, text in texts.items():
        area = path_area(path)
        for number, line in enumerate(text.splitlines(), 1):
            for url in URL_RE.findall(line):
                match = HOST_OF_RE.match(url)
                if not match:
                    continue
                host = match.group(1).lower().rstrip(".")
                if host in IGNORED_HOSTS or "." not in host and host not in LOCAL_HOSTS or host.endswith((".local", ".example")) or "$" in host or "{" in host:
                    continue
                record = records.setdefault(host, HostRecord(repo_label, host, host_group(host)))
                record.count += 1
                record.schemes.add(url.split(":", 1)[0])
                record.areas.add(area)
                if not record.first or (area in ("runtime-code", "web-runtime") and not record.first.startswith(("Sources", "Web"))):
                    record.first = f"{path}:{number}"
                    record.sample = url[:120]
            for domain in BARE_DOMAIN_RE.findall(line):
                domain = domain.lower()
                if host_group(domain) == "Project domain":
                    record = records.setdefault(domain, HostRecord(repo_label, domain, "Project domain"))
                    record.count += 1
                    record.areas.add(area)
                    record.first = record.first or f"{path}:{number}"
    return sorted(records.values(), key=lambda r: (r.group, r.host))


# Manual review decisions, keyed by (rule, path regex). Anything MEDIUM or above without a match stays NOT_REVIEWED.
REVIEWED = (
    ("tls-trust-bypass", r"^a-Shell/SceneDelegate\.swift$", "FINDING", "xem phát hiện về handler chấp nhận mọi server-trust"),
    ("network-listener", r"^a-Shell/Relay\.swift$", "BY_DESIGN", "Relay: opt-in, mặc định 127.0.0.1, TLS bắt buộc, token 32-256 ký tự, mTLS tuỳ chọn"),
    ("process-spawn", r"^a-Shell/Relay\.swift$", "BY_DESIGN", "Relay thực thi lệnh nhận qua TLS + token"),
    ("process-spawn", r"^a-Shell(-Intents|-LongCommands)?/", "BY_DESIGN", "đường thực thi lệnh cốt lõi của a-Shell (ios_system, Shortcuts intent)"),
    ("process-spawn", r"^Sources/SwiftTerm/Pty\.swift$", "BY_DESIGN", "LocalProcess: forkpty/execve chạy shell do app nhúng chỉ định"),
    ("process-spawn", r"^Sources/SwiftTermBuildInfoGenerator/", "BY_DESIGN", "công cụ build: chạy git với tham số cố định (-C <repo>)"),
    ("dynamic-symbol", r"^a-Shell/AppDelegate\.swift$", "BY_DESIGN", "dò khả năng: dlsym(..., \"ios_posix_spawn\") != nil"),
    ("eval", r"^require(_jscore)?\.js$", "BY_DESIGN", "bộ nạp module CommonJS: new Function bọc mã module trong bộ nhớ đệm của app"),
    ("dom-injection", r"^hterm_all\.js$", "THIRD_PARTY", "thư viện hterm đóng gói sẵn"),
    ("child-process", r"^(node/child-process-test\.cjs|Tests/WebWasmTests/corpus\.test\.mjs)$", "TEST_ONLY", "mã kiểm thử"),
    ("js-eval-in-webview", r"^Tools/BidiHarness/", "DEV_TOOL", "harness phát triển, không phát hành"),
)
REVIEWED_COMPILED = tuple((rule, re.compile(pattern), status, text) for rule, pattern, status, text in REVIEWED)


def review(hit: "SinkHit") -> tuple[str, str]:
    if hit.severity not in ("HIGH", "MEDIUM"):
        return "", ""
    path = hit.location.rsplit(":", 1)[0]
    for rule, pattern, status, text in REVIEWED_COMPILED:
        if rule == hit.rule and pattern.search(path):
            return status, text
    return "NOT_REVIEWED", ""


JS_ESCAPE_HELPERS = re.compile(r"replacingOccurrences\(of:\s*\"'\"|base64EncodedString|JSONSerialization|JSONEncoder|addingPercentEncoding|jsonString|escapeJS|jsEscaped")


def js_escape_checks(texts: dict[str, str]) -> list[dict]:
    """evaluateJavaScript calls that interpolate Swift values into a JS literal without (complete) escaping."""
    found: list[dict] = []
    for path, text in sorted(texts.items()):
        if not path.endswith(".swift"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if "evaluateJavaScript(" not in line:
                continue
            if "\\(" in line and not JS_ESCAPE_HELPERS.search(line):
                found.append({"kind": "js-interpolation-unescaped", "location": f"{path}:{number}", "snippet": line.strip()[:160]})
            elif 'replacingOccurrences(of: "\\\\"' in line and 'of: "\\""' not in line and '\\"' in line.split("evaluateJavaScript(", 1)[1][:60]:
                found.append({"kind": "js-escape-missing-quote", "location": f"{path}:{number}", "snippet": line.strip()[:160]})
    return found


def scan_sinks(path: str, text: str, language: str, repo_label: str = "") -> list[SinkHit]:
    rules = [r for r in SINK_RULES if r.language == language]
    if not rules:
        return []
    area = path_area(path)
    lines = text.splitlines()
    hits: list[SinkHit] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*", "/*")) and not stripped.startswith("#!"):
            continue
        for rule in rules:
            if not rule.pattern.search(line) or (rule.veto and rule.veto.search(line)):
                continue
            severity, note = rule.severity, ""
            if rule.guard:
                window = "\n".join(lines[max(0, index - rule.lookback): index + 1])
                if rule.guard.search(window):
                    severity, note = "INFO", rule.guard_note
            hits.append(SinkHit(repo_label, language, rule.name, severity, f"{path}:{index + 1}", area, stripped[:140], note))
    return hits


def sink_inventory(repo_label: str, texts: dict[str, str], entries: list[TreeEntry]) -> list[SinkHit]:
    hits: list[SinkHit] = []
    for path, text in texts.items():
        if path.startswith(("Resources/", "Resources_mini/")):
            continue
        language = classify(path, text[:512].encode("utf-8", "replace"))
        language = LANGUAGE_ALIASES.get(language, language)
        hits.extend(scan_sinks(path, text, language, repo_label))
    for hit in hits:
        hit.status, hit.verdict = review(hit)
    return hits


def secret_scan(repo_label: str, texts: dict[str, str], entries: list[TreeEntry]) -> list[SecretHit]:
    hits: list[SecretHit] = []
    for path, text in texts.items():
        if SECRET_PATH_SKIP.search(path):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, severity, regex in SECRET_PATTERNS:
                match = regex.search(line)
                if match:
                    hits.append(SecretHit(repo_label, kind, severity, f"{path}:{number}", redact(match.group(0)) if kind != "private-key-block" else "PRIVATE KEY block header"))
    for entry in entries:
        if entry.is_blob and CERT_FILE_RE.search(entry.path) and not entry.path.startswith(("Resources/", "Resources_mini/", "Tests/")):
            hits.append(SecretHit(repo_label, "key-or-certificate-file", "INFO", entry.path, f"{entry.size} bytes", "tracked key/cert material; verify purpose and key type"))
    return hits


def listener_summary(sinks: list[SinkHit]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for hit in sinks:
        if hit.rule in ("network-listener", "http-listener"):
            summary[hit.area] += 1
    return dict(summary)


def group_counts(records: list[HostRecord]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[record.group] += 1
    return dict(counts)


def posix_dir(path: str) -> str:
    return posixpath.dirname(path)
