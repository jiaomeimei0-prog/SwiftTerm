"""Shared helpers for the repository audit tools (standard library only)."""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


class GitError(RuntimeError):
    """A git command failed."""


# The audit's own code and generated reports quote other repositories' scripts, workflow names and
# mistyped domains on purpose (fixtures, evidence). Wrong-call detectors must not judge them.
SELF_AUDIT_PREFIXES = ("scripts/audit/", "Docs/audit/")


def minutes_between(start: str, end: str) -> int | None:
    """Whole minutes from `start` to `end` (both GitHub `...Z` timestamps), or None if either is missing."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return int((datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds() // 60)
    except ValueError:
        return None


def _is_macos(job: dict) -> bool:
    return any(label.startswith(("xcode-", "macos")) for label in job.get("labels", []))


def macos_ci_stats(facts: dict) -> dict | None:
    """Queue statistics of the macOS jobs over the recent runs of the `Swift` workflow (GitHub facts)."""
    runs = facts.get("swift_recent") or []
    all_jobs = [job for run in runs for job in run.get("jobs", [])]
    macos = [job for job in all_jobs if _is_macos(job)]
    if not macos:
        return None
    queued = [job for job in macos if job.get("status") == "queued"]
    started = [job for job in macos if job.get("runner_name")]
    delays = [m for m in (minutes_between(job.get("created_at", ""), job.get("started_at", "")) for job in started) if m is not None]
    ubuntu_delays = [m for m in (minutes_between(job.get("created_at", ""), job.get("started_at", "")) for job in all_jobs if job.get("runner_name") and not _is_macos(job)) if m is not None]
    # A job GitHub marks completed without ever assigning a runner (cancelled or skipped while queued)
    # did not run. Counting it as finished made `in_progress` negative and hid a queue that never moved.
    finished = [job for job in macos if job.get("status") == "completed" and job.get("runner_name")]
    not_started = [job for job in macos if job.get("status") == "completed" and not job.get("runner_name")]
    return {
        "runs": len(runs), "jobs": len(macos), "queued": len(queued), "started": len(started),
        "completed": len(finished), "in_progress": sum(1 for job in macos if job.get("status") == "in_progress"),
        "not_started": len(not_started),
        "conclusions": dict(collections.Counter(job.get("conclusion") or "-" for job in finished)),
        "oldest_queued_min": minutes_between(min((job["created_at"] for job in queued if job.get("created_at")), default=""), facts.get("collected_at", "")),
        "start_delay_min": (min(delays), max(delays)) if delays else None,
        "ubuntu_max_delay_min": max(ubuntu_delays) if ubuntu_delays else None,
        "labels": sorted({label for job in macos for label in job.get("labels", [])}),
    }


HARNESS_CHECK_RE = re.compile(r"(?:bom|ascii-only|parse|no Documents-based|root|SWIFTTERM_ROOT|Refresh-Path|Test-CanBindPort|Select-ListenPort|ingress yaml)\b|public host:")


def summarise_ps_log(text: str) -> dict:
    """Facts from the output of scripts/tests/windows-tunnel-common.tests.ps1 captured in a GitHub Actions job log.

    Only lines printed by the test harness count: the helper under test prints its own PASS/FAIL words.
    """
    passed, failed = 0, []
    summary = ps_version = os_name = error = ""
    for raw in text.splitlines():
        line = re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", raw).strip()
        if line.startswith(("PASS ", "FAIL ")) and HARNESS_CHECK_RE.match(line[5:]):
            if line.startswith("PASS "):
                passed += 1
            else:
                failed.append(line[5:].strip())
        elif line == "ALL PASSED" or re.fullmatch(r"\d+ FAILED", line):
            summary = line
        elif line.startswith("PSVersion"):
            ps_version = line.split()[-1]
        elif line.startswith("Microsoft Windows"):
            os_name = line
        elif not error and "is not recognized as the name of a cmdlet" in line:
            error = line[:140]
    return {"passed": passed, "failed": failed, "summary": summary, "ps_version": ps_version, "os": os_name, "error": error}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SWIFT_WARNING_RE = re.compile(r"^/\S+?/SwiftTerm/SwiftTerm/(?P<loc>\S+\.swift:\d+:\d+): warning: (?P<msg>.*?)(?: \[#|\x1b|\]8;;|$)")


def summarise_swift_log(text: str) -> dict:
    """Toolchain and compile facts from the log of a macOS `swift build` job (GitHub Actions)."""
    lines = [ANSI_RE.sub("", re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", raw)).rstrip() for raw in text.splitlines()]
    facts: dict = {"image": "", "macos": "", "xcode": "", "result": "", "warnings": []}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        if line.startswith("Image: ") and not facts["image"]:
            facts["image"] = line[7:].strip()
        elif line.strip() == "##[group]Operating System" and index + 3 < len(lines):
            facts["macos"] = f"{lines[index + 2].strip()} (build {lines[index + 3].strip()})"
        elif "DEVELOPER_DIR:" in line and not facts["xcode"]:
            found = re.search(r"Xcode_([\d.]+)\.app", line)
            facts["xcode"] = f"Xcode {found.group(1)}" if found else ""
        elif not facts["result"] and (line.startswith("Build complete!") or ": error:" in line):
            facts["result"] = line.strip()[:120]
        match = SWIFT_WARNING_RE.match(line)
        if match and match["loc"] not in seen:
            seen.add(match["loc"])
            facts["warnings"].append({"location": match["loc"], "message": match["msg"].strip()})
    return facts


HOSTHELPERS_COMPILE_RE = re.compile(r"^SwiftCompile normal \w+ \S*AppleTerminalView\+HostHelpers\.swift \(in target 'SwiftTerm'")
PROJECT_RE = re.compile(r"(?:-project\s+|^\s*cd\s+)\S*?/([\w+-]+)\.xcodeproj\b")
TEST_RESULT_RE = re.compile(r"Executed \d+ tests?, with \d+ failures|Test run with \d+ tests?")


def summarise_build_log(text: str) -> dict:
    """Facts from the log of the macOS `build` job: xcodebuild results, where HostHelpers was compiled, test totals."""
    lines = [ANSI_RE.sub("", re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", raw)).rstrip() for raw in text.splitlines()]
    facts: dict = {"xcodebuild_succeeded": 0, "xcodebuild_failed": 0, "swift_build_complete": 0, "hosthelpers_projects": [], "test_lines": []}
    current_project = ""
    for index, line in enumerate(lines):
        named = PROJECT_RE.search(line)
        if named:
            current_project = named.group(1)
        if line.startswith("** BUILD SUCCEEDED **"):
            facts["xcodebuild_succeeded"] += 1
        elif line.startswith("** BUILD FAILED **"):
            facts["xcodebuild_failed"] += 1
        elif line.startswith("Build complete!"):
            facts["swift_build_complete"] += 1
        elif HOSTHELPERS_COMPILE_RE.match(line):
            # The compile line names the Swift package ('SwiftTerm'), not the app. The following `cd` usually
            # names the .xcodeproj; when xcodebuild instead cds to the shared SRCROOT, the `xcodebuild -project`
            # line that opened this section is what distinguishes MacTerminal from iOSTerminal.
            project = ""
            if index + 1 < len(lines):
                following = PROJECT_RE.search(lines[index + 1])
                project = following.group(1) if following else ""
            project = project or current_project
            if project and project not in facts["hosthelpers_projects"]:
                facts["hosthelpers_projects"].append(project)
        elif TEST_RESULT_RE.search(line):
            facts["test_lines"].append(line.strip()[:140])
    facts["test_lines"] = facts["test_lines"][-4:]
    return facts


SWIFT_TREE_PATHS = ("Package.swift", "Sources", "Tests", "TerminalApp")


def tree_equivalence(repo: "GitRepo", ref_a: str, ref_b: str, paths: Iterable[str] = SWIFT_TREE_PATHS) -> dict[str, bool] | None:
    """Per path: do two refs hold the identical tree or blob? None when either commit is unknown to the repository."""
    if not (repo.git_ok("cat-file", "-e", f"{ref_a}^{{commit}}") and repo.git_ok("cat-file", "-e", f"{ref_b}^{{commit}}")):
        return None

    def ident(ref: str, path: str) -> str | None:
        try:
            return repo.tree_id(f"{ref}:{path}")
        except GitError:
            return None

    return {path: ident(ref_a, path) == ident(ref_b, path) for path in paths}


CONCLUSION_VI = {"success": "đạt", "failure": "lỗi", "cancelled": "bị huỷ", "skipped": "bỏ qua", "timed_out": "quá thời gian"}

# (job, step) pairs of the `Swift` workflow (.github/workflows/xcode.yml) that carry Apple-platform evidence.
SWIFT_EVIDENCE = {
    "mac_build": ("build", "Xcode Mac Build"),
    "ios_build": ("build", "Xcode iOS Build"),
    "swift_build": ("build", "Swift Package Build"),
    "swift_test": ("build", "Run tests"),
    "strict_concurrency": ("swiftpm-strict-concurrency", None),
    "thread_sanitizer": ("thread-sanitizer", None),
    "esctest": ("esctest", None),
    "swift6_tools": ("swift6-tools", None),
    "linux": ("linux-headless", None),
}


def job_state(job: dict | None, step: str | None = None) -> str:
    """Vietnamese one-word state of a workflow job or of one of its steps."""
    if job is None:
        return "không có dữ liệu"
    if job.get("status") == "queued":
        return "chưa có runner nhận"
    node = job if step is None else next((s for s in job.get("steps", []) if s.get("name") == step), None)
    if node is None:
        return "không có dữ liệu"
    if node.get("conclusion"):
        return CONCLUSION_VI.get(node["conclusion"], node["conclusion"])
    return "đang chạy" if node.get("status") == "in_progress" else "chưa chạy"


def swift_states(facts: dict) -> dict[str, str]:
    """State of every evidence job/step of the audited `Swift` run (facts["swift_jobs"])."""
    jobs = {job["name"]: job for job in facts.get("swift_jobs", [])}
    return {key: job_state(jobs.get(job), step) for key, (job, step) in SWIFT_EVIDENCE.items()}


def apple_evidence(states: dict[str, str]) -> dict[str, bool]:
    """What the Swift run proves so far: macOS compile, iOS compile (covers HostHelpers), `swift test` on macOS."""
    return {
        "mac_compiled": "đạt" in (states["strict_concurrency"], states["mac_build"], states["swift_build"]),
        "ios_compiled": states["ios_build"] == "đạt",
        "mac_tested": states["swift_test"] == "đạt",
    }


LINUX_XCTEST_RE = re.compile(r"Executed (\d+) tests?, with (\d+) failures?")
LINUX_TESTING_RE = re.compile(r"Test run with (\d+) tests? in (\d+) suites? (passed|failed)")
LOG_STAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")


def summarise_linux_log(text: str) -> dict:
    """Totals printed by `swift test` in the log of the `linux-headless` job.

    XCTest prints one summary per suite and the grand total last, so the last `Executed` line is the
    total; Swift Testing prints a single `Test run with ...` line.
    """
    xctest = testing = None
    evidence: list[str] = []
    for raw in text.splitlines():
        line = LOG_STAMP_RE.sub("", ANSI_RE.sub("", raw)).strip()
        match = LINUX_XCTEST_RE.search(line)
        if match:
            xctest = {"executed": int(match.group(1)), "failures": int(match.group(2))}
            evidence.append(line)
        match = LINUX_TESTING_RE.search(line)
        if match:
            testing = {"tests": int(match.group(1)), "suites": int(match.group(2)), "result": match.group(3)}
            evidence.append(line)
    return {"xctest": xctest, "swift_testing": testing, "evidence_lines": evidence[-3:]}


def linux_result(facts: dict) -> dict:
    """What the `linux-headless` job of the audited run proves: the counts count only when the job itself succeeded."""
    job = next((j for j in facts.get("swift_jobs", []) if j.get("name") == "linux-headless"), None)
    log = facts.get("linux_headless_log") or {}
    if "xctest" not in log and log.get("evidence_lines"):
        log = summarise_linux_log("\n".join(log["evidence_lines"]))
    xctest, testing = log.get("xctest"), log.get("swift_testing")
    ok = bool(job and job.get("conclusion") == "success" and xctest and xctest["failures"] == 0 and testing and testing["result"] == "passed")
    return {"ok": ok, "state": job_state(job), "job_id": str(job["id"]) if job else "?", "xctest": xctest, "swift_testing": testing}


RESULT_RANK = {"PASS": 0, "NOT_RUN": 1, "FAIL": 2}


def suite_results(test_runs: Iterable[dict], needle: str) -> dict[str, str]:
    """Worst result per ref over the executed runs whose suite name contains `needle` (FAIL > NOT_RUN > PASS)."""
    merged: dict[str, str] = {}
    for run in test_runs:
        if needle not in run.get("suite", ""):
            continue
        ref, result = run["ref"], run.get("result", "")
        result = result if result in RESULT_RANK else "NOT_RUN"
        if ref not in merged or RESULT_RANK[result] > RESULT_RANK[merged[ref]]:
            merged[ref] = result
    return merged


def suite_summary(results: dict[str, str]) -> str:
    """`upstream PASS; fork FAIL; pin FAIL` in a fixed order; empty when the suite was not run."""
    return "; ".join(f"{ref} {results[ref]}" for ref in ("upstream", "fork", "pin", "swiftterm") if ref in results)


def suite_verdict(results: dict[str, str], gate: tuple[str, ...] = ("fork", "pin")) -> str:
    """ĐẠT only when every gate ref ran and passed; upstream is the control, not the subject."""
    if not results:
        return "CHƯA CHẠY"
    failed = [ref for ref in gate if results.get(ref) == "FAIL"]
    if failed:
        return f"KHÔNG ĐẠT ({', '.join(failed)})"
    return "ĐẠT" if all(results.get(ref) == "PASS" for ref in gate) else "CHƯA ĐỦ DỮ LIỆU"


def defect_codes(defects: str) -> set[str]:
    """Defect codes of one command row (`D01:<target>` counts as D01)."""
    return {item.split(":", 1)[0] for item in (defects or "").split(";") if item}


def defect_targets(defects: str, code: str) -> set[str]:
    """Targets named by `<code>:<target>` entries of one command row."""
    return {item.split(":", 1)[1] for item in (defects or "").split(";") if item.startswith(code + ":")}


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    kind: str
    sha: str
    size: int
    path: str

    @property
    def is_blob(self) -> bool:
        return self.kind == "blob"

    @property
    def is_submodule(self) -> bool:
        return self.kind == "commit"

    @property
    def executable(self) -> bool:
        return self.mode == "100755"


class GitRepo:
    """Read-only view of a git repository addressed by ref (no checkout needed)."""

    def __init__(self, path: str | os.PathLike, label: str) -> None:
        self.path = str(path)
        self.label = label

    def git(self, *args: str) -> str:
        proc = subprocess.run(["git", "-C", self.path, *args], capture_output=True)
        if proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
        return proc.stdout.decode("utf-8", "replace")

    def git_ok(self, *args: str) -> bool:
        return subprocess.run(["git", "-C", self.path, *args], capture_output=True).returncode == 0

    def tree_id(self, spec: str) -> str:
        return self.git("rev-parse", "--verify", spec).strip()

    def rev(self, ref: str) -> str:
        return self.git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()

    def subject(self, ref: str) -> str:
        return self.git("log", "-1", "--format=%cI %s", ref).strip()

    def ls_tree(self, ref: str) -> list[TreeEntry]:
        raw = subprocess.run(
            ["git", "-C", self.path, "ls-tree", "-r", "-l", "-z", ref], capture_output=True, check=True
        ).stdout
        entries: list[TreeEntry] = []
        for record in raw.split(b"\0"):
            if not record:
                continue
            meta, _, path = record.partition(b"\t")
            mode, kind, sha, size = meta.split()
            entries.append(
                TreeEntry(mode.decode(), kind.decode(), sha.decode(), 0 if size == b"-" else int(size), path.decode("utf-8", "replace"))
            )
        return entries

    def show(self, ref: str, path: str) -> bytes | None:
        proc = subprocess.run(["git", "-C", self.path, "show", f"{ref}:{path}"], capture_output=True)
        return proc.stdout if proc.returncode == 0 else None

    def reader(self) -> "BlobReader":
        return BlobReader(self)


class BlobReader:
    """Streams many blobs through one long-lived `git cat-file --batch` process."""

    def __init__(self, repo: GitRepo) -> None:
        self._proc = subprocess.Popen(
            ["git", "-C", repo.path, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )

    def read(self, sha: str) -> bytes | None:
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._proc.stdin.write(sha.encode() + b"\n")
        self._proc.stdin.flush()
        header = self._proc.stdout.readline().split()
        if len(header) < 3 or header[1] != b"blob":
            return None
        size = int(header[2])
        data = self._proc.stdout.read(size)
        self._proc.stdout.read(1)
        return data

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.wait()

    def __enter__(self) -> "BlobReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def count_lines(data: bytes) -> tuple[int, int]:
    """Return (total lines, non-blank lines) for text bytes."""
    if not data:
        return 0, 0
    lines = data.splitlines()
    return len(lines), sum(1 for line in lines if line.strip())


def decode(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


@dataclass
class Finding:
    severity: str
    category: str
    repo: str
    location: str
    title: str
    evidence: str
    recommendation: str
    check: str
    status: str = "OPEN"
    id: str = ""


class FindingRegistry:
    """Collects findings and assigns stable IDs ordered by severity then discovery."""

    def __init__(self) -> None:
        self._items: list[Finding] = []

    def add(self, severity: str, category: str, repo: str, location: str, title: str,
            evidence: str, recommendation: str, check: str, status: str = "OPEN") -> Finding:
        if severity not in SEVERITY_ORDER:
            raise ValueError(f"unknown severity {severity}")
        item = Finding(severity, category, repo, location, title, evidence, recommendation, check, status)
        self._items.append(item)
        return item

    def finalize(self) -> list[Finding]:
        ordered = sorted(enumerate(self._items), key=lambda pair: (SEVERITY_ORDER[pair[1].severity], pair[0]))
        for number, (_, item) in enumerate(ordered, 1):
            item.id = f"F-{number:03d}"
        return [item for _, item in ordered]

    def __iter__(self) -> Iterator[Finding]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def write_csv(path: Path, header: list[str], rows: Iterable[Iterable[object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if cell is None else cell for cell in row])
            count += 1
    return count


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=False)
        handle.write("\n")


def findings_to_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(item) for item in findings]


EXT_LANGUAGE = {
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++", ".h": "C/C++/ObjC header",
    ".c": "C", ".cc": "C++", ".cpp": "C++", ".hpp": "C++", ".rs": "Rust", ".go": "Go",
    ".py": "Python", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell",
    ".psm1": "PowerShell", ".cmd": "Batch", ".bat": "Batch", ".js": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".json": "JSON", ".yml": "YAML",
    ".yaml": "YAML", ".toml": "TOML", ".md": "Markdown", ".html": "HTML", ".css": "CSS",
    ".plist": "plist", ".entitlements": "plist", ".pbxproj": "Xcode project", ".xcconfig": "xcconfig",
    ".strings": "Localization", ".xcstrings": "Localization", ".pl": "Perl", ".pm": "Perl", ".lua": "Lua",
    ".tex": "TeX", ".sty": "TeX", ".wat": "WebAssembly text", ".metal": "Metal", ".storyboard": "Interface Builder",
    ".xib": "Interface Builder", ".txt": "Text", ".csv": "CSV", ".patch": "Patch", ".diff": "Patch",
    ".pem": "PEM key/cert", ".cmake": "CMake", ".mk": "Make", ".map": "Source map", ".1": "man page",
    ".resolved": "SwiftPM lock", ".sample": "Config sample", ".env": "Config",
}
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".a", ".dylib", ".so", ".zip", ".gz", ".tar", ".wasm", ".ttf",
    ".otf", ".woff", ".woff2", ".pfx", ".ico", ".icns", ".car", ".mp3", ".mp4", ".mov", ".bin", ".o",
    ".xcassets", ".nib", ".jar", ".class", ".db", ".sqlite", ".webp", ".heic",
}
NAME_LANGUAGE = {
    "Makefile": "Make", "Dockerfile": "Dockerfile", "Package.swift": "Swift", "LICENSE": "Text",
    "Podfile": "Ruby", "Gemfile": "Ruby", "Rakefile": "Ruby", ".gitignore": "Config", ".gitattributes": "Config",
    ".gitmodules": "Config", ".sonarcloud.properties": "Config",
}
SHEBANG_LANGUAGE = (
    ("python", "Python"), ("node", "JavaScript"), ("perl", "Perl"), ("ruby", "Ruby"), ("lua", "Lua"),
    ("pwsh", "PowerShell"), ("bash", "Shell"), ("zsh", "Shell"), ("dash", "Shell"), ("/sh", "Shell"), (" sh", "Shell"),
)


def classify(path: str, head: bytes | None) -> str:
    """Language of a tracked file from its name, extension or shebang."""
    name = os.path.basename(path)
    if name in NAME_LANGUAGE:
        return NAME_LANGUAGE[name]
    ext = os.path.splitext(name)[1].lower()
    if ext in EXT_LANGUAGE:
        return EXT_LANGUAGE[ext]
    if ext in BINARY_EXTENSIONS:
        return "Binary asset"
    if head and head.startswith(b"#!"):
        first = head.split(b"\n", 1)[0].decode("utf-8", "replace").lower()
        for needle, language in SHEBANG_LANGUAGE:
            if needle in first:
                return language
    if head is not None and is_binary(head):
        return "Binary asset"
    return "Other/no extension" if not ext else f"Other ({ext})"
