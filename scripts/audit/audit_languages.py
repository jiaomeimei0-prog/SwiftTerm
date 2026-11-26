"""Language / size inventory of one git ref (what is in the tree, by language and area)."""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

from audit_lib import GitRepo, TreeEntry, classify, count_lines, is_binary

MAX_TEXT_BYTES = 2_000_000

AREA_BY_TOP_DIR = {
    "swiftterm": {
        "Sources": "engine+libraries", "Tests": "tests", "TerminalApp": "sample apps", "Web": "web (TS/WASM/Cloudflare)",
        "Tools": "dev tools", "Benchmarks": "dev tools", "Plugins": "build plugins", "Docs": "docs/evidence",
        "scripts": "scripts", ".github": "ci", "Apps": "submodule glue", ".swiftpm": "config",
    },
    "ashell": {
        "a-Shell": "app (Swift)", "ShellWorkers": "app (workers)", "Util": "app (Swift)", "a-Shell-Intents": "app (intents)",
        "a-Shell-IntentsUI": "app (intents)", "a-Shell-LongCommands": "app (intents)", "a-Shell-mini-Intents": "app (intents)",
        "a-Shell-mini-IntentsUI": "app (intents)", "Resources": "bundled resources", "Resources_mini": "bundled resources",
        "man": "bundled resources", "terminfo": "bundled resources", "ODR": "bundled resources", "Assets.xcassets": "bundled resources",
        "Base.lproj": "localization", "en.lproj": "localization", "de.lproj": "localization", "es.lproj": "localization",
        "fr.lproj": "localization", "ja.lproj": "localization", "ko.lproj": "localization", "zh-Hans.lproj": "localization",
        "Settings.bundle": "localization", "codex": "native command recipes", "fd": "native command recipes",
        "fzf": "native command recipes", "gitoxide": "native command recipes", "helix": "native command recipes",
        "Herdr": "native command recipes", "navi": "native command recipes", "node": "native command recipes",
        "rg": "native command recipes", "ruff": "native command recipes", "cpython": "native command recipes",
        "tests": "tests", "ci": "ci/scripts", "scripts": "ci/scripts", ".github": "ci/scripts", "patches": "ci/scripts",
        "docs": "docs", "a-Shell.xcodeproj": "build config", "xcfs": "build config", "SwiftTerm": "submodule",
    },
}
THIRD_PARTY_AREAS = {"bundled resources", "submodule"}


@dataclass
class Bucket:
    files: int = 0
    lines: int = 0
    nonblank: int = 0
    size: int = 0


@dataclass
class LanguageInventory:
    label: str
    ref: str
    sha: str
    by_language: dict[str, Bucket] = field(default_factory=lambda: collections.defaultdict(Bucket))
    first_party_by_language: dict[str, Bucket] = field(default_factory=lambda: collections.defaultdict(Bucket))
    by_area: dict[str, Bucket] = field(default_factory=lambda: collections.defaultdict(Bucket))
    by_top_dir: dict[str, Bucket] = field(default_factory=lambda: collections.defaultdict(Bucket))
    top_dir_languages: dict[str, collections.Counter] = field(default_factory=lambda: collections.defaultdict(collections.Counter))
    submodules: list[tuple[str, str]] = field(default_factory=list)
    total_files: int = 0


def area_of(label: str, path: str) -> str:
    top = path.split("/", 1)[0] if "/" in path else "(root files)"
    return AREA_BY_TOP_DIR[label].get(top, "root files" if top == "(root files)" else "other")


def _add(bucket: Bucket, entry: TreeEntry, lines: int, nonblank: int) -> None:
    bucket.files += 1
    bucket.lines += lines
    bucket.nonblank += nonblank
    bucket.size += entry.size


def collect(repo: GitRepo, ref: str, label: str) -> LanguageInventory:
    inventory = LanguageInventory(label=label, ref=ref, sha=repo.rev(ref))
    with repo.reader() as reader:
        for entry in repo.ls_tree(ref):
            if entry.is_submodule:
                inventory.submodules.append((entry.path, entry.sha))
                continue
            if not entry.is_blob:
                continue
            data = reader.read(entry.sha) if entry.size <= MAX_TEXT_BYTES else None
            head = data[:512] if data is not None else None
            language = classify(entry.path, head)
            lines = nonblank = 0
            if data is not None and not is_binary(data):
                lines, nonblank = count_lines(data)
            area = area_of(label, entry.path)
            top = entry.path.split("/", 1)[0] if "/" in entry.path else "(root files)"
            inventory.total_files += 1
            _add(inventory.by_language[language], entry, lines, nonblank)
            _add(inventory.by_area[area], entry, lines, nonblank)
            _add(inventory.by_top_dir[top], entry, lines, nonblank)
            inventory.top_dir_languages[top][language] += 1
            if area not in THIRD_PARTY_AREAS:
                _add(inventory.first_party_by_language[language], entry, lines, nonblank)
    return inventory


def language_rows(inventory: LanguageInventory) -> list[list[object]]:
    rows: list[list[object]] = []
    for scope, table in (("all tracked files", inventory.by_language), ("first-party only", inventory.first_party_by_language)):
        for language, bucket in sorted(table.items(), key=lambda kv: -kv[1].lines):
            rows.append([inventory.label, inventory.sha[:10], scope, language, bucket.files, bucket.lines, bucket.nonblank, bucket.size])
    return rows


def area_rows(inventory: LanguageInventory) -> list[list[object]]:
    return [
        [inventory.label, inventory.sha[:10], area, b.files, b.lines, b.nonblank, b.size]
        for area, b in sorted(inventory.by_area.items(), key=lambda kv: -kv[1].size)
    ]


def directory_rows(inventory: LanguageInventory) -> list[list[object]]:
    rows = []
    for top, bucket in sorted(inventory.by_top_dir.items(), key=lambda kv: -kv[1].size):
        langs = ", ".join(f"{name} ({count})" for name, count in inventory.top_dir_languages[top].most_common(3))
        rows.append([inventory.label, inventory.sha[:10], top, bucket.files, bucket.lines, bucket.size, langs])
    return rows
