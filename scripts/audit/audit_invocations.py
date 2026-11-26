#!/usr/bin/env python3
"""Check command invocations written in docs, scripts and workflows against what the repo defines.

Covered: `swift run/build/test` names against Package.swift, `npm run` against package.json,
`make` targets against Makefiles, `gh workflow run` against workflow files and PowerShell
helper calls against the parameters of the functions that the helper declares.
"""
from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass

from audit_lib import TreeEntry
from audit_scripts import WrongCall

SWIFT_NAMES_RE = re.compile(r"\.(?:executable|library|executableTarget|target|testTarget|plugin)\(\s*name:\s*\"([^\"]+)\"")
SWIFT_RUN_RE = re.compile(r"\bswift\s+run\s+(?:-[\w-]+(?:\s+\S+)?\s+)*([A-Za-z][\w-]*)")
SWIFT_PRODUCT_RE = re.compile(r"\bswift\s+build\b[^\n]*?--(?:product|target)\s+([A-Za-z][\w-]*)")
NPM_RUN_RE = re.compile(r"\bnpm\s+(?:--prefix\s+\S+\s+)?run\s+([\w:-]+)")
MAKE_RE = re.compile(r"(?:^\s*(?:\$\s+)?(?:sudo\s+)?|(?:&&|\|\||;)\s*)make\s+(?:-[\w=-]+\s+)*([A-Za-z][\w.-]*)(?=\s|$|[;&|`])")
CHECKED_SUFFIXES = (".md", ".sh", ".bash", ".ps1", ".cmd", ".yml", ".yaml", ".py", ".toml")
GH_WORKFLOW_RE = re.compile(r"gh\s+workflow\s+run\s+([\w./-]+\.ya?ml)")
PS_FUNCTION_RE = re.compile(r"(?im)^\s*function\s+([\w-]+)\s*(?:\(([^)]*)\))?\s*\{")
PS_PARAM_RE = re.compile(r"(?is)param\s*\((.*?)\)\s*(?:\r?\n|$)")
PS_PARAM_NAME_RE = re.compile(r"\$([A-Za-z_]\w*)")
PS_CALL_RE = re.compile(r"(?im)^\s*(?:\$\w+\s*=\s*)?([A-Z][\w]*-[\w-]+)\b((?:\s+-[A-Za-z]\w*(?:\s+(?!-)(?:\"[^\"]*\"|'[^']*'|\$[\w.:{}()]+|[\w./\\:-]+))?)+)")
FENCE_RE = re.compile(r"^\s*```(\w*)")


@dataclass
class Targets:
    swift_names: set[str]
    npm_scripts: set[str]
    make_targets: set[str]
    workflows: set[str]


def collect_targets(texts: dict[str, str]) -> Targets:
    swift_names: set[str] = set()
    npm_scripts: set[str] = set()
    make_targets: set[str] = set()
    workflows: set[str] = set()
    for path, text in texts.items():
        if path.endswith("Package.swift"):
            swift_names.update(SWIFT_NAMES_RE.findall(text))
        elif path.endswith("package.json") and "node_modules" not in path:
            try:
                npm_scripts.update((json.loads(text).get("scripts") or {}).keys())
            except (json.JSONDecodeError, AttributeError):
                pass
        elif posixpath.basename(path) in ("Makefile", "makefile", "GNUmakefile"):
            make_targets.update(re.findall(r"^([A-Za-z][\w.-]*)\s*:(?!=)", text, re.M))
        elif path.startswith(".github/workflows/"):
            workflows.add(posixpath.basename(path))
    return Targets(swift_names, npm_scripts, make_targets, workflows)


def invocation_checks(repo_label: str, texts: dict[str, str], targets: Targets) -> list[WrongCall]:
    problems: list[WrongCall] = []
    for path, text in texts.items():
        if posixpath.basename(path) == "Makefile" or not path.endswith(CHECKED_SUFFIXES):
            continue
        is_doc = path.endswith(".md")
        in_fence = False
        fence_lang = ""
        for number, line in enumerate(text.splitlines(), 1):
            fence = FENCE_RE.match(line)
            if fence:
                in_fence = not in_fence
                fence_lang = fence.group(1).lower() if in_fence else ""
                continue
            if is_doc and not (in_fence and fence_lang in ("", "sh", "bash", "shell", "zsh", "console", "powershell", "ps1")) and "`" not in line:
                continue
            if line.lstrip().startswith("#") and not is_doc:
                continue
            location = f"{path}:{number}"
            snippet = line.strip()[:160]
            for name in SWIFT_RUN_RE.findall(line):
                if name not in targets.swift_names and name not in ("build", "test"):
                    problems.append(WrongCall("swift-run-unknown-product", repo_label, location, f"swift run {name}", "no such product/target in Package.swift", snippet, "MEDIUM"))
            for name in SWIFT_PRODUCT_RE.findall(line):
                if name not in targets.swift_names:
                    problems.append(WrongCall("swift-build-unknown-target", repo_label, location, f"--product/--target {name}", "no such product/target in Package.swift", snippet, "MEDIUM"))
            for name in NPM_RUN_RE.findall(line):
                if targets.npm_scripts and name not in targets.npm_scripts:
                    problems.append(WrongCall("npm-run-unknown-script", repo_label, location, f"npm run {name}", "no package.json declares this script", snippet, "MEDIUM"))
            if not is_doc or in_fence:
                for name in MAKE_RE.findall(line):
                    if targets.make_targets and name not in targets.make_targets and name not in ("sure", "sense", "it", "use", "install"):
                        problems.append(WrongCall("make-unknown-target", repo_label, location, f"make {name}", "no Makefile declares this target", snippet, "LOW"))
            for name in GH_WORKFLOW_RE.findall(line):
                if posixpath.basename(name) not in targets.workflows:
                    problems.append(WrongCall("gh-workflow-unknown", repo_label, location, name, "no such workflow file under .github/workflows", snippet, "MEDIUM"))
    return problems


def powershell_call_checks(repo_label: str, texts: dict[str, str]) -> list[WrongCall]:
    """Calls of helper functions whose parameter list does not contain the named switch."""
    functions: dict[str, set[str]] = {}
    declared_in: dict[str, str] = {}
    for path, text in texts.items():
        if not path.endswith(".ps1"):
            continue
        for match in PS_FUNCTION_RE.finditer(text):
            name, inline = match.group(1), match.group(2)
            params: set[str] = set()
            if inline:
                params.update(p.lower() for p in PS_PARAM_NAME_RE.findall(inline))
            body = text[match.end(): match.end() + 1500]
            block = PS_PARAM_RE.search(body)
            if block and body[: block.start()].strip() == "":
                params.update(p.lower() for p in PS_PARAM_NAME_RE.findall(block.group(1)))
            functions[name.lower()] = params
            declared_in[name.lower()] = path
    problems: list[WrongCall] = []
    for path, text in texts.items():
        if not path.endswith(".ps1"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            match = PS_CALL_RE.match(line)
            if not match:
                continue
            name = match.group(1).lower()
            if name not in functions or not functions[name]:
                continue
            for switch in re.findall(r"\s-([A-Za-z]\w*)", match.group(2)):
                if switch.lower() not in functions[name] and switch.lower() not in {"verbose", "debug", "erroraction", "warningaction", "whatif", "confirm"}:
                    problems.append(WrongCall("ps1-unknown-parameter", repo_label, f"{path}:{number}", f"{match.group(1)} -{switch}", f"function declared in {declared_in[name]} has no parameter -{switch}", line.strip()[:160], "HIGH"))
    return problems


def missing_exec_bits(repo_label: str, entries: list[TreeEntry], texts: dict[str, str]) -> list[WrongCall]:
    """Files with a shebang that are not executable in git (cannot be run as ./file)."""
    problems: list[WrongCall] = []
    for entry in entries:
        text = texts.get(entry.path)
        if text and text.startswith("#!") and entry.mode != "100755" and entry.is_blob and not entry.path.startswith(("Resources/", "SwiftTerm/")):
            problems.append(WrongCall("shebang-not-executable", repo_label, entry.path, text.splitlines()[0], f"has a shebang but git mode is {entry.mode}", "", "LOW"))
    return problems
