#!/usr/bin/env python3
"""Run the full audit of the two core sources and write machine-readable data.

    python3 scripts/audit/run_audit.py --ashell /path/to/a-shell --out Docs/audit

Reads git objects only (no checkout needed). Optional steps need network/tools:
  --run-tests   run the manufacturer's host tests (plutil shim) and the host E2E script
  --online      refresh GitHub facts (ahead/behind, CI jobs) through `gh`
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_commands as C  # noqa: E402
import audit_hostapi as H  # noqa: E402
import audit_invocations as I  # noqa: E402
import audit_languages as L  # noqa: E402
import audit_scripts as S  # noqa: E402
import audit_security as X  # noqa: E402
from audit_lib import FindingRegistry, GitRepo, decode, findings_to_dicts, write_csv, write_json  # noqa: E402

TABLE_ORDER = ["full", "mini", "extra", "llvm", "tex", "luatex", "sshStock"]
BASELINE = {"full", "mini"}
ON_DEMAND = {"extra", "llvm", "tex", "luatex"}
MANUFACTURER_TESTS = (
    ("tests/ssh-stock-registration.sh", "catalog"),
    ("tests/ssh-stock-registration.sh", "project"),
    ("tests/ssh-stock-registration.sh", "activation-wiring"),
    ("tests/worker-binding.sh", ""),
)
GENERATED_OK = ("Web/dist", "Resources/npm", "Resources/node-fetch")


@dataclass
class Results:
    generated_at: str = ""
    sources: list[dict] = field(default_factory=list)
    graph: dict = field(default_factory=dict)
    languages: dict = field(default_factory=dict)
    scripts: list[dict] = field(default_factory=list)
    entrypoints: list[dict] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    builtins: list[dict] = field(default_factory=list)
    catalogue_sizes: list[dict] = field(default_factory=list)
    target_matrix: list[dict] = field(default_factory=list)
    wrong_calls: list[dict] = field(default_factory=list)
    hostapi: list[dict] = field(default_factory=list)
    hostapi_script: dict = field(default_factory=dict)
    tests_inventory: list[dict] = field(default_factory=list)
    test_runs: list[dict] = field(default_factory=list)
    ci_facts: dict = field(default_factory=dict)
    workflows: list[dict] = field(default_factory=list)
    hosts: list[dict] = field(default_factory=list)
    sinks: list[dict] = field(default_factory=list)
    secrets: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    stale_pins: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    js_escape: list[dict] = field(default_factory=list)
    unit_tests: dict = field(default_factory=dict)
    baseline: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def run(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, f"{type(exc).__name__}: {exc}"


def run_unit_tests() -> dict:
    code, output = run([sys.executable, "-m", "unittest", "test_audit"], cwd=str(HERE), timeout=300)
    ran = re.search(r"Ran (\d+) tests?", output)
    return {"suite": "scripts/audit/test_audit.py (bộ phát hiện, đối chứng dương/âm)", "ran": int(ran.group(1)) if ran else 0, "exit": code, "result": "PASS" if code == 0 else "FAIL"}


def commit_info(repo: GitRepo, ref: str) -> dict:
    sha = repo.rev(ref)
    date = repo.git("log", "-1", "--format=%cs", sha).strip()
    return {"sha": sha, "short": sha[:10], "date": date, "subject": repo.git("log", "-1", "--format=%s", sha).strip()}


def collect_sources(st: GitRepo, ash: GitRepo, args: argparse.Namespace, results: Results) -> dict[str, str]:
    pin = st.git("ls-tree", args.st_ref, "Apps/a-Shell").split()[2]
    refs = {"upstream": args.upstream, "fork": args.fork, "pin": pin}
    nested = {label: next((e.sha for e in ash.ls_tree(ref) if e.path == "SwiftTerm" and e.is_submodule), "") for label, ref in refs.items()}
    results.sources.append({"name": "SwiftTerm (lõi, SoT)", "label": "swiftterm", "repo": "jiaomeimei0-prog/SwiftTerm", "ref": args.st_ref, **commit_info(st, args.st_ref)})
    for label, role in (("upstream", "a-Shell gốc nhà sản xuất (holzschu/a-shell master)"), ("fork", "a-Shell fork master (jiaomeimei0-prog/a-shell)"), ("pin", "a-Shell commit được SwiftTerm ghim (Apps/a-Shell)")):
        results.sources.append({"name": role, "label": label, "repo": "a-shell", "ref": refs[label], **commit_info(ash, refs[label]), "nested_swiftterm": nested[label]})
    graph = {"pin": pin, "nested": nested}
    contains = ash.git("branch", "-a", "--contains", pin).split()
    graph["pin_reachable_from_fork_master"] = ash.git_ok("merge-base", "--is-ancestor", pin, args.fork)
    graph["pin_branches"] = [b for b in contains if b not in ("*",)]
    nested_pin = nested["pin"]
    if nested_pin and st.git_ok("cat-file", "-e", nested_pin + "^{commit}"):
        graph["nested_is_ancestor_of_head"] = st.git_ok("merge-base", "--is-ancestor", nested_pin, args.st_ref)
        graph["nested_commits_behind"] = int(st.git("rev-list", "--count", f"{nested_pin}..{args.st_ref}").strip())
        graph["sources_tree_equal"] = st.tree_id(f"{args.st_ref}:Sources/SwiftTerm") == st.tree_id(f"{nested_pin}:Sources/SwiftTerm")
        graph["nested_subject"] = st.git("log", "-1", "--format=%s", nested_pin).strip()
    def numstat(a: str, b: str) -> list[dict]:
        rows = []
        for line in ash.git("diff", "--numstat", a, b).splitlines():
            added, deleted, path = line.split("\t", 2)
            rows.append({"path": path, "added": added, "deleted": deleted})
        return rows

    graph["fork_vs_upstream_files"] = numstat(refs["upstream"], refs["fork"])
    graph["pin_vs_fork_files"] = numstat(refs["fork"], refs["pin"])
    graph["pbx_swiftterm_reference"] = "XCLocalSwiftPackageReference relativePath=SwiftTerm (nested checkout inside a-Shell)"
    results.graph = graph
    return refs


def posix_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def collect_languages(st: GitRepo, ash: GitRepo, args: argparse.Namespace, results: Results) -> None:
    inventories = [L.collect(st, args.st_ref, "swiftterm"), L.collect(ash, args.fork, "ashell")]
    results.languages = {
        "by_language": [r for inv in inventories for r in L.language_rows(inv)],
        "by_area": [r for inv in inventories for r in L.area_rows(inv)],
        "by_directory": [r for inv in inventories for r in L.directory_rows(inv)],
        "totals": {inv.label: {"sha": inv.sha[:10], "files": inv.total_files, "submodules": len(inv.submodules)} for inv in inventories},
    }
    prefix = "Web/cloudflare/site/"
    generated = [e for e in st.ls_tree(args.st_ref) if e.is_blob and e.path.startswith(prefix)]
    if generated:
        names = collections.Counter(posix_name(e.path) for e in generated if e.path.endswith(".js"))
        results.languages["generated_committed"] = {
            "prefix": prefix, "files": len(generated), "bytes": sum(e.size for e in generated),
            "duplicate_js": sum(1 for count in names.values() if count > 1), "largest": max(generated, key=lambda e: e.size).path[len(prefix):],
        }


def collect_scripts(st: GitRepo, ash: GitRepo, args: argparse.Namespace, results: Results, pin_files: set[str]) -> dict:
    per_repo = {}
    for label, repo, ref in (("swiftterm", st, args.st_ref), ("ashell", ash, args.fork)):
        entries = repo.ls_tree(ref)
        texts = S.collect_texts(repo, ref, entries)
        per_repo[label] = (repo, ref, entries, texts)
        results.scripts += [asdict(s) for s in S.inventory(label, entries, texts)]
        calls = S.script_calls(label, texts, entries)
        extra = {"Apps/a-Shell/": pin_files} if label == "swiftterm" else None
        docs = [p for p in S.doc_references(label, texts, entries, extra) if not p.call.startswith(GENERATED_OK) and not p.call.endswith("-")]
        wf_rows, wf_problems = S.workflow_audit(label, texts)
        containers, functions, per_file = S.test_inventory(texts)
        flt = S.ci_filters(label, texts, containers, functions)
        targets = I.collect_targets(texts)
        inv_problems = I.invocation_checks(label, texts, targets) + I.powershell_call_checks(label, texts) + I.missing_exec_bits(label, entries, texts)
        pkg, ps1 = [], []
        if label == "swiftterm":
            pkg = S.package_references(label, decode(repo.show(ref, "Package.swift")), entries)
            raw = {e.path: repo.show(ref, e.path) for e in entries if e.path.endswith(".ps1")}
            ps1 = S.powershell_checks(label, entries, raw)
        results.wrong_calls += [asdict(p) for p in calls + docs + wf_problems + flt + inv_problems + pkg + ps1 + S.domain_references(label, texts)]
        results.workflows += wf_rows
        results.tests_inventory += [
            {"repo": label, "file": path, "target": path.split("/")[1], "xctest_methods": x, "swift_testing_cases": t}
            for path, (x, t) in sorted(per_file.items())
        ]
        results.entrypoints += entrypoints(label, texts)
    return per_repo


def entrypoints(label: str, texts: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    for path, text in texts.items():
        if path.endswith("Package.swift") and not path.startswith(("Resources/", "cpython/")):
            for kind, name in re.findall(r"\.(executable|library)\(\s*name:\s*\"([^\"]+)\"", text):
                rows.append({"repo": label, "type": f"swift-{kind}", "name": name, "defined_in": path})
        elif path.endswith("package.json") and "node_modules" not in path:
            try:
                for name, cmd in (json.loads(text).get("scripts") or {}).items():
                    rows.append({"repo": label, "type": "npm-script", "name": name, "defined_in": path, "command": str(cmd)[:120]})
            except (json.JSONDecodeError, AttributeError):
                pass
        elif os.path.basename(path) == "Makefile":
            for name in re.findall(r"^([A-Za-z][\w.-]*)\s*:(?!=)", text, re.M):
                rows.append({"repo": label, "type": "make-target", "name": name, "defined_in": path})
        elif path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            jobs = re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", text.split("\njobs:", 1)[-1], re.M) if "\njobs:" in text else []
            rows.append({"repo": label, "type": "workflow", "name": os.path.basename(path), "defined_in": path, "command": ",".join(jobs)})
    return rows


def command_table(snaps: dict[str, C.AshellSnapshot], results: Results) -> None:
    fork, upstream, pin = snaps["fork"], snaps["upstream"], snaps["pin"]
    symbols = {label: C.locate_symbols(s, {row[1] for t in s.tables.values() for row in (t or {}).values() if row[0] == "SELF"} | {b.symbol for b in s.builtins}) for label, s in snaps.items()}
    arg_types = {row[3] for t in upstream.tables.values() for row in (t or {}).values() if len(row) > 3}
    cat_for_target = C.target_catalogues(fork)
    names: set[str] = set()
    for snap in snaps.values():
        names.update(n for t in snap.tables.values() for n in (t or {}))
        names.update(b.name for b in snap.builtins)

    def defs(snap: C.AshellSnapshot, name: str) -> dict[str, tuple]:
        return {k: tuple(snap.tables[k][name]) for k in TABLE_ORDER if snap.tables.get(k) and name in snap.tables[k]}

    def defects_for(label: str, name: str) -> dict[str, str]:
        snap = snaps[label]
        found: dict[str, str] = {}
        table_defs = defs(snap, name)
        for key, row in table_defs.items():
            if len(row) != 4 or not all(isinstance(x, str) for x in row):
                found["D08"] = f"{key}: tuple is not 4 strings"
            elif row[3] not in arg_types:
                found["D08"] = f"{key}: argtype '{row[3]}' not used by manufacturer"
        distinct = {key: row for key, row in table_defs.items() if key not in ("sshStock", "extra")}
        if len({row for row in distinct.values()}) > 1:
            found["D04"] = "; ".join(f"{k}={r[3]!r}" for k, r in distinct.items())
        for target, key in C.target_catalogues(snap).items():
            row = table_defs.get(key)
            if row and row[0] != "SELF" and not row[0].startswith("/"):
                fw = C._framework_name(row[0])
                if fw not in snap.targets[target].embedded:
                    found[f"D01:{target}"] = f"framework {fw} referenced by catalogue '{key}' but not embedded in target {target}"
        for key, row in table_defs.items():
            if row[0] != "SELF" and key in BASELINE:
                category, _ = C.framework_provenance(snap, row[0], row[1], symbols[label])
                if category.startswith(("undeclared artifact", "UNPROVISIONED")):
                    found["D07"] = f"{key}: {row[0]} cannot be reproduced from the repo (no xcfs binaryTarget, no build recipe)"
                elif category.startswith("downloadFrameworks.sh tarball"):
                    found["D10"] = f"{key}: {row[0]} comes from a tarball downloaded without checksum verification"
        for b in snap.builtins:
            if b.name == name and not symbols[label][b.symbol]["defined"] and not table_defs:
                found["D05"] = f"replaceCommand('{name}','{b.symbol}') symbol not defined in repo sources and no catalogue entry"
            elif b.name == name and not symbols[label][b.symbol]["defined"]:
                found["D05"] = f"replaceCommand('{name}','{b.symbol}') symbol not defined in repo sources"
        return found

    def drift(a: C.AshellSnapshot, b: C.AshellSnapshot, name: str) -> str:
        da, db = defs(a, name), defs(b, name)
        ba = sorted((x.symbol, x.main_thread) for x in a.builtins if x.name == name)
        bb = sorted((x.symbol, x.main_thread) for x in b.builtins if x.name == name)
        if not da and not db and not ba and not bb:
            return "-"
        if da == db and ba == bb:
            return "same"
        if not da and not ba:
            return "only-in-other"
        if not db and not bb:
            return "only-in-this"
        return "differs"

    by_builtin = collections.defaultdict(list)
    for b in fork.builtins:
        by_builtin[b.name].append(b)
    for name in sorted(names):
        fork_defs = defs(fork, name) or defs(upstream, name) or defs(pin, name)
        primary_key = next(iter(fork_defs), None)
        row = fork_defs[primary_key] if primary_key else ("", "", "", "")
        category, detail = ("host-builtin only", "") if not primary_key else C.framework_provenance(fork, row[0], row[1], symbols["fork"])
        symbol = row[1] if primary_key else (by_builtin[name][0].symbol if by_builtin[name] else "")
        src = symbols["fork"].get(symbol, {}).get("defined", [])
        placeholder = name in fork.bins
        man = name in fork.mans
        per_target = {}
        for target in C.APP_TARGETS:
            key = cat_for_target.get(target)
            tdefs = defs(fork, name)
            tinfo = fork.targets.get(target)
            if key in tdefs and tinfo:
                fw = tdefs[key][0]
                per_target[target] = "self" if fw == "SELF" or fw.startswith("/") else ("ok" if C._framework_name(fw) in tinfo.embedded else "MISSING")
            elif "sshStock" in tdefs and tinfo:
                per_target[target] = "stock-ok" if C._framework_name(tdefs["sshStock"][0]) in tinfo.embedded else "stock-MISSING"
            elif any(k in tdefs for k in ON_DEMAND):
                per_target[target] = "on-demand"
            elif by_builtin[name]:
                per_target[target] = "host"
            else:
                per_target[target] = "-"
        d_up, d_fork, d_pin = defects_for("upstream", name), defects_for("fork", name), defects_for("pin", name)
        codes = sorted(d_fork)
        origin = "" if not codes else ("upstream-original" if all(c in d_up for c in codes) else "fork-introduced")
        verdict = "OK" if not codes else "DEFECT"
        results.commands.append({
            "command": name, "in_upstream": bool(defs(upstream, name) or any(b.name == name for b in upstream.builtins)),
            "in_fork": bool(defs(fork, name) or by_builtin[name]), "in_pin": bool(defs(pin, name) or any(b.name == name for b in pin.builtins)),
            "catalogues_fork": ",".join(defs(fork, name)), "framework": row[0], "symbol": symbol, "options": row[2], "argtype": row[3],
            "kind": category, "provenance_detail": detail,
            "symbol_defined_in_source": src[0] if src else ("" if not symbol else "not in repo sources (prebuilt/unverified)"),
            "host_builtin": ";".join(f"{b.symbol}@{b.path}:{b.line}" for b in by_builtin[name]),
            "placeholder_in_Resources_bin": placeholder, "man_page": man,
            **{f"target_{t}": per_target[t] for t in C.APP_TARGETS},
            "drift_fork_vs_upstream": drift(fork, upstream, name), "drift_pin_vs_fork": drift(pin, fork, name),
            "defects": ";".join(codes), "defect_detail": " | ".join(d_fork[c] for c in codes), "defect_origin": origin,
            "static_verdict": verdict, "runtime_verdict": "PENDING_USER_DEVICE",
        })
    for key in TABLE_ORDER:
        sizes = {label: (len(s.tables[key]) if s.tables.get(key) else None) for label, s in snaps.items()}
        results.catalogue_sizes.append({"catalogue": key, "file": C.PLIST_FILES[key], **sizes})
    for b in fork.builtins:
        defined = symbols["fork"][b.symbol]["defined"]
        results.builtins.append({
            "name": b.name, "symbol": b.symbol, "main_thread_flag": b.main_thread, "file": b.path, "line": b.line, "conditional": b.conditional,
            "symbol_defined_in_source": defined[0] if defined else "no",
            "also_in_catalogue": ",".join(defs(fork, b.name)),
            "duplicate_registration": sum(1 for x in fork.builtins if x.name == b.name) > 1,
            "same_as_upstream": any((x.name, x.symbol, x.path, x.main_thread) == (b.name, b.symbol, b.path, b.main_thread) for x in upstream.builtins),
        })
    for target, key in sorted(cat_for_target.items()):
        info = fork.targets[target]
        missing = sorted({C._framework_name(r[0]) for r in (fork.tables[key] or {}).values() if r[0] != "SELF" and not r[0].startswith("/") and C._framework_name(r[0]) not in info.embedded})
        results.target_matrix.append({"target": target, "catalogue": key, "catalogue_entries": len(fork.tables[key]), "embedded_frameworks": len(info.embedded), "frameworks_referenced_but_not_embedded": ";".join(missing), "missing_count": len(missing)})


def hostapi_section(st: GitRepo, snaps: dict[str, C.AshellSnapshot], args: argparse.Namespace, results: Results) -> None:
    apis, guard = H.analyse(st, args.st_ref, snaps["pin"].sources)
    results.hostapi = [{"name": a.name, "kind": a.kind, "line": a.line, "status": a.status, "ashell_call_sites": len(a.ashell_calls), "first_call": a.ashell_calls[0] if a.ashell_calls else "", "swiftterm_test_refs": len(a.test_refs), "internal_refs": len(a.internal_refs), "sample_refs": len(a.sample_refs)} for a in apis]
    script = st.show(args.st_ref, "scripts/e2e_acceptance_host.sh")
    listed = re.search(r"APIS=\((.*?)\n\)", decode(script or b""), re.S)
    names = listed.group(1).split() if listed else []
    declared = {a.name for a in apis}
    results.hostapi_script = {"platform_guard": guard, "declared": len(declared), "listed_in_e2e_script": len(names), "declared_not_checked_by_script": sorted(declared - set(names)), "checked_by_script_but_not_declared": sorted(set(names) - declared)}


def run_tests(st: GitRepo, ash: GitRepo, refs: dict[str, str], args: argparse.Namespace, results: Results, out: Path) -> None:
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=f"{HERE / 'shims'}:{os.environ['PATH']}")
    upstream_tests: dict[str, bytes] = {}
    for script, _ in MANUFACTURER_TESTS:
        data = ash.show(refs["upstream"], script)
        if data is not None:
            upstream_tests[script] = data
    for label, ref in refs.items():
        sha = ash.rev(ref)
        tree = work / f"{label}-{sha[:10]}"
        if not tree.exists():
            tree.mkdir(parents=True)
            archive = subprocess.run(["git", "-C", str(ash.path), "archive", sha], capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", str(tree)], input=archive, check=True)
        for script, mode in MANUFACTURER_TESTS:
            present = (tree / script).exists()
            origin = "ref" if present else "upstream (script absent at this ref; applied as treatment)"
            if not present and script in upstream_tests:
                (tree / script).parent.mkdir(parents=True, exist_ok=True)
                (tree / script).write_bytes(upstream_tests[script])
            elif not present:
                results.test_runs.append({"suite": f"a-Shell {script} {mode}".strip(), "ref": label, "sha": sha[:10], "exit": "", "result": "NOT_RUN", "detail": "script absent everywhere"})
                continue
            code, output = run(["bash", script] + ([mode] if mode else []), cwd=str(tree), env=env, timeout=180)
            last = [ln for ln in output.strip().splitlines() if ln.strip()][-1:] or [""]
            results.test_runs.append({"suite": f"a-Shell {script} {mode}".strip(), "ref": label, "sha": sha[:10], "exit": code, "result": "PASS" if code == 0 else "FAIL", "detail": last[0][:160], "script_origin": origin})
    report = out / "data" / "e2e_acceptance_host.log"
    code, output = run(["bash", "scripts/e2e_acceptance_host.sh"], cwd=str(st.path), env=dict(os.environ, E2E_REPORT=str(work / "e2e.md")), timeout=600)
    report.write_text(output, encoding="utf-8")
    summary = re.findall(r"^PASS=(\d+) WARN=(\d+) FAIL=(\d+) SKIP=(\d+)", output, re.M)
    counts = dict(zip(("pass", "warn", "fail", "skip"), map(int, summary[-1]))) if summary else {}
    results.test_runs.append({"suite": "SwiftTerm scripts/e2e_acceptance_host.sh (static greps + dry-run)", "ref": "swiftterm", "sha": st.rev(args.st_ref)[:10], "exit": code, "result": "PASS" if code == 0 and counts.get("fail", 1) == 0 else "FAIL", "detail": json.dumps(counts), "script_origin": "ref"})


def collect_security(per_repo: dict, results: Results, ash: GitRepo, args: argparse.Namespace) -> None:
    for label, (repo, ref, entries, texts) in per_repo.items():
        results.hosts += [{**asdict(h), "schemes": ",".join(sorted(h.schemes)), "areas": ",".join(sorted(h.areas))} for h in X.host_inventory(label, texts)]
        results.sinks += [asdict(h) for h in X.sink_inventory(label, texts, entries)]
        results.secrets += [asdict(h) for h in X.secret_scan(label, texts, entries)]
        if label == "ashell":
            for item in X.js_escape_checks(texts):
                path = item["location"].rsplit(":", 1)[0]
                upstream_text = ash.show(args.upstream, path)
                same = bool(upstream_text) and any(u["snippet"] == item["snippet"] for u in X.js_escape_checks({path: decode(upstream_text)}))
                results.js_escape.append({**item, "repo": label, "same_in_upstream": same})


def doc_claims(st: GitRepo, ash: GitRepo, args: argparse.Namespace, results: Results, snaps: dict[str, C.AshellSnapshot], pin: str) -> None:
    fork = snaps["fork"]
    distinct = len({b.name for b in fork.builtins})
    declared = len(results.hostapi)
    checks = (
        (r"Host builtins \(app\)\s*\|\s*~?(\d+)", "Số host built-in (replaceCommand)", f"{distinct} tên / {len(fork.builtins)} lượt đăng ký", lambda v: int(v) == distinct),
        (r"HostHelpers[^\n]*\((\d+) APIs?\)", "Số API HostHelpers", f"{declared} thành viên public", lambda v: int(v) == declared),
        (r"Port ~(\d+) API HostHelpers", "Số API HostHelpers", f"{declared} thành viên public", lambda v: int(v) == declared),
        (r"\|\s*ST-02\s*\|\s*HostHelpers (\d+) API", "Số API HostHelpers", f"{declared} thành viên public", lambda v: int(v) == declared),
    )
    for entry in st.ls_tree(args.st_ref):
        if not (entry.is_blob and entry.path.endswith(".md")) or entry.path.startswith(("Docs/audit/", "Docs/evidence/")):
            continue
        text = decode(st.show(args.st_ref, entry.path) or b"")
        for number, line in enumerate(text.splitlines(), 1):
            for regex, label, actual, ok in checks:
                match = re.search(regex, line)
                if match:
                    results.claims.append({"location": f"{entry.path}:{number}", "claim": line.strip()[:110], "metric": label, "claimed": match.group(1), "actual": actual, "verdict": "ĐÚNG" if ok(match.group(1)) else "SAI/LỖI THỜI"})
            if re.search(r"a-?shell", line, re.I):
                for token in set(re.findall(r"\b[0-9a-f]{7,40}\b", line)):
                    if sum(ch.isdigit() for ch in token) < 2 or not re.search(r"[a-f]", token):
                        continue
                    if not ash.git_ok("cat-file", "-e", token + "^{commit}"):
                        continue
                    full = ash.rev(token)
                    if full == pin:
                        relation = "hiện hành"
                    elif ash.git_ok("merge-base", "--is-ancestor", full, pin):
                        relation = "cũ hơn pin hiện tại (đã bị thay thế)"
                    elif ash.git_ok("merge-base", "--is-ancestor", full, args.fork):
                        relation = "tổ tiên của fork master"
                    else:
                        relation = "nhánh khác / không liên quan pin"
                    if relation != "hiện hành":
                        results.stale_pins.append({"location": f"{entry.path}:{number}", "sha": token, "subject": ash.git("log", "-1", "--format=%s", full).strip()[:70], "relation": relation})


def load_github_facts(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def refresh_github_facts(args: argparse.Namespace, path: Path, refs: dict[str, str], ash: GitRepo) -> dict:
    facts: dict = {"collected_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    code, out = run(["gh", "api", "repos/jiaomeimei0-prog/a-shell/compare/holzschu:master...master", "--jq", "{status,ahead_by,behind_by,merge_base:.merge_base_commit.sha,html_url}"])
    if code == 0:
        facts["fork_vs_upstream"] = json.loads(out)
    code, out = run(["gh", "api", "repos/jiaomeimei0-prog/SwiftTerm/actions/runs", "--jq", f".workflow_runs|map(select(.head_sha==\"{args.ci_sha or ''}\" and .name==\"Swift\"))|.[0]|{{id,html_url,head_sha,status,conclusion,created_at}}"])
    if code == 0 and out.strip().startswith("{"):
        run_info = json.loads(out)
        facts["swift_run"] = run_info
        if run_info.get("id"):
            code, jobs = run(["gh", "api", f"repos/jiaomeimei0-prog/SwiftTerm/actions/runs/{run_info['id']}/jobs", "--jq", "[.jobs[]|{id,name,labels,status,conclusion,runner_name}]"])
            if code == 0:
                facts["swift_jobs"] = json.loads(jobs)
    pin = refs["pin"]
    for key, endpoint, jq in (
        ("pin_vs_master", f"repos/jiaomeimei0-prog/a-shell/compare/master...{pin}", "{status,ahead_by,behind_by,merge_base:.merge_base_commit.sha}"),
        ("pin_pulls", f"repos/jiaomeimei0-prog/a-shell/commits/{pin}/pulls", "[.[]|{number,state,merged_at,base:.base.ref,head:.head.ref,title,html_url}]"),
        ("fork_only_files", "repos/jiaomeimei0-prog/a-shell/compare/holzschu:master...master", "[.files[]|{filename,status,additions,deletions}]"),
        ("fork_only_commits", "repos/jiaomeimei0-prog/a-shell/compare/holzschu:master...master", "[.commits[]|{sha:.sha[0:10],message:(.commit.message|split(\"\n\")[0])}]"),
        ("upstream_only_commits", "repos/jiaomeimei0-prog/a-shell/compare/master...holzschu:master", "[.commits[]|{sha:.sha[0:10],date:.commit.committer.date[0:10],message:(.commit.message|split(\"\n\")[0])}]"),
        ("runs_for_sha", f"repos/jiaomeimei0-prog/SwiftTerm/actions/runs?head_sha={args.ci_sha}", "[.workflow_runs[]|{id,name,status,conclusion,html_url}]"),
    ):
        code, out = run(["gh", "api", endpoint, "--jq", jq])
        if code == 0 and out.strip():
            facts[key] = json.loads(out)
    if args.linux_log and Path(args.linux_log).exists():
        text = Path(args.linux_log).read_text(encoding="utf-8", errors="replace").splitlines()
        facts["linux_headless_log"] = {"path_note": "log of the linux-headless job (downloaded via MCP get_job_logs)", "evidence_lines": [ln.split("Z ", 1)[-1].strip() for ln in text if re.search(r"Executed \d+ tests, with \d+ failures|Test run with \d+ tests", ln)][-3:]}
    path.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return facts


def build_findings(results: Results, snaps: dict[str, C.AshellSnapshot]) -> FindingRegistry:
    reg = FindingRegistry()
    g, facts = results.graph, results.ci_facts
    by_kind = collections.defaultdict(list)
    for p in results.wrong_calls:
        by_kind[p["kind"]].append(p)
    jobs = facts.get("swift_jobs", [])
    queued = [j["name"] for j in jobs if j.get("status") == "queued"]
    if queued or any("xcode-27" in " ".join(j.get("labels", [])) for j in jobs):
        reg.add("HIGH", "CI/assurance", "swiftterm", ".github/workflows/xcode.yml", "5 job macOS của CI không chạy được trên fork: fork không có runner mang nhãn `xcode-27` (nhãn hạ tầng của upstream)",
                f"{len(queued)} job ở trạng thái queued không có runner: {', '.join(queued)}. Toàn bộ code Apple (Sources/SwiftTerm/{{Apple,Mac,iOS}}, gồm HostHelpers) không được build/test trong CI của fork. Chỉ job linux-headless chạy.",
                "Thêm job biên dịch trên runner GitHub-hosted (repo public nên không tốn phí) — workflow `apple-compile.yml` trong nhánh này — hoặc đăng ký runner `xcode-27` cho fork.", "gh api repos/jiaomeimei0-prog/SwiftTerm/actions/runs/<id>/jobs")
    fork_up = facts.get("fork_vs_upstream")
    failing = [r for r in results.test_runs if r["ref"] == "fork" and r["result"] == "FAIL"]
    if fork_up or failing:
        evidence = (f"fork ahead {fork_up['ahead_by']} / behind {fork_up['behind_by']} so với holzschu/a-shell master (merge-base {fork_up['merge_base'][:10]}); "
                    f"{len(facts.get('upstream_only_commits', []))} commit upstream chưa có trong fork. " if fork_up else "") + \
                   "; ".join(f"{r['suite']} trên {r['ref']}: {r['detail']}" for r in failing) + \
                   ". Đối chứng: cùng script trên upstream = PASS (test do upstream thêm sau merge-base)."
        reg.add("HIGH", "Toàn vẹn build", "ashell", "a-Shell.xcodeproj/project.pbxproj; tests/worker-binding.sh", "Fork a-Shell tụt hậu upstream và không qua bài test `worker-binding.sh` của nhà sản xuất", evidence,
                "Merge `upstream/master` vào fork rồi chạy lại `tests/worker-binding.sh`; xem nhánh đồng bộ upstream.", "bash tests/worker-binding.sh (plutil shim) trên cây fork; đối chứng upstream PASS")
    pvm, pulls = facts.get("pin_vs_master"), facts.get("pin_pulls", [])
    unmerged = (pvm and pvm.get("ahead_by", 0) > 0) or (not pvm and not g.get("pin_reachable_from_fork_master", True))
    if unmerged:
        pr = ", ".join(f"PR #{p['number']} ({p['state']}, nhánh {p['head']})" for p in pulls) or "không tìm thấy PR"
        reg.add("MEDIUM", "Toàn vẹn pin", "swiftterm", ".gitmodules / Apps/a-Shell", "Pin `Apps/a-Shell` trỏ vào commit của PR chưa merge, không thuộc `master` của a-shell",
                f"pin={g['pin'][:10]}; GitHub compare master...pin: {pvm['status']} ahead {pvm['ahead_by']} behind {pvm['behind_by']} (merge-base {pvm['merge_base'][:10]}) — {pr}. Nếu nhánh bị xoá hoặc squash-merge rồi GC, `git submodule update --init` trên bản clone mới sẽ hỏng." if pvm else
                f"pin={g['pin'][:10]} không là tổ tiên của fork master (kiểm tra cục bộ).",
                "Merge PR a-shell tương ứng rồi bump pin về commit nằm trên master (hoặc dùng merge-commit/rebase, không squash).", "gh api repos/jiaomeimei0-prog/a-shell/compare/master...<pin>")
    for target in results.target_matrix:
        if target["missing_count"]:
            cmds = sorted(c["command"] for c in results.commands if c.get(f"target_{target['target']}") == "MISSING")
            reg.add("MEDIUM", "Lệnh", "ashell", f"a-Shell.xcodeproj ({target['target']}) + Resources_mini/commandDictionary.plist",
                    f"Target `{target['target']}` dùng catalogue có {len(cmds)} lệnh mà framework của chúng không được nhúng (giống upstream; có thể là chủ ý cho biến thể CI)",
                    f"Framework thiếu: {target['frameworks_referenced_but_not_embedded']}. Lệnh bị ảnh hưởng: {', '.join(cmds)}. Giống hệt upstream: {all(c['defect_origin'] == 'upstream-original' for c in results.commands if c['command'] in cmds)}.",
                    "Nếu biến thể này được phát hành: dùng catalogue riêng hoặc nhúng framework; nếu chỉ dùng cho CI thì ghi rõ trong tài liệu.", "audit_commands.target_catalogues + PBXNativeTarget embedded frameworks")
    for code, severity, title, rec in (
        ("D07", "MEDIUM", "Không truy được nguồn tái tạo của framework được Xcode nhúng (không có binaryTarget trong xcfs/Package.swift, không có công thức trong repo theo 4 quy tắc tra cứu)",
         "Khai báo binaryTarget có checksum hoặc thêm công thức dựng vào `ci/native-frameworks.sh`."),
        ("D10", "MEDIUM", "Python.framework lấy từ tarball tải bằng `curl -fOL` không kiểm checksum (downloadFrameworks.sh:8)",
         "Ghim SHA-256 của `pythonInstall.tar.gz` và kiểm trước khi `tar xzf` (xcfs đã làm vậy cho 65 binaryTarget)."),
    ):
        hit = [c for c in results.commands if code in c["defects"].split(";")]
        if hit:
            reg.add(severity, "Lệnh / chuỗi cung ứng", "ashell", "xcfs/Package.swift; downloadFrameworks.sh", f"{title}: {len(hit)} lệnh ({', '.join(c['command'] for c in hit)})",
                    f"Framework: {', '.join(sorted({c['framework'] for c in hit}))}. Giống hệt upstream (lỗi gốc nhà sản xuất): {all(c['defect_origin'] == 'upstream-original' for c in hit)}.", rec, f"audit_commands.framework_provenance ({code})")
    basename_hits = [c for c in results.commands if "D04" in c["defects"].split(";")]
    if basename_hits:
        reg.add("LOW", "Lệnh", "ashell", "Resources/commandDictionary.plist vs Resources_mini/commandDictionary.plist", f"Cùng một lệnh khai báo khác nhau giữa catalogue full và mini: {', '.join(c['command'] for c in basename_hits)}",
                "; ".join(f"{c['command']}: {c['defect_detail']}" for c in basename_hits) + " (argtype `file` ở full nhưng `none` ở mini — lỗi gốc nhà sản xuất)", "Thống nhất argtype giữa hai catalogue.", "audit_commands tables diff")
    builtins_unresolved = [b for b in results.builtins if b["symbol_defined_in_source"] == "no"]
    if builtins_unresolved:
        reg.add("LOW", "Lệnh", "ashell", "a-Shell/AppDelegate+TeX.swift:39-79", f"CHƯA XÁC MINH: {len(builtins_unresolved)} đăng ký `replaceCommand` (TeX) trỏ vào symbol `{'`, `'.join(sorted({b['symbol'] for b in builtins_unresolved}))}` nằm trong framework tải theo nhu cầu",
                "Symbol không được định nghĩa trong mã nguồn repo, nên chỉ kiểm chứng được bằng nhị phân prebuilt (VM không tải được). Nếu framework không export symbol này, `replaceCommand` chỉ ghi NSLog và không làm gì. Giống upstream (di sản TeX). Đây là khoảng trống kiểm chứng, chưa phải lỗi đã xác nhận.",
                "Xác minh bằng `nm -gU` trên framework `tex`/`luatex` (job CI trên macOS) hoặc kiểm trên thiết bị: chạy `pdftex --version`.", "audit_commands.locate_symbols + ios_system.m replaceCommand semantics")
    for kind, severity, title, rec in (
        ("ps1-hardcoded-root", "MEDIUM", "Script PowerShell gắn cứng gốc repo `%USERPROFILE%\\Documents\\SwiftTerm`", "Suy ra gốc từ `$PSScriptRoot`."),
        ("wrong-domain-reference", "MEDIUM", "Tham chiếu tên miền sai `tooltop1.vip` (tên miền thật: toolvip1.top)", "Chuyển `toolvip1.top` thành tên miền chính trong workflow/script; thêm biểu ngữ vào tài liệu cũ."),
        ("ps1-no-bom", "LOW", "Script PowerShell thiếu UTF-8 BOM (PowerShell 5.1 đọc theo ANSI)", "Ghi lại file với BOM."),
        ("broken-doc-path", "LOW", "Tài liệu nêu đường dẫn không tồn tại", "Sửa hoặc xoá tham chiếu."),
        ("broken-doc-link", "LOW", "Liên kết markdown hỏng", "Sửa liên kết."),
        ("workflow-permissions", "LOW", "Workflow không khai báo `permissions:` (GITHUB_TOKEN dùng mặc định của repo)", "Thêm `permissions: contents: read`."),
        ("workflow-unpinned-actions", "LOW", "Action bên thứ ba tham chiếu bằng tag thay vì SHA commit", "Ghim SHA (a-Shell của nhà sản xuất đã ghim SHA)."),
        ("shebang-not-executable", "INFO", "File có shebang nhưng git mode không phải 100755", "Chạy qua interpreter hoặc `chmod +x`."),
    ):
        items = by_kind.get(kind, [])
        if items:
            repos = sorted({i["repo"] for i in items})
            reg.add(severity, "Lời gọi sai / vệ sinh", "+".join(repos), items[0]["location"], f"{title} ({len(items)} chỗ)", "; ".join(f"{i['location']}" for i in items[:8]) + (" ..." if len(items) > 8 else ""), rec, f"audit_scripts/audit_invocations kind={kind}")
    if g.get("nested_is_ancestor_of_head") is not None:
        reg.add("LOW", "Kiến trúc", "swiftterm", "Apps/a-Shell/SwiftTerm (submodule lồng)", "Hai bản SwiftTerm: a-Shell build bằng bản lồng `SwiftTerm/` (XCLocalSwiftPackageReference), không phải SoT ở gốc",
                f"nested={g['nested']['pin'][:10]} chậm {g.get('nested_commits_behind')} commit so với HEAD nhưng `Sources/SwiftTerm` {'GIỐNG HỆT' if g.get('sources_tree_equal') else 'KHÁC'} (so tree hash). Đồ thị phụ thuộc vòng: SwiftTerm → a-Shell → SwiftTerm.",
                "Chạy `Sources/SwiftTerm` tree-hash check trong CI mỗi khi bump; hoặc để a-Shell trỏ vào SoT.", "git rev-parse HEAD:Sources/SwiftTerm vs <nested>:Sources/SwiftTerm")
    cert = [s for s in results.secrets if s["kind"] == "private-key-block"]
    if cert:
        reg.add("MEDIUM", "An ninh", "ashell", cert[0]["location"], "Private key + PKCS#12 (mật khẩu `password` viết cứng) commit trong repo public (di sản upstream)",
                "AppDelegate.swift:45-47 nạp `localCertificate.pfx` với passphrase \"password\" cho server HTTPS loopback 127.0.0.1 (WASM). Khoá riêng của chứng chỉ localhost là công khai.",
                "Sinh chứng chỉ per-install khi chạy lần đầu; không commit khoá. Rủi ro thực tế giới hạn ở loopback nhưng khoá công khai nghĩa là bất kỳ tiến trình cục bộ nào cũng mạo danh được nếu WebView tin chứng chỉ.", "audit_security.secret_scan")
        reg.add("MEDIUM", "An ninh", "ashell", "a-Shell/SceneDelegate.swift:6338-6342", "`webView(_:didReceive:)` chấp nhận mọi server-trust (không kiểm tra host/phương thức xác thực) — phát hiện tĩnh, chưa kiểm chứng tính tiếp cận",
                "Handler trả `.useCredential` dựng từ chính `serverTrust` của server cho mọi challenge → vô hiệu hoá kiểm tra chứng chỉ cho WebView dùng delegate này (cần cho chứng chỉ localhost tự ký).",
                "Chỉ chấp nhận khi `protectionSpace.host` là 127.0.0.1/localhost và đúng cổng WASM; còn lại `performDefaultHandling`.", "audit_security.sink_inventory rule=tls-trust-bypass; đọc mã")
    jwt = [s for s in results.secrets if s["kind"] == "jwt"]
    if jwt:
        reg.add("LOW", "An ninh", "swiftterm", jwt[0]["location"], f"Token JWT trong file bằng chứng ({len(jwt)} chỗ)",
                "JWT 'meta' của luồng đăng nhập Cloudflare Access (thời hạn 300 s, đã hết hạn, chứa app AUD tag). Không phải thông tin xác thực còn hiệu lực nhưng không nên nằm trong repo.", "Che (redact) giá trị token trong file bằng chứng.", "audit_security.secret_scan kind=jwt")
    if results.js_escape:
        all_upstream = all(i["same_in_upstream"] for i in results.js_escape)
        reg.add("LOW", "An ninh / độ đúng", "ashell", results.js_escape[0]["location"],
                f"{len(results.js_escape)} chỗ nội suy chuỗi Swift vào JS của WebView mà không escape đầy đủ ({'giống hệt upstream' if all_upstream else 'có chỗ khác upstream'})",
                "; ".join(f"{i['location']} [{i['kind']}]" for i in results.js_escape) + ". Các chỗ cùng loại ở `SceneDelegate+TerminalView.swift` (nhập stdin cho lệnh WebAssembly tương tác) và `SceneDelegate.swift` (xuất stdout vào editor web) đã escape `\\`, `'`/`\"`, xuống dòng; ba chỗ này thì không nhất quán. "
                "Hệ quả suy ra từ mã (chưa kiểm chứng động): nhập dấu `'` rồi Ctrl-D khi lệnh WASM đang đọc stdin làm câu JS lỗi cú pháp (EOF không tới lệnh); nội dung có `\"` trong nút bàn phím phụ gây lỗi tương tự trong editor web.",
                "Dùng cùng hàm escape cho cả ba chỗ (hoặc truyền qua JSON/base64 như các chỗ khác).", "audit_security.js_escape_checks")
    stale = [c for c in results.claims if c["verdict"] != "ĐÚNG"]
    if stale or results.stale_pins:
        reg.add("MEDIUM", "Toàn vẹn báo cáo", "swiftterm", "Docs/*.md", f"Tài liệu chứa {len(stale)} số liệu sai/lỗi thời và {len(results.stale_pins)} tham chiếu pin cũ",
                "; ".join(f"{c['location']} ({c['claimed']} ≠ {c['actual']})" for c in stale[:6]), "Dùng `Docs/audit/` (sinh tự động) làm nguồn số liệu; thêm biểu ngữ 'đã thay thế' vào các báo cáo cũ.", "run_audit.doc_claims")
    hs = results.hostapi_script
    unused = [a["name"] for a in results.hostapi if a["status"] == "UNUSED"]
    untested = [a["name"] for a in results.hostapi if a["status"] == "USED_BY_ASHELL_UNTESTED_IN_SWIFTTERM"]
    if hs:
        reg.add("LOW", "Kiểm thử", "swiftterm", "scripts/e2e_acceptance_host.sh:77", "Bằng chứng HostHelpers chỉ ở mức L0 (grep chuỗi) và nhãn '20 APIs' đã lỗi thời: "
                f"file khai báo {hs['declared']} API (script liệt kê {hs['listed_in_e2e_script']}); {len(untested)} API được a-Shell gọi nhưng SwiftTerm không có test; {len(unused)} API không ai dùng",
                f"Không có test trong SwiftTerm: {', '.join(untested)}; không ai dùng: {', '.join(unused)}. HostHelpers bị bao bởi `{hs['platform_guard']}` nên không bao giờ biên dịch trên Linux (cũng không được CI macOS biên dịch vì job không chạy).",
                "Dùng workflow `apple-compile.yml` (biên dịch iOS) và thêm test cho các API chưa được phủ.", "audit_hostapi.analyse")
    if any(s["repo"] == "ashell" and s["kind"] == "key-or-certificate-file" for s in results.secrets):
        reg.add("INFO", "An ninh", "ashell", "cacert.pem", "Gói CA (cacert.pem, ~200 KB) commit trong repo (di sản upstream, dữ liệu công khai của curl.se)", "Không phải bí mật; cần cập nhật định kỳ.", "Cập nhật theo lịch.", "audit_security.secret_scan")
    reg.add("INFO", "An ninh", "swiftterm", "TerminalApp/WebTerminal/Sources/WebTerminalServer/HTTPServer.swift:4-20,98", "Điểm tốt: WebTerminal (PTY qua WebSocket) chỉ bind 127.0.0.1 và yêu cầu Host + Origin loopback khớp",
            "isAllowedWebSocketOrigin từ chối Origin vắng/không khớp; do đó KHÔNG thể phơi server PTY qua tunnel công khai (Host/Origin sẽ bị từ chối). Các script tunnel chỉ phơi `python -m http.server` tĩnh trên 127.0.0.1.", "Giữ nguyên; không tunnel WebTerminalServer.", "đọc mã HTTPServer.swift + scripts/*.ps1")
    reg.add("INFO", "An ninh", "ashell", "a-Shell/Relay.swift:140-225", "Điểm tốt: Relay chạy lệnh từ xa là opt-in, mặc định bind 127.0.0.1, TLS luôn bật, token ≥32 ký tự so sánh hằng thời gian, mTLS tuỳ chọn", "Rủi ro còn lại: bind 0.0.0.0 + token lộ ⇒ thực thi lệnh từ xa; `relay status` in token khi mTLS tắt (có cảnh báo).", "Khuyến nghị mTLS khi bind ngoài loopback.", "đọc mã Relay.swift")
    reg.add("INFO", "Môi trường", "swiftterm", "VM egress", "Egress VM thực tế là allowlist (github.com/api.github.com) trái với mô tả của công cụ; bằng chứng probe tên miền từ VM không có giá trị", "TLS tới host khác bị reset; tải release asset (release-assets.githubusercontent.com) trả 302 rồi bị chặn.", "Probe `toolvip1.top` từ ngoài VM (GitHub Actions hoặc máy người dùng).", "curl thử nghiệm trong phiên audit")
    return reg


def write_outputs(results: Results, out: Path) -> None:
    data = out / "data"
    data.mkdir(parents=True, exist_ok=True)
    write_csv(data / "languages_by_language.csv", ["repo", "sha", "scope", "language", "files", "lines", "nonblank", "bytes"], results.languages["by_language"])
    write_csv(data / "languages_by_area.csv", ["repo", "sha", "area", "files", "lines", "nonblank", "bytes"], results.languages["by_area"])
    write_csv(data / "directories.csv", ["repo", "sha", "top_dir", "files", "lines", "bytes", "top_languages"], results.languages["by_directory"])

    def dump(name: str, rows: list[dict]) -> None:
        if rows:
            keys = list(rows[0])
            write_csv(data / name, keys, [[("" if r.get(k) is None else (";".join(map(str, r[k])) if isinstance(r.get(k), (list, set)) else r.get(k))) for k in keys] for r in rows])

    dump("scripts_inventory.csv", results.scripts)
    dump("entrypoints.csv", results.entrypoints)
    dump("commands_master.csv", results.commands)
    dump("commands_defects.csv", [c for c in results.commands if c["defects"]])
    dump("commands_host_builtins.csv", results.builtins)
    dump("catalogue_sizes.csv", results.catalogue_sizes)
    dump("target_matrix.csv", results.target_matrix)
    dump("wrong_calls.csv", results.wrong_calls)
    dump("hostapi.csv", results.hostapi)
    dump("tests_inventory.csv", results.tests_inventory)
    dump("test_runs.csv", results.test_runs)
    dump("workflows.csv", results.workflows)
    dump("security_hosts.csv", results.hosts)
    dump("security_sinks.csv", results.sinks)
    dump("security_secrets_redacted.csv", results.secrets)
    dump("doc_claims.csv", results.claims)
    dump("doc_stale_pins.csv", results.stale_pins)
    write_json(data / "findings.json", results.findings)
    write_json(data / "summary.json", results.summary)


def summarise(results: Results) -> dict:
    cmds = results.commands
    return {
        "generated_at": results.generated_at,
        "distinct_command_names": len(cmds),
        "catalogue_sizes_fork": {r["catalogue"]: r["fork"] for r in results.catalogue_sizes},
        "host_builtin_registrations": len(results.builtins),
        "host_builtin_distinct_names": len({b["name"] for b in results.builtins}),
        "commands_with_static_defects": sum(1 for c in cmds if c["defects"]),
        "defects_upstream_original": sum(1 for c in cmds if c["defect_origin"] == "upstream-original"),
        "defects_fork_introduced": sum(1 for c in cmds if c["defect_origin"] == "fork-introduced"),
        "defect_groups": {
            "config": sorted(c["command"] for c in cmds if set(c["defects"].split(";")) & {"D01", "D04", "D08"}),
            "provenance": sorted(c["command"] for c in cmds if set(c["defects"].split(";")) & {"D07", "D10"}),
            "unverified_symbol": sorted(c["command"] for c in cmds if "D05" in c["defects"].split(";")),
        },
        "sinks_by_status": dict(collections.Counter(h["status"] or "-" for h in results.sinks if h["severity"] in ("HIGH", "MEDIUM"))),
        "unit_tests": results.unit_tests,
        "drift_fork_vs_upstream": dict(collections.Counter(c["drift_fork_vs_upstream"] for c in cmds)),
        "wrong_calls_total": len(results.wrong_calls),
        "wrong_calls_by_kind": dict(collections.Counter(p["kind"] for p in results.wrong_calls)),
        "findings_by_severity": dict(collections.Counter(f["severity"] for f in results.findings)),
        "test_runs": {f"{ref}:{res}": n for (ref, res), n in collections.Counter((r["ref"], r["result"]) for r in results.test_runs).items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--swiftterm", default=".")
    parser.add_argument("--ashell", required=True)
    parser.add_argument("--st-ref", default="HEAD")
    parser.add_argument("--upstream", default="upstream/master")
    parser.add_argument("--fork", default="origin/master")
    parser.add_argument("--out", default="Docs/audit")
    parser.add_argument("--workdir", default="/tmp/audit/run")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--ci-sha", default="")
    parser.add_argument("--linux-log", default="")
    parser.add_argument("--baseline-dir", default="", help="directory with summary.json + wrong_calls.csv of an earlier audit (before fixes)")
    parser.add_argument("--baseline-ref", default="", help="commit the baseline audit was run on (documentation only)")
    args = parser.parse_args()

    st, ash = GitRepo(args.swiftterm, "swiftterm"), GitRepo(args.ashell, "ashell")
    out = Path(args.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    results = Results(generated_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    refs = collect_sources(st, ash, args, results)
    pin_files = {e.path for e in ash.ls_tree(refs["pin"]) if e.is_blob}
    snaps = {label: C.snapshot(ash, ref, label) for label, ref in refs.items()}
    collect_languages(st, ash, args, results)
    per_repo = collect_scripts(st, ash, args, results, pin_files)
    command_table(snaps, results)
    hostapi_section(st, snaps, args, results)
    facts_path = out / "data" / "github_facts.json"
    results.ci_facts = refresh_github_facts(args, facts_path, refs, ash) if args.online else load_github_facts(facts_path)
    if args.run_tests:
        run_tests(st, ash, refs, args, results, out)
    elif (out / "data" / "test_runs.csv").exists():
        import csv
        with open(out / "data" / "test_runs.csv", encoding="utf-8") as handle:
            results.test_runs = list(csv.DictReader(handle))
    collect_security(per_repo, results, ash, args)
    results.unit_tests = run_unit_tests()
    if args.baseline_dir and (Path(args.baseline_dir) / "summary.json").exists():
        base = Path(args.baseline_dir)
        import csv
        with open(base / "wrong_calls.csv", encoding="utf-8") as handle:
            results.baseline = {"summary": json.loads((base / "summary.json").read_text(encoding="utf-8")), "wrong_calls": list(csv.DictReader(handle)), "ref": args.baseline_ref}
    doc_claims(st, ash, args, results, snaps, refs["pin"])
    registry = build_findings(results, snaps)
    results.findings = findings_to_dicts(registry.finalize())
    results.summary = summarise(results)
    write_outputs(results, out)
    from render_report import render  # noqa: E402
    render(results, out)
    print(json.dumps(results.summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
