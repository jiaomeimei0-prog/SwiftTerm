#!/usr/bin/env python3
"""Script inventory and wrong-call detection (missing files, filters, modes, PowerShell)."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field

from audit_lib import GitRepo, TreeEntry, classify, decode

try:  # PyYAML is optional; workflows are still scanned textually without it.
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SCRIPT_LANGUAGES = {"Shell", "Python", "PowerShell", "Batch"}
SKIP_PREFIXES = ("Resources/", "Resources_mini/", "SwiftTerm/", "cpython/", "man/", "node_modules/", "Web/node_modules/")
KNOWN_TOOLS = (
    "curl", "wget", "git", "swift", "xcodebuild", "xcrun", "npm", "npx", "node", "python3", "pip", "cargo", "rustup", "go",
    "brew", "sudo", "docker", "cloudflared", "wrangler", "gh", "jq", "sed", "awk", "tar", "unzip", "openssl", "ssh", "scp",
    "rsync", "plutil", "codesign", "swiftc", "clang", "make", "cmake", "uv", "shasum", "sha256sum", "powershell", "pwsh",
)
REPO_PATH_RE = re.compile(r"(?<![\w$/{}.~-])((?:Docs|scripts|Sources|Tests|Tools|TerminalApp|Web|Apps|Plugins|Benchmarks|\.github|ci|tests|ShellWorkers|Resources|Resources_mini)/[\w./+-]*[\w+-])")
ARTIFACT_RE = re.compile(r"(?:^|/)(?:node_modules|\.build|dist|build|DerivedData|\.swiftpm|pkg)/|^\./configure$|^configure$")
INTERPRETER_RE = re.compile(r"(?:^|[;&|(]\s*|\bthen\s+|\bdo\s+)(?:sudo\s+)?(?:bash|sh|dash|zsh|python3?|node|source|\.|pwsh|powershell(?:\.exe)?(?:\s+-\w+\s+\w+)*(?:\s+-File)?)\s+(?:-[\w-]+\s+)*[\"']?((?:\.{1,2}/)?[\w./+-]+\.(?:sh|py|mjs|js|ps1|cmd|bash))")
DIRECT_RE = re.compile(r"(?:^|[;&|(]\s*)(\./[\w./+-]+|(?:scripts|ci|tests|Tools)/[\w./+-]+\.(?:sh|py|bash))")
MD_LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")


@dataclass
class ScriptInfo:
    repo: str
    path: str
    language: str
    lines: int
    mode: str
    shebang: str
    strict_mode: str
    purpose: str
    tools: list[str]
    referenced_by: list[str] = field(default_factory=list)


@dataclass
class WrongCall:
    kind: str
    repo: str
    location: str
    call: str
    problem: str
    evidence: str
    severity: str = "MEDIUM"


def _purpose(text: str) -> str:
    for line in text.splitlines()[:25]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#!") or stripped.startswith("<#") or stripped in ("#", "'''", '"""'):
            continue
        if stripped.startswith(("#", "//", "REM", "rem", "::")):
            return stripped.lstrip("#/ :").strip()[:140]
        if stripped.startswith(('"""', "'''")):
            return stripped.strip("\"' ")[:140]
        break
    return ""


def _strict(text: str, language: str) -> str:
    if language == "Shell":
        match = re.search(r"^\s*set\s+(-[A-Za-z]*[eu][A-Za-z]*(?:\s+-o\s+pipefail)?)", text, re.M)
        return match.group(0).strip() if match else "none"
    if language == "PowerShell":
        match = re.search(r"\$ErrorActionPreference\s*=\s*['\"]?(\w+)", text)
        return f"ErrorActionPreference={match.group(1)}" if match else "none"
    return "n/a"


def _tools(text: str) -> list[str]:
    found = []
    for tool in KNOWN_TOOLS:
        if re.search(rf"(?:^|[\s;&|(`$]){re.escape(tool)}\s", text, re.M):
            found.append(tool)
    return found


def collect_texts(repo: GitRepo, ref: str, entries: list[TreeEntry]) -> dict[str, str]:
    """All small text blobs outside vendored trees (used for cross references)."""
    texts: dict[str, str] = {}
    with repo.reader() as reader:
        for entry in entries:
            if not entry.is_blob or entry.size > 1_500_000 or entry.path.startswith(SKIP_PREFIXES):
                continue
            data = reader.read(entry.sha)
            if data is None or b"\0" in data[:4000]:
                continue
            texts[entry.path] = decode(data)
    return texts


def inventory(repo_label: str, entries: list[TreeEntry], texts: dict[str, str]) -> list[ScriptInfo]:
    by_path = {e.path: e for e in entries}
    scripts: list[ScriptInfo] = []
    for path, text in texts.items():
        entry = by_path[path]
        language = classify(path, text[:512].encode("utf-8", "replace"))
        is_makefile = path.endswith("Makefile")
        if language not in SCRIPT_LANGUAGES and not is_makefile:
            continue
        first = text.splitlines()[0] if text else ""
        scripts.append(ScriptInfo(
            repo=repo_label, path=path, language="Make" if is_makefile else language, lines=len(text.splitlines()), mode=entry.mode,
            shebang=first if first.startswith("#!") else "", strict_mode=_strict(text, language), purpose=_purpose(text), tools=_tools(text),
        ))
    names = {posixpath.basename(s.path): s for s in scripts if len(posixpath.basename(s.path)) > 6}
    if names:
        pattern = re.compile("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
        for path, text in texts.items():
            for name in set(pattern.findall(text)):
                target = names[name]
                if path != target.path:
                    target.referenced_by.append(path)
    return scripts


def _exists(path: str, tree: set[str], dirs: set[str]) -> bool:
    path = posixpath.normpath(path)
    return path in tree or path in dirs


def _tree_dirs(tree: set[str]) -> set[str]:
    dirs: set[str] = set()
    for path in tree:
        while "/" in path:
            path = path.rsplit("/", 1)[0]
            dirs.add(path)
    return dirs


def script_calls(repo_label: str, texts: dict[str, str], entries: list[TreeEntry]) -> list[WrongCall]:
    """Scripts / workflow steps that call a script that does not exist or cannot be executed."""
    tree = {e.path for e in entries}
    dirs = _tree_dirs(tree)
    modes = {e.path: e.mode for e in entries}
    problems: list[WrongCall] = []
    for path, text in texts.items():
        language = classify(path, text[:512].encode("utf-8", "replace"))
        if language not in SCRIPT_LANGUAGES and not path.startswith(".github/workflows/") and not path.endswith("Makefile"):
            continue
        base = posixpath.dirname(path)
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "REM ", "rem ", "::")):
                continue
            for regex in (INTERPRETER_RE, DIRECT_RE):
                for match in regex.finditer(stripped):
                    target = match.group(1)
                    if "$" in target or "*" in target or target.startswith("/") or ARTIFACT_RE.search(target):
                        continue
                    if re.search(r">>?\s*[\"']?(?:\./)?" + re.escape(target.removeprefix("./")), text):
                        continue
                    candidates = [posixpath.join(base, target), target]
                    resolved = next((posixpath.normpath(c) for c in candidates if _exists(c, tree, dirs)), None)
                    if resolved is None:
                        problems.append(WrongCall("missing-script", repo_label, f"{path}:{number}", target, "called script/file does not exist in the repo at this ref", stripped[:160]))
                    elif regex is DIRECT_RE and resolved in modes and modes[resolved] != "100755":
                        problems.append(WrongCall("not-executable", repo_label, f"{path}:{number}", resolved, f"invoked directly but git mode is {modes[resolved]} (needs 100755)", stripped[:160]))
    return problems


def doc_references(repo_label: str, texts: dict[str, str], entries: list[TreeEntry],
                   extra_trees: dict[str, set[str]] | None = None) -> list[WrongCall]:
    """Markdown links / backticked repo paths that point to files that do not exist.

    `extra_trees` maps a path prefix (e.g. "Apps/a-Shell/") to the file set of the repository
    mounted there, and also supplies fall-back roots for paths written relative to that repo.
    """
    tree = {e.path for e in entries}
    extra_trees = extra_trees or {}
    for prefix, files in extra_trees.items():
        tree |= {prefix + f for f in files}
    fallback = set().union(*extra_trees.values()) if extra_trees else set()
    dirs = _tree_dirs(tree | fallback)
    tree = tree | fallback
    problems: list[WrongCall] = []
    for path, text in texts.items():
        if not path.endswith(".md"):
            continue
        base = posixpath.dirname(path)
        in_fence = False
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            seen: set[str] = set()
            for match in MD_LINK_RE.finditer(line):
                target = match.group(1)
                if re.match(r"^[a-z]+:", target) or target.startswith(("/", "mailto")):
                    continue
                resolved = posixpath.normpath(posixpath.join(base, target))
                if resolved not in seen and not _exists(resolved, tree, dirs):
                    seen.add(resolved)
                    problems.append(WrongCall("broken-doc-link", repo_label, f"{path}:{number}", target, "markdown link target does not exist", line.strip()[:160], "LOW"))
            if in_fence:
                continue
            for tick in BACKTICK_RE.finditer(line):
                for ref in REPO_PATH_RE.findall(tick.group(1)):
                    clean = ref.rstrip(".,:;)")
                    sibling = posixpath.join(base, clean)
                    if any(ch in clean for ch in "*<>{}") or clean in seen or ARTIFACT_RE.search(clean) or _exists(clean, tree, dirs) or _exists(sibling, tree, dirs):
                        continue
                    seen.add(clean)
                    problems.append(WrongCall("broken-doc-path", repo_label, f"{path}:{number}", clean, "path named in docs does not exist at this ref", line.strip()[:160], "LOW"))
    return problems


def workflow_audit(repo_label: str, texts: dict[str, str]) -> tuple[list[dict], list[WrongCall]]:
    """Per-workflow facts (triggers, permissions, pinning, secrets) plus runner/permission problems."""
    rows: list[dict] = []
    problems: list[WrongCall] = []
    for path, text in sorted(texts.items()):
        if not path.startswith(".github/workflows/") or not path.endswith((".yml", ".yaml")):
            continue
        uses = re.findall(r"uses:\s*([^\s#]+)", text)
        unpinned = [u for u in uses if "@" in u and not re.search(r"@[0-9a-f]{40}$", u) and not u.startswith("./")]
        secrets = sorted(set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text)))
        runners = sorted(set(re.findall(r"runs-on:\s*([^\s#]+)", text)))
        triggers: list[str] = []
        if yaml is not None:
            try:
                doc = yaml.safe_load(text)
                on = doc.get(True, doc.get("on")) if isinstance(doc, dict) else None
                triggers = sorted(on) if isinstance(on, dict) else ([on] if isinstance(on, str) else list(on or []))
            except yaml.YAMLError:
                triggers = ["<yaml-parse-error>"]
        top_level = bool(re.search(r"^permissions:", text, re.M))
        job_blocks = re.split(r"^  [A-Za-z0-9_-]+:\s*$", text.split("\njobs:", 1)[1], flags=re.M)[1:] if "\njobs:" in text else []
        jobs_without = [i for i, block in enumerate(job_blocks) if not re.search(r"^    permissions:", block, re.M)]
        has_permissions = top_level or (bool(job_blocks) and not jobs_without)
        rows.append({
            "repo": repo_label, "workflow": path, "triggers": ",".join(map(str, triggers)), "runners": ",".join(runners),
            "permissions": "top-level" if top_level else ("per-job" if has_permissions else "missing"), "unpinned_actions": len(unpinned),
            "pinned_actions": len(uses) - len(unpinned), "secrets": ",".join(secrets),
        })
        if not has_permissions:
            problems.append(WrongCall("workflow-permissions", repo_label, path, "permissions:", "no top-level `permissions:` block (GITHUB_TOKEN gets the repository default)", f"secrets used: {secrets or 'none'}", "LOW"))
        if unpinned:
            problems.append(WrongCall("workflow-unpinned-actions", repo_label, path, ", ".join(sorted(set(unpinned))), "third-party actions referenced by mutable tag instead of commit SHA", f"{len(unpinned)} reference(s)", "LOW"))
        for runner in runners:
            if re.fullmatch(r"xcode-\d+", runner):
                problems.append(WrongCall("ci-runner-never-runs", repo_label, path, f"runs-on: {runner}", "custom runner label that GitHub-hosted runners do not provide: jobs stay queued unless a runner with this label is registered for the repository", "see `gh run list`: jobs queued with no conclusion", "HIGH"))
    return rows, problems


def test_inventory(texts: dict[str, str]) -> tuple[set[str], set[str], dict[str, tuple[int, int]]]:
    """Declared test containers/functions and per-file counts of XCTest methods and Swift Testing cases."""
    containers: set[str] = set()
    functions: set[str] = set()
    per_file: dict[str, tuple[int, int]] = {}
    for path, text in texts.items():
        if not path.startswith("Tests/") or not path.endswith(".swift"):
            continue
        containers.add(path.split("/")[1])
        containers.update(re.findall(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:final\s+|public\s+)*(?:class|struct|enum|actor|extension)\s+(\w+)", text, re.M))
        functions.update(re.findall(r"\bfunc\s+(\w+)\s*\(", text))
        xctest = len(re.findall(r"\bfunc\s+test\w*\s*\(", text))
        swift_testing = len(re.findall(r"^\s*@Test\b", text, re.M))
        per_file[path] = (xctest, swift_testing)
    return containers, functions, per_file


def ci_filters(repo_label: str, texts: dict[str, str], containers: set[str], functions: set[str]) -> list[WrongCall]:
    """`swift test --filter X` patterns in workflows that match no declared test."""
    problems: list[WrongCall] = []
    for path, text in texts.items():
        if not path.startswith(".github/workflows/"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            match = re.search(r"swift test\b.*?--filter\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))", line)
            if not match:
                continue
            expr = next(g for g in match.groups() if g)
            for alt in expr.split("|"):
                try:
                    regex = re.compile(alt)
                except re.error:
                    continue
                if not any(regex.search(name) for name in containers | functions):
                    problems.append(WrongCall("ci-filter-matches-nothing", repo_label, f"{path}:{number}", f"--filter {alt}", "no test class/struct/function name matches this filter", line.strip()[:160], "MEDIUM"))
    return problems


def package_references(repo_label: str, package_text: str, entries: list[TreeEntry]) -> list[WrongCall]:
    """`path:` / `exclude:` / `.copy(...)` literals in Package.swift that point nowhere."""
    tree = {e.path for e in entries}
    dirs = _tree_dirs(tree)
    problems: list[WrongCall] = []
    for match in re.finditer(r"\.(target|testTarget|executableTarget|plugin)\(", package_text):
        start = match.end()
        depth, index = 1, start
        while index < len(package_text) and depth:
            depth += {"(": 1, ")": -1}.get(package_text[index], 0)
            index += 1
        block = package_text[start:index]
        path_match = re.search(r"path:\s*\"([^\"]+)\"", block)
        name = re.search(r"name:\s*\"([^\"]+)\"", block)
        if not path_match:
            continue
        root = path_match.group(1)
        line = package_text.count("\n", 0, match.start()) + 1
        label = f"Package.swift:{line} target {name.group(1) if name else '?'}"
        if not _exists(root, tree, dirs):
            problems.append(WrongCall("package-path-missing", repo_label, label, root, "target `path:` does not exist", block[:120].replace("\n", " "), "HIGH"))
            continue
        for relative in re.findall(r"exclude:\s*(?:\w+\s*\+\s*)?\[(.*?)\]", block, re.S):
            for item in re.findall(r"\"([^\"]+)\"", relative):
                if not _exists(posixpath.join(root, item), tree, dirs):
                    problems.append(WrongCall("package-exclude-missing", repo_label, label, posixpath.join(root, item), "excluded path does not exist (SwiftPM warns)", item, "LOW"))
        for item in re.findall(r"\.(?:copy|process)\(\"([^\"]+)\"\)", block):
            if not _exists(posixpath.join(root, item), tree, dirs):
                problems.append(WrongCall("package-resource-missing", repo_label, label, posixpath.join(root, item), "declared resource does not exist", item, "HIGH"))
    return problems


def powershell_checks(repo_label: str, entries: list[TreeEntry], raw: dict[str, bytes]) -> list[WrongCall]:
    """Windows-only constraints: BOM + ASCII for PowerShell 5.1, hard-coded roots, dot-sourced files."""
    tree = {e.path for e in entries}
    problems: list[WrongCall] = []
    for path, data in raw.items():
        if not path.endswith(".ps1"):
            continue
        text = data.decode("utf-8-sig", "replace")
        base = posixpath.dirname(path)
        if not data.startswith(b"\xef\xbb\xbf"):
            problems.append(WrongCall("ps1-no-bom", repo_label, path, "(file header)", "no UTF-8 BOM: Windows PowerShell 5.1 reads it as ANSI", "first bytes: " + data[:4].hex(), "LOW"))
        non_ascii = [(n, ch) for n, line in enumerate(text.splitlines(), 1) for ch in line if ord(ch) > 127]
        if non_ascii:
            problems.append(WrongCall("ps1-non-ascii", repo_label, f"{path}:{non_ascii[0][0]}", repr(non_ascii[0][1]), f"{len(non_ascii)} non-ASCII char(s); PowerShell 5.1 can mis-parse them", "", "LOW"))
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"Documents\\\\?SwiftTerm", line):
                problems.append(WrongCall("ps1-hardcoded-root", repo_label, f"{path}:{number}", line.strip()[:120], "repo root hard-coded to %USERPROFILE%\\Documents\\SwiftTerm; breaks when the clone lives elsewhere (e.g. C:\\Users\\<user>\\SwiftTerm)", line.strip()[:160], "MEDIUM"))
            dot = re.match(r"\s*\.\s+\(Join-Path \$PSScriptRoot \"([^\"]+)\"\)", line)
            if dot and posixpath.join(base, dot.group(1)) not in tree:
                problems.append(WrongCall("ps1-dot-source-missing", repo_label, f"{path}:{number}", dot.group(1), "dot-sourced helper does not exist", line.strip()[:160], "HIGH"))
    return problems


WRONG_DOMAINS = {"tooltop1.vip": "toolvip1.top"}


def domain_references(repo_label: str, texts: dict[str, str]) -> list[WrongCall]:
    """References to a mistyped project domain; code/config is MEDIUM, prose is LOW. Evidence files are history."""
    problems: list[WrongCall] = []
    for path, text in texts.items():
        if path.startswith(("Docs/evidence/", "Docs/audit/", "scripts/audit/")):
            continue
        is_prose = path.endswith(".md")
        header = "\n".join(text.splitlines()[:15])
        if is_prose and all(domain in header for domain in (*WRONG_DOMAINS, *WRONG_DOMAINS.values())):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for wrong, right in WRONG_DOMAINS.items():
                if wrong in line:
                    problems.append(WrongCall(
                        "wrong-domain-reference", repo_label, f"{path}:{number}", wrong,
                        f"mistyped domain; the real project domain is {right}", line.strip()[:160], "LOW" if is_prose else "MEDIUM"))
    return problems
