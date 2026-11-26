"""Usage audit of the SwiftTerm HostHelpers bridge (the API a-Shell consumes).

For each public member declared in AppleTerminalView+HostHelpers.swift, count the
call sites in a-Shell and the references in SwiftTerm tests / samples / other sources.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from audit_lib import GitRepo, decode

HOST_HELPERS_PATH = "Sources/SwiftTerm/Apple/AppleTerminalView+HostHelpers.swift"
DECL_RE = re.compile(r"^\s*(?:public|open)\s+(?:final\s+)?(func|var)\s+(\w+)")
PLATFORM_RE = re.compile(r"^#if\s+(.*)$")


@dataclass
class HostApi:
    name: str
    kind: str
    line: int
    ashell_calls: list[str] = field(default_factory=list)
    test_refs: list[str] = field(default_factory=list)
    internal_refs: list[str] = field(default_factory=list)
    sample_refs: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.ashell_calls:
            return "USED_BY_ASHELL" if self.test_refs else "USED_BY_ASHELL_UNTESTED_IN_SWIFTTERM"
        if self.test_refs or self.internal_refs or self.sample_refs:
            return "INTERNAL_OR_TEST_ONLY"
        return "UNUSED"


def declared_api(swiftterm: GitRepo, ref: str) -> tuple[list[HostApi], str]:
    data = swiftterm.show(ref, HOST_HELPERS_PATH)
    if data is None:
        return [], ""
    apis: list[HostApi] = []
    guard = ""
    for number, line in enumerate(decode(data).splitlines(), 1):
        platform = PLATFORM_RE.match(line)
        if platform and "os(" in platform.group(1):
            guard = platform.group(1).strip()
        decl = DECL_RE.match(line)
        if decl:
            apis.append(HostApi(decl.group(2), decl.group(1), number))
    return apis, guard


def _scan(files: dict[str, str], api: HostApi, bucket: list[str], skip: str = "") -> None:
    pattern = re.compile(rf"\b{re.escape(api.name)}\b")
    for path, text in files.items():
        if path == skip:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or not pattern.search(line):
                continue
            if re.search(rf"\b(func|var)\s+{re.escape(api.name)}\b", line):
                continue
            bucket.append(f"{path}:{number}")


def analyse(swiftterm: GitRepo, st_ref: str, ashell_sources: dict[str, str]) -> tuple[list[HostApi], str]:
    apis, guard = declared_api(swiftterm, st_ref)
    swift_files: dict[str, str] = {}
    with swiftterm.reader() as reader:
        for entry in swiftterm.ls_tree(st_ref):
            if entry.is_blob and entry.path.endswith(".swift"):
                data = reader.read(entry.sha)
                if data is not None:
                    swift_files[entry.path] = decode(data)
    tests = {p: t for p, t in swift_files.items() if p.startswith("Tests/")}
    samples = {p: t for p, t in swift_files.items() if p.startswith(("TerminalApp/", "Tools/"))}
    internal = {p: t for p, t in swift_files.items() if p.startswith("Sources/")}
    ashell_swift = {p: t for p, t in ashell_sources.items() if p.endswith(".swift") and p.startswith(("a-Shell/", "ShellWorkers/"))}
    for api in apis:
        _scan(ashell_swift, api, api.ashell_calls)
        _scan(tests, api, api.test_refs)
        _scan(samples, api, api.sample_refs)
        _scan(internal, api, api.internal_refs, skip=HOST_HELPERS_PATH)
    return apis, guard
