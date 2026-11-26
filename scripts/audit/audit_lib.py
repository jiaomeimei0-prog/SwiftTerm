#!/usr/bin/env python3
"""Shared helpers for the repository audit tools (standard library only)."""
from __future__ import annotations

import csv
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


class GitError(RuntimeError):
    """A git command failed."""


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
