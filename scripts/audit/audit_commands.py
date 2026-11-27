"""a-Shell command inventory: plist catalogues, host built-ins, wiring in the Xcode project.

Everything is read from git refs, so the same code can compare the manufacturer
(upstream) tip, the fork tip and the commit pinned by the SwiftTerm super-project.
"""
from __future__ import annotations

import os
import plistlib
import re
from dataclasses import dataclass, field
from xml.parsers.expat import ExpatError

import openstep
from audit_lib import GitRepo, TreeEntry, decode

PLIST_FILES = {
    "full": "Resources/commandDictionary.plist",
    "mini": "Resources_mini/commandDictionary.plist",
    "extra": "Resources/extraCommandsDictionary.plist",
    "llvm": "Resources/llvmDictionary.plist",
    "tex": "Resources/texCommandsDictionary.plist",
    "luatex": "Resources/luatexCommandsDictionary.plist",
    "sshStock": "Resources_mini/sshStockCommands.plist",
}
VALID_ARG_TYPES = {"file", "directory", "no", "none", ""}
SOURCE_EXTENSIONS = (".swift", ".m", ".mm", ".c", ".h", ".rs", ".go", ".cpp", ".cc")
APP_TARGETS = ("a-Shell", "a-Shell-mini", "a-Shell-noPython")
REPLACE_RE = re.compile(r"""replaceCommand\(\s*@?"([^"]+)"\s*,\s*@?"([^"]+)"\s*,\s*(\w+)""")
CDECL_RE = re.compile(r"""@_cdecl\(\s*"([^"]+)"\s*\)""")
DEFINITION_HINTS = (
    r"@_cdecl\(\s*\"{sym}\"",
    r"\bfunc\s+{sym}\b",
    r"\bfn\s+{sym}\b",
    r"^//export\s+{sym}\b",
    r"^[\w \t\*]+[ \t\*]{sym}\s*\([^;]*$",
)


@dataclass
class Builtin:
    name: str
    symbol: str
    path: str
    line: int
    main_thread: str
    conditional: bool


@dataclass
class TargetInfo:
    name: str
    catalogue: str | None
    embedded: set[str] = field(default_factory=set)
    resources: set[str] = field(default_factory=set)


@dataclass
class AshellSnapshot:
    label: str
    ref: str
    sha: str
    tables: dict[str, dict[str, list[str]] | None]
    builtins: list[Builtin]
    bins: dict[str, int]
    mans: set[str]
    xcfs_targets: set[str]
    targets: dict[str, TargetInfo]
    absolute_refs: list[tuple[str, str]]
    entries: dict[str, TreeEntry]
    sources: dict[str, str]
    malformed: dict[str, dict[str, str]] = field(default_factory=dict)
    plist_errors: dict[str, str] = field(default_factory=dict)


def _framework_name(framework: str) -> str:
    """`awk.framework/awk` -> `awk`; `@rpath/SCPStock.framework/SCPStock` -> `SCPStock`."""
    head = framework.rsplit("@rpath/", 1)[-1].split("/", 1)[0]
    for suffix in (".framework", ".xcframework", ".dylib"):
        if head.endswith(suffix):
            return head[: -len(suffix)]
    return head


def _pbx_embedded_name(path: str) -> str:
    base = os.path.basename(path)
    for suffix in (".xcframework", ".framework"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def normalise_table(table: dict) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Coerce a catalogue to `name -> [framework, symbol, options, argtype]` so callers can index every row.

    Rows that had to be coerced are returned separately with the reason (defect D08); they must not be
    judged by the other checks because their fields are placeholders.
    """
    rows: dict[str, list[str]] = {}
    malformed: dict[str, str] = {}
    for name, row in table.items():
        key = str(name)
        sequence = isinstance(row, (list, tuple))
        if sequence and len(row) == 4 and all(isinstance(item, str) for item in row):
            rows[key] = list(row)
            continue
        items = [item if isinstance(item, str) else str(item) for item in (row if sequence else [])][:4]
        rows[key] = items + [""] * (4 - len(items))
        malformed[key] = f"expected 4 strings, got {f'{len(row)} item(s)' if sequence else type(row).__name__}"
    return rows, malformed


def _load_tables(repo: GitRepo, ref: str) -> tuple[dict[str, dict[str, list[str]] | None], dict[str, dict[str, str]], dict[str, str]]:
    """(tables, malformed rows per catalogue, unreadable catalogues); a missing file maps to None."""
    tables: dict[str, dict[str, list[str]] | None] = {}
    malformed: dict[str, dict[str, str]] = {}
    errors: dict[str, str] = {}
    for key, path in PLIST_FILES.items():
        data = repo.show(ref, path)
        if data is None:
            tables[key] = None
            continue
        try:
            parsed = plistlib.loads(data)
        except (plistlib.InvalidFileException, ValueError, ExpatError) as exc:
            tables[key], errors[key] = {}, f"{type(exc).__name__}: {exc}"[:200]
            continue
        if not isinstance(parsed, dict):
            tables[key], errors[key] = {}, f"root is {type(parsed).__name__}, expected a dictionary"
            continue
        tables[key], bad = normalise_table(parsed)
        if bad:
            malformed[key] = bad
    return tables, malformed, errors


def _scan_builtins(path: str, text: str) -> tuple[list[Builtin], int]:
    found: list[Builtin] = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("//"):
            continue
        match = REPLACE_RE.search(stripped)
        if match:
            indent = len(raw) - len(raw.lstrip())
            found.append(Builtin(match.group(1), match.group(2), path, number, match.group(3), indent > 8))
    return found, len(found)


GROUP_KINDS = ("PBXGroup", "PBXVariantGroup", "XCVersionGroup")


def pbx_paths(objects: dict) -> dict[str, str]:
    """Project-relative path of every file reference, resolved through its parent groups.

    Xcode keeps only the last path component on a reference that sits in a folder group, so
    `path = commandDictionary.plist` under a group `path = Resources_mini` is the mini catalogue.
    Only `sourceTree = "<group>"` inherits the parent's path; other roots keep their own.
    """
    parent = {child: oid for oid, obj in objects.items() if obj.get("isa") in GROUP_KINDS for child in obj.get("children", [])}
    resolved: dict[str, str] = {}

    def resolve(oid: str, trail: frozenset[str]) -> str:
        if oid in resolved:
            return resolved[oid]
        obj = objects.get(oid, {})
        own = obj.get("path", "")
        if oid in trail or oid not in parent or obj.get("sourceTree", "<group>") != "<group>":
            path = own
        else:
            base = resolve(parent[oid], trail | {oid})
            path = f"{base}/{own}" if base and own else base or own
        resolved[oid] = path
        return path

    return {oid: resolve(oid, frozenset()) for oid, obj in objects.items() if obj.get("isa") == "PBXFileReference"}


def catalogue_key(path: str) -> str | None:
    """`mini`/`full` for a bundled commandDictionary.plist path (group folders may precede it), else None."""
    for key in ("mini", "full"):
        if f"/{path}".endswith(f"/{PLIST_FILES[key]}"):
            return key
    return None


def _load_pbx(repo: GitRepo, ref: str):
    data = repo.show(ref, "a-Shell.xcodeproj/project.pbxproj")
    if data is None:
        return {}, {}, []
    objects = openstep.loads(data)["objects"]
    paths = pbx_paths(objects)
    targets: dict[str, TargetInfo] = {}
    for obj in objects.values():
        if obj.get("isa") != "PBXNativeTarget":
            continue
        info = TargetInfo(obj["name"], None)
        for phase_id in obj.get("buildPhases", []):
            phase = objects.get(phase_id, {})
            kind = phase.get("isa")
            for build_id in phase.get("files", []):
                path = paths.get(objects.get(build_id, {}).get("fileRef", ""), "")
                if kind == "PBXResourcesBuildPhase":
                    info.resources.add(path)
                    if path.endswith("commandDictionary.plist"):
                        info.catalogue = path
                elif kind in ("PBXCopyFilesBuildPhase", "PBXFrameworksBuildPhase") and re.search(r"\.(xcframework|framework|dylib)$", path):
                    info.embedded.add(_pbx_embedded_name(path))
        targets[info.name] = info
    absolute = [
        (obj.get("name") or obj.get("path", ""), obj["path"])
        for obj in objects.values()
        if obj.get("isa") == "PBXFileReference" and obj.get("sourceTree") == "<absolute>"
    ]
    return objects, targets, absolute


def _xcfs_targets(repo: GitRepo, ref: str) -> set[str]:
    data = repo.show(ref, "xcfs/Package.swift")
    if data is None:
        return set()
    return set(re.findall(r"\.binaryTarget\(\s*name:\s*\"([^\"]+)\"", decode(data)))


def snapshot(repo: GitRepo, ref: str, label: str) -> AshellSnapshot:
    entries = {entry.path: entry for entry in repo.ls_tree(ref)}
    builtins: list[Builtin] = []
    sources: dict[str, str] = {}
    with repo.reader() as reader:
        for path, entry in entries.items():
            if not entry.is_blob or not path.endswith(SOURCE_EXTENSIONS) or path.startswith(("Resources/", "Resources_mini/", "SwiftTerm/", "cpython/")):
                continue
            data = reader.read(entry.sha)
            if data is None:
                continue
            text = decode(data)
            sources[path] = text
            if path.startswith(("a-Shell/", "ShellWorkers/")):
                found, _ = _scan_builtins(path, text)
                builtins.extend(found)
    bins = {os.path.basename(p): e.size for p, e in entries.items() if p.startswith("Resources/bin/") and e.is_blob}
    mans = {os.path.basename(p).rsplit(".", 1)[0] for p in entries if p.startswith("man/")}
    _, targets, absolute = _load_pbx(repo, ref)
    tables, malformed, plist_errors = _load_tables(repo, ref)
    return AshellSnapshot(
        label=label, ref=ref, sha=repo.rev(ref), tables=tables, builtins=builtins, bins=bins,
        mans=mans, xcfs_targets=_xcfs_targets(repo, ref), targets=targets, absolute_refs=absolute,
        entries=entries, sources=sources, malformed=malformed, plist_errors=plist_errors,
    )


def locate_symbols(snap: AshellSnapshot, wanted: set[str]) -> dict[str, dict[str, object]]:
    """Find where each symbol is defined (or merely mentioned) in first-party sources."""
    result: dict[str, dict[str, object]] = {sym: {"defined": [], "mentioned": []} for sym in wanted}
    if not wanted:
        return result
    pattern = re.compile(r"\b(" + "|".join(re.escape(sym) for sym in sorted(wanted, key=len, reverse=True)) + r")\b")
    hints = {sym: [re.compile(h.format(sym=re.escape(sym)), re.M) for h in DEFINITION_HINTS] for sym in wanted}
    for path, text in snap.sources.items():
        if not pattern.search(text):
            continue
        lines = text.splitlines()
        for number, line in enumerate(lines, 1):
            for match in pattern.finditer(line):
                sym = match.group(1)
                if "replaceCommand(" in line:
                    continue
                window = "\n".join(lines[max(0, number - 2):number])
                bucket = "defined" if any(h.search(window) or h.search(line) for h in hints[sym]) else "mentioned"
                result[sym][bucket].append(f"{path}:{number}")
    return result


def framework_provenance(snap: AshellSnapshot, framework: str, symbol: str, symbols: dict[str, dict[str, object]]) -> tuple[str, str]:
    """(category, detail) describing where a plist framework reference comes from."""
    if framework == "SELF":
        defined = symbols.get(symbol, {}).get("defined", [])
        if defined:
            return "app-source", str(defined[0])
        return "linked-prebuilt (SELF, ios_system)", "symbol not defined in repo sources"
    name = _framework_name(framework)
    if framework.endswith(".dylib") and not framework.startswith("@rpath"):
        return "system-dylib", framework
    low = name.lower()
    in_xcfs = name in snap.xcfs_targets
    embedded_anywhere = any(name in t.embedded for t in snap.targets.values())
    recipe = next((p for p in sorted(snap.entries) if p.startswith((f"{low}/", f"{name}/", f"scripts/build-{low}"))), None)
    workflow = next((p for p in sorted(snap.entries) if p.startswith(".github/workflows/") and low in os.path.basename(p).lower()), None)
    if in_xcfs:
        return "xcfs-binaryTarget (prebuilt, checksum-pinned)", name
    if recipe or workflow:
        return "in-repo recipe (build script / CI workflow)", recipe or workflow or name
    if name == "Python" and "downloadFrameworks.sh" in snap.entries:
        return "downloadFrameworks.sh tarball (pythonInstall.tar.gz, no checksum)", "curl -fOL https://github.com/holzschu/a-shell/releases/download/cpython_05_22/pythonInstall.tar.gz"
    if embedded_anywhere:
        return "undeclared artifact (embedded by Xcode project; no xcfs binaryTarget, no recipe)", name
    return "UNPROVISIONED", name


def target_catalogues(snap: AshellSnapshot) -> dict[str, str]:
    """Map the app target -> catalogue key (`full` or `mini`) by its bundled commandDictionary.plist.

    A target whose catalogue path is neither is left out instead of being assumed to be `full`.
    """
    mapping: dict[str, str] = {}
    for name in APP_TARGETS:
        target = snap.targets.get(name)
        key = catalogue_key(target.catalogue) if target and target.catalogue else None
        if key:
            mapping[name] = key
    return mapping
