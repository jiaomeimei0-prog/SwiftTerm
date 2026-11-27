"""Positive/negative controls for the audit detectors.

A detector that never fires proves nothing, so every check is exercised on a known-bad
input (must fire) and a known-good input (must stay silent). Run: python3 -m unittest -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_commands  # noqa: E402
import audit_invocations as inv  # noqa: E402
import audit_scripts as scripts  # noqa: E402
import audit_security as sec  # noqa: E402
import openstep  # noqa: E402
import render_report  # noqa: E402
import run_audit  # noqa: E402
from audit_lib import (FindingRegistry, GitRepo, TreeEntry, apple_evidence, classify, defect_codes, defect_targets, job_state, macos_ci_stats,  # noqa: E402
                       minutes_between, suite_results, suite_summary, suite_verdict, summarise_build_log, summarise_ps_log, summarise_swift_log, swift_states, tree_equivalence)


def blob(path: str, mode: str = "100644", size: int = 10) -> TreeEntry:
    return TreeEntry(mode, "blob", "0" * 40, size, path)


class ClassifyTests(unittest.TestCase):
    def test_extension_name_and_shebang(self) -> None:
        self.assertEqual(classify("a/b.swift", b""), "Swift")
        self.assertEqual(classify("x/run", b"#!/usr/bin/env bash\n"), "Shell")
        self.assertEqual(classify("Makefile", b""), "Make")
        self.assertEqual(classify("s.ps1", b""), "PowerShell")


class OpenStepTests(unittest.TestCase):
    def test_parses_pbxproj_style_plist(self) -> None:
        text = b'// !$*UTF8*!\n{ archiveVersion = 1; objects = { A1 = { isa = PBXFileReference; path = "a b.swift"; }; }; list = ( one, "two words", ); }'
        doc = openstep.loads(text)
        self.assertEqual(doc["objects"]["A1"]["path"], "a b.swift")
        self.assertEqual(doc["list"], ["one", "two words"])


class ScriptCallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = [blob("scripts/ok.sh", "100755"), blob("scripts/plain.sh"), blob("scripts/caller.sh"), blob("Docs/a.md")]

    def test_missing_script_fires(self) -> None:
        texts = {"scripts/caller.sh": "#!/bin/sh\nbash scripts/gone.sh\n"}
        kinds = [p.kind for p in scripts.script_calls("t", texts, self.entries)]
        self.assertEqual(kinds, ["missing-script"])

    def test_existing_script_and_build_artifacts_stay_silent(self) -> None:
        texts = {"scripts/caller.sh": "#!/bin/sh\nbash scripts/ok.sh\n./node_modules/.bin/wrangler deploy\n./configure\n"}
        self.assertEqual(scripts.script_calls("t", texts, self.entries), [])

    def test_script_generated_by_the_caller_is_not_missing(self) -> None:
        texts = {"scripts/caller.sh": "#!/bin/sh\necho 'x' >gen.mjs\nnode gen.mjs\n"}
        self.assertEqual(scripts.script_calls("t", texts, self.entries), [])

    def test_direct_call_of_non_executable_fires(self) -> None:
        texts = {"scripts/caller.sh": "#!/bin/sh\n./scripts/plain.sh\n"}
        kinds = [p.kind for p in scripts.script_calls("t", texts, self.entries)]
        self.assertEqual(kinds, ["not-executable"])


class DocReferenceTests(unittest.TestCase):
    def test_broken_link_and_path_fire_valid_ones_do_not(self) -> None:
        entries = [blob("Docs/a.md"), blob("Docs/real.md"), blob("scripts/real.sh")]
        texts = {"Docs/a.md": "See [x](real.md) and [y](nope.md) and `scripts/real.sh` and `scripts/ghost.sh`\n"}
        kinds = sorted(p.kind + ":" + p.call for p in scripts.doc_references("t", texts, entries))
        self.assertEqual(kinds, ["broken-doc-link:nope.md", "broken-doc-path:scripts/ghost.sh"])

    def test_extra_tree_resolves_submodule_paths(self) -> None:
        entries = [blob("Docs/a.md")]
        texts = {"Docs/a.md": "`Apps/a-Shell/tests/x.sh` and `tests/x.sh`\n"}
        self.assertEqual(scripts.doc_references("t", texts, entries, {"Apps/a-Shell/": {"tests/x.sh"}}), [])
        self.assertTrue(scripts.doc_references("t", texts, entries))


class CiFilterTests(unittest.TestCase):
    def test_filter_matching_nothing_fires(self) -> None:
        texts = {".github/workflows/w.yml": "      - run: swift test --filter \"RealSuite|GhostSuite\"\n"}
        problems = scripts.ci_filters("t", texts, {"RealSuite"}, {"testThing"})
        self.assertEqual([p.call for p in problems], ["--filter GhostSuite"])

    def test_module_target_name_is_a_valid_filter(self) -> None:
        texts = {"Tests/Mod/T.swift": "final class A: XCTestCase { func testX() {} }\n"}
        containers, functions, _ = scripts.test_inventory(texts)
        wf = {".github/workflows/w.yml": "swift test --filter Mod\n"}
        self.assertEqual(scripts.ci_filters("t", wf, containers, functions), [])


class PackageTests(unittest.TestCase):
    PACKAGE = '''let package = Package(targets: [
        .target(name: "Good", path: "Sources/Good", exclude: ["gone.txt", "kept.txt"], resources: [.copy("res")]),
        .target(name: "Bad", path: "Sources/Missing"),
    ])'''

    def test_missing_path_exclude_and_resource_fire(self) -> None:
        entries = [blob("Sources/Good/kept.txt")]
        kinds = sorted(p.kind for p in scripts.package_references("t", self.PACKAGE, entries))
        self.assertEqual(kinds, ["package-exclude-missing", "package-path-missing", "package-resource-missing"])


class PowerShellTests(unittest.TestCase):
    def test_hardcoded_root_bom_and_ascii_fire(self) -> None:
        raw = {"scripts/x.ps1": '$Root = Join-Path $env:USERPROFILE "Documents\\SwiftTerm"\n# caf\u00e9\n'.encode("utf-8")}
        kinds = sorted(p.kind for p in scripts.powershell_checks("t", [blob("scripts/x.ps1")], raw))
        self.assertEqual(kinds, ["ps1-hardcoded-root", "ps1-no-bom", "ps1-non-ascii"])

    def test_clean_file_with_bom_is_silent(self) -> None:
        raw = {"scripts/x.ps1": b"\xef\xbb\xbf$Root = Split-Path -Parent $PSScriptRoot\n"}
        self.assertEqual(scripts.powershell_checks("t", [blob("scripts/x.ps1")], raw), [])

    def test_unknown_helper_parameter_fires(self) -> None:
        texts = {
            "scripts/common.ps1": "function Start-Thing {\n  param([string]$Name, [int]$Port)\n}\n",
            "scripts/use.ps1": "Start-Thing -Name a -Port 1\nStart-Thing -Nmae b\n",
        }
        problems = inv.powershell_call_checks("t", texts)
        self.assertEqual([p.call for p in problems], ["Start-Thing -Nmae"])


class InvocationTests(unittest.TestCase):
    TEXTS = {
        "Package.swift": '.executable(name: "tool", targets: ["tool"]), .executableTarget(name: "tool")',
        "package.json": '{"scripts": {"build": "x"}}',
        "Makefile": "all:\n\ttrue\n",
        ".github/workflows/real.yml": "name: x\n",
        "Docs/guide.md": "```bash\nswift run tool\nswift run ghost\nnpm run build\nnpm run nope\nmake all\nmake nothing\ngh workflow run real.yml\ngh workflow run fake.yml\n```\n",
    }

    def test_each_wrong_call_fires_once(self) -> None:
        targets = inv.collect_targets(self.TEXTS)
        kinds = sorted(p.kind for p in inv.invocation_checks("t", self.TEXTS, targets))
        self.assertEqual(kinds, ["gh-workflow-unknown", "make-unknown-target", "npm-run-unknown-script", "swift-run-unknown-product"])

    def test_english_prose_is_not_a_make_call(self) -> None:
        texts = dict(self.TEXTS)
        texts["Docs/prose.md"] = "This will make the build faster; we make a note.\n"
        targets = inv.collect_targets(texts)
        self.assertFalse([p for p in inv.invocation_checks("t", texts, targets) if "prose" in p.location])


class WorkflowTests(unittest.TestCase):
    def test_runner_permissions_and_pinning(self) -> None:
        text = "on: [push]\njobs:\n  a:\n    runs-on: xcode-27\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@" + "a" * 40 + "\n"
        rows, problems = scripts.workflow_audit("t", {".github/workflows/w.yml": text})
        kinds = sorted(p.kind for p in problems)
        self.assertEqual(kinds, ["workflow-permissions", "workflow-unpinned-actions"])
        self.assertEqual((rows[0]["pinned_actions"], rows[0]["unpinned_actions"]), (1, 1))

    def test_job_level_permissions_count(self) -> None:
        text = "on: [push]\njobs:\n  a:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps: []\n"
        problems = scripts.workflow_audit("t", {".github/workflows/w.yml": text})[1]
        self.assertNotIn("workflow-permissions", [p.kind for p in problems])
        two_jobs = text + "  b:\n    runs-on: ubuntu-latest\n    steps: []\n"
        self.assertIn("workflow-permissions", [p.kind for p in scripts.workflow_audit("t", {".github/workflows/w.yml": two_jobs})[1]])

    def test_hardened_workflow_is_silent(self) -> None:
        text = "on: [push]\npermissions:\n  contents: read\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@" + "b" * 40 + "\n"
        self.assertEqual(scripts.workflow_audit("t", {".github/workflows/w.yml": text})[1], [])


class DomainTests(unittest.TestCase):
    def test_wrong_domain_in_code_is_medium_and_in_prose_low(self) -> None:
        texts = {"a.yml": "CUSTOM_DOMAIN: tooltop1.vip\n", "Docs/x.md": "open tooltop1.vip\n", "Docs/evidence/e.md": "tooltop1.vip\n", "ok.yml": "toolvip1.top\n"}
        got = {p.location.split(":")[0]: p.severity for p in scripts.domain_references("t", texts)}
        self.assertEqual(got, {"a.yml": "MEDIUM", "Docs/x.md": "LOW"})


class DomainAcknowledgementTests(unittest.TestCase):
    def test_wrong_domain_flags_code_and_unacknowledged_prose_only(self) -> None:
        wrong, right = next(iter(scripts.WRONG_DOMAINS.items()))
        texts = {
            "wf.yml": f"env:\n  D: {wrong}\n",
            "note.md": f"# Note\nuse {wrong}\n",
            "ack.md": f"# Note\n> Correct domain: {right}; the typo {wrong} is historical.\nbody {wrong}\n",
            "scripts/audit/self.py": f"X = '{wrong}'\n",
            "neg.md": f"# Title\nthe domain is {right} (NOT {wrong})\n",
            "cfg.toml": f"# NOT {wrong}\nhost = '{wrong}'\n",
            "Docs/evidence/old.md": f"{wrong}\n",
        }
        got = sorted((p.location.split(":")[0], p.severity) for p in scripts.domain_references("t", texts))
        self.assertEqual(got, [("cfg.toml", "MEDIUM"), ("cfg.toml", "MEDIUM"), ("note.md", "LOW"), ("wf.yml", "MEDIUM")])


class SelfAuditSkipTests(unittest.TestCase):
    """The audit quotes other repositories' scripts, workflows and mistyped domains on purpose."""

    def test_wrong_call_detectors_ignore_audit_tooling_and_generated_reports(self) -> None:
        entries = [blob("scripts/audit/fixture.py"), blob("Docs/audit/REPORT.md"), blob("scripts/real.sh"), blob("scripts/other.sh")]
        quoted = "bash tests/ghost.sh\ngh workflow run ghost.yml\nsee `scripts/ghost.sh`\n"
        texts = {"scripts/audit/fixture.py": quoted, "Docs/audit/REPORT.md": quoted, "scripts/real.sh": "#!/bin/sh\nbash tests/ghost.sh\n", "scripts/other.sh": "#!/bin/sh\ntrue\n"}
        self.assertEqual([p.location for p in scripts.script_calls("t", texts, entries)], ["scripts/real.sh:2"])
        self.assertEqual(scripts.doc_references("t", texts, entries), [])
        targets = inv.collect_targets(texts)
        self.assertEqual(inv.invocation_checks("t", texts, targets), [])


class SecurityTests(unittest.TestCase):
    def test_secret_scan_redacts_and_ignores_placeholders(self) -> None:
        fake_pat = "ghp_" + "A1b2C3d4" * 5
        texts = {
            "a.txt": f"token={fake_pat}\n" + "-----BEGIN " + "PRIVATE KEY-----\n",
            "b.txt": "password = \"changeme\"\nCLOUDFLARE_API_TOKEN: ${{ secrets.X }}\n",
        }
        hits = sec.secret_scan("t", texts, [])
        self.assertEqual(sorted(h.kind for h in hits), ["github-token", "private-key-block"])
        self.assertTrue(all(fake_pat not in h.redacted for h in hits))

    def test_host_inventory_classifies_and_skips_noise(self) -> None:
        texts = {
            "Sources/a.swift": "// https://github.com/x/y and http://www.w3.org/1999/xhtml and https://toolvip1.top/path\n",
            "Docs/b.md": "see https://example.com\n",
        }
        records = {r.host: r for r in sec.host_inventory("t", texts)}
        self.assertEqual(sorted(records), ["github.com", "toolvip1.top"])
        self.assertEqual(records["toolvip1.top"].group, "Project domain")

    def test_sink_rules_fire_per_language(self) -> None:
        texts = {
            "s.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n",
            "s.ps1": "iex (irm http://x)\n",
            "s.sh": "curl -fsSL http://x | sh\n",
        }
        entries = [blob(p) for p in texts]
        rules = {h.rule for h in sec.sink_inventory("t", texts, entries)}
        self.assertTrue({"shell-true", "invoke-expression", "curl-pipe-shell"} <= rules)

    def scan(self, path: str, language: str, text: str) -> list:
        return sec.scan_sinks(path, text, language)

    def test_listener_detects_real_servers_not_view_binding(self) -> None:
        nw = self.scan("a.swift", "Swift", "let listener = try NWListener(using: parameters)\n")
        self.assertEqual([(h.rule, h.severity) for h in nw], [("network-listener", "MEDIUM")])
        hummingbird = self.scan("b.swift", "Swift", "address: .hostname(\"127.0.0.1\", port: configuration.port)\n")
        self.assertEqual([(h.rule, h.severity) for h in hummingbird], [("network-listener", "INFO")])
        wildcard = self.scan("c.swift", "Swift", "address: .hostname(\"0.0.0.0\", port: 80)\n")
        self.assertIn(("wildcard-bind", "HIGH"), [(h.rule, h.severity) for h in wildcard])
        self.assertEqual(self.scan("d.swift", "Swift", "frameDriver.bind(to: window == nil ? nil : self)\n"), [])
        self.assertEqual(self.scan("e.swift", "Swift", "if listen == \"0.0.0.0\" { return true }\n"), [])
        unix = self.scan("f.swift", "Swift", "let fd = socket(AF_UNIX, SOCK_STREAM, 0)\nguard Darwin.listen(fd, 8) == 0 else {}\n")
        self.assertEqual([(h.rule, h.severity) for h in unix], [("network-listener", "INFO")])

    def test_powershell_print_lines_and_health_checks_are_not_execution(self) -> None:
        self.assertEqual(self.scan("a.ps1", "PowerShell", "Write-Host \"  irm 'https://x/install' | iex\"\n"), [])
        self.assertEqual(self.scan("b.ps1", "PowerShell", "$r = Invoke-WebRequest \"http://127.0.0.1:$Port/\" -UseBasicParsing\n"), [])
        real = self.scan("c.ps1", "PowerShell", "irm https://x/install | iex\nInvoke-WebRequest $u -OutFile $f\n")
        self.assertEqual(sorted((h.rule, h.severity) for h in real), [("download-exec", "MEDIUM"), ("download-exec", "MEDIUM"), ("invoke-expression", "HIGH")])

    def test_guards_downgrade_only_with_visible_mitigation(self) -> None:
        guarded = "for m in z.infolist():\n    t = (root / m.filename).resolve()\n    if not t.is_relative_to(root): raise ValueError()\nz.extractall(root)\n"
        self.assertEqual([(h.rule, h.severity) for h in self.scan("a.py", "Python", guarded)], [("archive-extractall", "INFO")])
        self.assertEqual([(h.rule, h.severity) for h in self.scan("b.py", "Python", "z.extractall(root)\n")], [("archive-extractall", "MEDIUM")])
        checked = "if (n + sizeof(\"/x\") > sizeof(buf)) return 1;\nstrcpy(p, \"/x\");\n"
        self.assertEqual([h.severity for h in self.scan("a.c", "Objective-C/C", checked)], ["INFO"])
        self.assertEqual([h.severity for h in self.scan("b.c", "Objective-C/C", "strcpy(dst, src);\n")], ["MEDIUM"])
        self.assertEqual([h.severity for h in self.scan("a.sh", "Shell", "curl -k https://127.0.0.1:8080/\n")], ["INFO"])
        self.assertEqual([h.severity for h in self.scan("b.sh", "Shell", "curl -k https://example.org/\n")], ["HIGH"])
        self.assertEqual([h.severity for h in self.scan("c.sh", "Shell", "rm -rf \"${dir:?}\"\n")], ["INFO"])
        self.assertEqual([h.severity for h in self.scan("d.sh", "Shell", "rm -rf \"$dir\"\n")], ["LOW"])

    def test_js_escape_checks_flag_only_unescaped_interpolation(self) -> None:
        texts = {
            "A.swift": "\n".join([
                "webView.evaluateJavaScript(\"x += '\\(typed)';\")",
                "webView.evaluateJavaScript(\"x += '\\(typed.replacingOccurrences(of: \"'\", with: \"\\\\'\"))';\")",
                "webView.evaluateJavaScript(\"decode('\\(data.base64EncodedString())')\")",
                "webView.evaluateJavaScript(\"insert(\\\"\" + t.replacingOccurrences(of: \"\\\\\", with: \"\\\\\\\\\") + \"\\\");\")",
                "webView.evaluateJavaScript(\"insert(\\\"\" + t.replacingOccurrences(of: \"\\\\\", with: \"\\\\\\\\\").replacingOccurrences(of: \"\\\"\", with: \"\\\\\\\"\") + \"\\\");\")",
                "webView.evaluateJavaScript(\"window.reset();\")",
            ]),
            "B.txt": "evaluateJavaScript(\"x \\(y)\")",
        }
        got = [(h["kind"], h["location"]) for h in sec.js_escape_checks(texts)]
        self.assertEqual(got, [("js-interpolation-unescaped", "A.swift:1"), ("js-escape-missing-quote", "A.swift:4")])

    def test_review_marks_only_medium_plus_and_defaults_to_not_reviewed(self) -> None:
        known = sec.SinkHit("t", "JavaScript", "eval", "HIGH", "require.js:161", "runtime-code", "x")
        unknown = sec.SinkHit("t", "Swift", "process-spawn", "MEDIUM", "Other/File.swift:3", "runtime-code", "x")
        low = sec.SinkHit("t", "Python", "subprocess", "LOW", "x.py:1", "ci-dev-tooling", "x")
        self.assertEqual(sec.review(known)[0], "BY_DESIGN")
        self.assertEqual(sec.review(unknown), ("NOT_REVIEWED", ""))
        self.assertEqual(sec.review(low), ("", ""))

    def test_javascript_listener_and_child_process_precision(self) -> None:
        self.assertEqual(self.scan("a.js", "JavaScript", "this.listen('keydown', handler);\n"), [])
        self.assertEqual(self.scan("b.js", "JavaScript", "const m = /_HEX_(\\d+)_END_/.exec(output);\n"), [])
        loop = self.scan("c.js", "JavaScript", "server.listen(0, '127.0.0.1', ready);\n")
        self.assertEqual([(h.rule, h.severity) for h in loop], [("http-listener", "INFO")])
        wide = self.scan("d.js", "JavaScript", "httpServer.listen(8080);\n")
        self.assertEqual([(h.rule, h.severity) for h in wide], [("http-listener", "MEDIUM")])
        spawn = self.scan("e.js", "JavaScript", "import { spawnSync } from 'node:child_process';\n")
        self.assertEqual([h.rule for h in spawn], ["child-process"])


class TimeTests(unittest.TestCase):
    def test_vn_time_adds_seven_hours_and_passes_unknown_through(self) -> None:
        self.assertEqual(render_report.vn_time("2026-11-26T16:56:39Z"), "2026-11-26T16:56:39Z (UTC) = 2026-11-26 23:56 giờ Việt Nam (UTC+7)")
        self.assertEqual(render_report.vn_time("2026-11-26T20:00:00Z").split("= ")[1][:16], "2026-11-27 03:00")
        self.assertEqual(render_report.vn_time("?"), "?")


class DefectCodeTests(unittest.TestCase):
    def test_target_suffix_counts_as_the_code(self) -> None:
        self.assertEqual(defect_codes("D01:a-Shell-noPython;D07"), {"D01", "D07"})
        self.assertEqual(defect_codes(""), set())
        self.assertEqual(defect_targets("D01:a-Shell-noPython;D01:x;D07", "D01"), {"a-Shell-noPython", "x"})


class CiFactsTests(unittest.TestCase):
    def test_minutes_between_handles_missing_and_valid_stamps(self) -> None:
        self.assertEqual(minutes_between("2026-11-26T15:47:28Z", "2026-11-26T16:50:53Z"), 63)
        self.assertIsNone(minutes_between("", "2026-11-26T16:50:53Z"))

    FACTS = {
        "collected_at": "2026-11-26T17:00:00Z",
        "swift_recent": [
            {"id": 2, "jobs": [
                {"name": "build", "status": "queued", "conclusion": None, "labels": ["xcode-27"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:50:54Z", "runner_name": None},
                {"name": "strict", "status": "in_progress", "conclusion": None, "labels": ["xcode-27"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:56:18Z", "runner_name": "GitHub Actions 7"},
                {"name": "linux-headless", "status": "completed", "conclusion": "success", "labels": ["ubuntu-latest"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:50:57Z", "runner_name": "GitHub Actions 8"}]},
            {"id": 1, "jobs": [
                {"name": "build", "status": "queued", "conclusion": None, "labels": ["xcode-27"], "created_at": "2026-11-26T15:47:28Z", "started_at": "2026-11-26T15:47:28Z", "runner_name": None}]},
        ]}

    def test_macos_queue_statistics_use_runner_assignment_not_started_at(self) -> None:
        stats = macos_ci_stats(self.FACTS)
        self.assertEqual((stats["runs"], stats["jobs"], stats["started"], stats["queued"], stats["completed"], stats["in_progress"]), (2, 3, 1, 2, 0, 1))
        self.assertEqual(stats["conclusions"], {})
        self.assertEqual(stats["start_delay_min"], (5, 5))
        self.assertEqual(stats["oldest_queued_min"], 72)
        self.assertEqual(stats["ubuntu_max_delay_min"], 0)
        self.assertEqual(stats["not_started"], 0)
        self.assertIsNone(macos_ci_stats({"swift_recent": [{"jobs": [{"labels": ["ubuntu-latest"]}]}]}))

    def test_cancelled_before_a_runner_is_not_a_finished_job(self) -> None:
        facts = {"collected_at": "2026-11-26T17:00:00Z", "swift_recent": [{"id": 1, "jobs": [
            {"name": "build", "status": "completed", "conclusion": "cancelled", "labels": ["xcode-27"], "created_at": "2026-11-26T15:47:28Z", "started_at": "2026-11-26T15:47:28Z", "runner_name": None},
            {"name": "build", "status": "queued", "conclusion": None, "labels": ["xcode-27"], "created_at": "2026-11-26T15:47:28Z", "started_at": "2026-11-26T15:47:28Z", "runner_name": None}]}]}
        stats = macos_ci_stats(facts)
        self.assertEqual((stats["completed"], stats["in_progress"], stats["not_started"], stats["queued"]), (0, 0, 1, 1))
        self.assertGreaterEqual(stats["in_progress"], 0)
        findings = run_audit.findings_to_dicts(run_audit.build_findings(run_audit.Results(ci_facts=facts), {}))
        ci = [f for f in findings if "Hàng đợi job macOS" in f["title"]]
        self.assertEqual([f["severity"] for f in ci], ["HIGH"])
        self.assertIn("0/2 job", ci[0]["title"])
        self.assertIn("1 kết thúc khi chưa có runner", ci[0]["evidence"])

    def test_ci_finding_reports_observed_queueing_and_denies_the_missing_label_theory(self) -> None:
        results = run_audit.Results(ci_facts=self.FACTS)
        findings = run_audit.findings_to_dicts(run_audit.build_findings(results, {}))
        ci = [f for f in findings if "Hàng đợi job macOS" in f["title"]]
        self.assertEqual(len(ci), 1)
        self.assertEqual(ci[0]["severity"], "HIGH")
        self.assertIn("0/3 job", ci[0]["title"])
        self.assertIn("≥ 72 phút", ci[0]["evidence"])
        self.assertIn("không phải thiếu nhãn", ci[0]["evidence"])
        self.assertIn("chưa xác định", ci[0]["evidence"])

    def test_partial_completion_lowers_severity_and_states_the_consequence(self) -> None:
        facts = {**self.FACTS, "swift_run": {"id": 9}, "swift_jobs": [
            {"id": 1, "name": "swiftpm-strict-concurrency", "status": "completed", "conclusion": "success", "labels": ["xcode-27"], "steps": []},
            {"id": 2, "name": "build", "status": "queued", "conclusion": None, "labels": ["xcode-27"], "steps": []}]}
        facts["swift_recent"] = [{"id": 2, "jobs": facts["swift_recent"][0]["jobs"] + [
            {"name": "strict", "status": "completed", "conclusion": "success", "labels": ["xcode-27"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:56:18Z", "runner_name": "r"}]}, facts["swift_recent"][1]]
        findings = run_audit.findings_to_dicts(run_audit.build_findings(run_audit.Results(ci_facts=facts), {}))
        ci = [f for f in findings if "Hàng đợi job macOS" in f["title"]]
        self.assertEqual([f["severity"] for f in ci], ["MEDIUM"])
        self.assertIn("success=1", ci[0]["evidence"])
        self.assertIn("biên dịch macOS ĐÃ có bằng chứng", ci[0]["evidence"])
        self.assertIn("biên dịch iOS (HostHelpers) CHƯA", ci[0]["evidence"])

    def test_finished_macos_job_removes_the_finding(self) -> None:
        facts = {"collected_at": "2026-11-26T17:00:00Z", "swift_recent": [{"id": 1, "jobs": [
            {"name": "build", "status": "completed", "conclusion": "success", "labels": ["xcode-27"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:52:00Z", "runner_name": "r"}]}]}
        findings = run_audit.findings_to_dicts(run_audit.build_findings(run_audit.Results(ci_facts=facts), {}))
        self.assertFalse([f for f in findings if "Hàng đợi job macOS" in f["title"]])

    def test_failed_swift_job_and_failed_windows_run_become_high_findings(self) -> None:
        facts = {"swift_run": {"id": 9}, "swift_jobs": [
            {"id": 7, "name": "build", "status": "completed", "conclusion": "failure", "labels": ["xcode-27"], "html_url": "u",
             "steps": [{"name": "Xcode iOS Build", "conclusion": "failure"}, {"name": "Run tests", "conclusion": "skipped"}]}],
            "runs_for_sha": [{"id": 5, "name": "Windows scripts", "status": "completed", "conclusion": "failure", "html_url": "w"}]}
        findings = run_audit.findings_to_dicts(run_audit.build_findings(run_audit.Results(ci_facts=facts), {}))
        titles = {f["title"]: f["severity"] for f in findings if "CI/assurance" == f["category"]}
        self.assertEqual(titles["Job `build` của workflow Swift thất bại ở bước: Xcode iOS Build"], "HIGH")
        self.assertEqual(titles["Bộ kiểm thử script Windows (PowerShell 5.1) thất bại trên commit CI"], "HIGH")

    def test_compiler_warnings_from_the_log_become_one_low_finding(self) -> None:
        facts = {"swift_log": {"xcode": "Xcode 27.1", "result": "Build complete! (66.22 sec)", "warnings": [
            {"location": "Sources/SwiftTerm/Mac/MacTerminalView.swift:1388:16", "message": "unused"},
            {"location": "Sources/SwiftTerm/Mac/MacTerminalView.swift:4915:45", "message": "deprecated"}]}}
        findings = run_audit.findings_to_dicts(run_audit.build_findings(run_audit.Results(ci_facts=facts), {}))
        warn = [f for f in findings if "cảnh báo" in f["title"]]
        self.assertEqual([(f["severity"], "2 cảnh báo" in f["title"], "`MacTerminalView.swift`" in f["title"]) for f in warn], [("LOW", True, True)])

    def test_job_and_step_states(self) -> None:
        job = {"name": "build", "status": "in_progress", "conclusion": None, "steps": [
            {"name": "Xcode Mac Build", "status": "completed", "conclusion": "success"},
            {"name": "Xcode iOS Build", "status": "in_progress", "conclusion": None},
            {"name": "Run tests", "status": "pending", "conclusion": None},
            {"name": "Coverage", "status": "completed", "conclusion": "skipped"}]}
        self.assertEqual([job_state(job, name) for name in ("Xcode Mac Build", "Xcode iOS Build", "Run tests", "Coverage", "nope")],
                         ["đạt", "đang chạy", "chưa chạy", "bỏ qua", "không có dữ liệu"])
        self.assertEqual(job_state({"status": "queued", "steps": []}, "Run tests"), "chưa có runner nhận")
        self.assertEqual(job_state(None), "không có dữ liệu")
        self.assertEqual(job_state({"status": "completed", "conclusion": "failure"}), "lỗi")

    def test_apple_evidence_needs_the_right_job_or_step(self) -> None:
        jobs = [{"name": "swiftpm-strict-concurrency", "status": "completed", "conclusion": "success", "steps": []},
                {"name": "build", "status": "in_progress", "conclusion": None, "steps": [{"name": "Xcode iOS Build", "status": "in_progress", "conclusion": None}]}]
        proven = apple_evidence(swift_states({"swift_jobs": jobs}))
        self.assertEqual(proven, {"mac_compiled": True, "ios_compiled": False, "mac_tested": False})
        self.assertEqual(apple_evidence(swift_states({})), {"mac_compiled": False, "ios_compiled": False, "mac_tested": False})

    def test_swift_run_lines_show_tree_comparison_and_toolchain(self) -> None:
        facts = {"swift_run": {"id": 9, "head_sha": "c" * 40, "status": "queued", "conclusion": None},
                 "swift_tree": {"st_ref": "HEAD", "same": {"Sources": True, "Tests": False}},
                 "swift_jobs": [{"name": "build", "labels": ["xcode-27"], "status": "queued", "conclusion": None, "steps": [], "html_url": "u"}],
                 "swift_log": {"image": "xcode-27-arm64", "macos": "27.0.1 (build 26A434)", "xcode": "Xcode 27.1", "result": "Build complete! (66.22 sec)", "warnings": []}}
        text = "\n".join(render_report.swift_run_lines(run_audit.Results(ci_facts=facts)))
        self.assertIn("KHÁC ở `Tests`", text)
        self.assertIn("chưa chạy", text)
        self.assertIn("xcode-27-arm64", text)
        facts["swift_tree"]["same"] = {"Sources": True}
        self.assertIn("kết quả áp dụng cho mã đang kiểm", "\n".join(render_report.swift_run_lines(run_audit.Results(ci_facts=facts))))

    def test_windows_lines_contrast_fixed_and_pre_fix_scripts(self) -> None:
        facts = {"windows_log": {"passed": 52, "failed": [], "summary": "ALL PASSED", "ps_version": "5.1.26100.33822", "os": "Microsoft Windows Server 2025", "error": ""},
                 "windows_mutation_log": {"passed": 29, "failed": ["bom a.ps1"], "summary": "", "ps_version": "5.1.26100.33822", "os": "Microsoft Windows Server 2025", "error": "Get-SwiftTermRoot : not recognized"}}
        text = "\n".join(render_report.windows_lines(run_audit.Results(ci_facts=facts)))
        self.assertIn("| 52 | 0 | ALL PASSED |", text)
        self.assertIn("đỏ trên bản lỗi và xanh trên bản đã sửa", text)
        self.assertEqual(render_report.windows_lines(run_audit.Results(ci_facts={})), [])

    def test_section_calls_the_queue_slow_only_while_jobs_are_still_waiting(self) -> None:
        finished = {"collected_at": "2026-11-26T17:00:00Z", "swift_recent": [{"id": 1, "jobs": [
            {"name": "build", "status": "completed", "conclusion": "success", "labels": ["xcode-27"], "created_at": "2026-11-26T16:50:54Z", "started_at": "2026-11-26T16:51:10Z", "runner_name": "r"}]}]}
        self.assertNotIn("chạy chậm", render_report.section_tests(self._report(finished)))
        waiting = render_report.section_tests(self._report(self.FACTS))
        self.assertIn("chạy chậm", waiting)
        self.assertIn("CHƯA CÓ BẰNG CHỨNG", waiting)
        self.assertNotIn("fork/pin PASS", waiting)

    def _report(self, facts: dict) -> run_audit.Results:
        return run_audit.Results(ci_facts=facts, tests_inventory=[], unit_tests={}, test_runs=[], commands=[], wrong_calls=[], hostapi=[],
                                  hostapi_script={"declared": 0}, catalogue_sizes=[{"fork": 0}, {"fork": 0}])


class LogSummaryTests(unittest.TestCase):
    PS_LOG = "\n".join([
        "2026-11-26T17:06:30.1Z PSVersion                 5.1.26100.33822",
        "2026-11-26T17:06:30.1Z Microsoft Windows Server 2025",
        "2026-11-26T17:06:30.2Z PASS bom a.ps1",
        "2026-11-26T17:06:30.3Z PASS public SwiftTerm",
        "2026-11-26T17:06:30.4Z FAIL Error 1033 / tunnel down",
        "2026-11-26T17:06:30.5Z PASS public host: tunnel error fails",
        "2026-11-26T17:06:30.6Z FAIL parse b.ps1 Unexpected token",
        "2026-11-26T17:06:30.7Z FAIL root = parent of scripts dir expected=[x]",
        "2026-11-26T17:06:30.8Z Get-SwiftTermRoot : The term 'Get-SwiftTermRoot' is not recognized as the name of a cmdlet",
        "2026-11-26T17:06:30.9Z 2 FAILED"])

    def test_ps_log_counts_only_harness_lines(self) -> None:
        facts = summarise_ps_log(self.PS_LOG)
        self.assertEqual(facts["passed"], 2)
        self.assertEqual(facts["failed"], ["parse b.ps1 Unexpected token", "root = parent of scripts dir expected=[x]"])
        self.assertEqual((facts["summary"], facts["ps_version"], facts["os"]), ("2 FAILED", "5.1.26100.33822", "Microsoft Windows Server 2025"))
        self.assertIn("Get-SwiftTermRoot", facts["error"])

    def test_swift_log_reads_toolchain_result_and_unique_warnings(self) -> None:
        esc = "\x1b[1;33m"
        warning = f"2026-11-26T16:58:14.4Z /Users/runner/work/SwiftTerm/SwiftTerm/Sources/SwiftTerm/Mac/MacTerminalView.swift:1388:16: {esc}warning: \x1b[1;39mimmutable value 'terminal' was never used\x1b[0;0m \x1b]8;;https://docs.swift.org\x1b\\[#NoUsage]"
        log = "\n".join(["2026-11-26T16:56:19Z Image: xcode-27-arm64", "2026-11-26T16:56:19Z ##[group]Operating System", "2026-11-26T16:56:19Z macOS",
                          "2026-11-26T16:56:19Z 27.0.1", "2026-11-26T16:56:19Z 26A434", "2026-11-26T16:56:20Z   DEVELOPER_DIR: /Applications/Xcode_27.1.app/Contents/Developer",
                          warning, warning, "2026-11-26T16:58:17Z Build complete! (66.22 sec)"])
        facts = summarise_swift_log(log)
        self.assertEqual((facts["image"], facts["macos"], facts["xcode"], facts["result"]), ("xcode-27-arm64", "27.0.1 (build 26A434)", "Xcode 27.1", "Build complete! (66.22 sec)"))
        self.assertEqual(facts["warnings"], [{"location": "Sources/SwiftTerm/Mac/MacTerminalView.swift:1388:16", "message": "immutable value 'terminal' was never used"}])


    def test_build_log_records_results_hosthelpers_projects_and_tests(self) -> None:
        compile_line = "SwiftCompile normal arm64 /Users/runner/work/SwiftTerm/SwiftTerm/Sources/SwiftTerm/Apple/AppleTerminalView+HostHelpers.swift (in target 'SwiftTerm' from project 'SwiftTerm')"
        log = "\n".join([
            "2026-11-26T17:10:46Z " + compile_line, "2026-11-26T17:10:46Z     cd /Users/runner/work/SwiftTerm/SwiftTerm/TerminalApp/MacTerminal.xcodeproj",
            "2026-11-26T17:11:08Z ** BUILD SUCCEEDED **",
            "2026-11-26T17:13:50Z " + compile_line, "2026-11-26T17:13:50Z     cd /Users/runner/work/SwiftTerm/SwiftTerm/TerminalApp/iOSTerminal.xcodeproj",
            "2026-11-26T17:14:14Z ** BUILD SUCCEEDED **", "2026-11-26T17:20:00Z Build complete! (4.2s)",
            "2026-11-26T17:30:00Z Executed 876 tests, with 0 failures (0 unexpected) in 95.1 (95.2) seconds",
            "2026-11-26T17:31:00Z \u2714 Test run with 2291 tests in 140 suites passed after 60.0 seconds."])
        facts = summarise_build_log(log)
        self.assertEqual((facts["xcodebuild_succeeded"], facts["xcodebuild_failed"], facts["swift_build_complete"]), (2, 0, 1))
        self.assertEqual(facts["hosthelpers_projects"], ["MacTerminal", "iOSTerminal"])
        self.assertEqual(len(facts["test_lines"]), 2)
        failed = summarise_build_log("2026-11-26T17:11:08Z ** BUILD FAILED **")
        self.assertEqual((failed["xcodebuild_succeeded"], failed["xcodebuild_failed"], failed["hosthelpers_projects"]), (0, 1, []))

    def test_hosthelpers_project_comes_from_the_xcodebuild_invocation_when_cd_is_the_shared_root(self) -> None:
        compile_line = "SwiftCompile normal arm64 /src/AppleTerminalView+HostHelpers.swift (in target 'SwiftTerm' from project 'SwiftTerm')"
        log = "\n".join([
            "xcodebuild -project TerminalApp/MacTerminal.xcodeproj -scheme MacTerminal",
            compile_line, "    cd /Users/runner/work/SwiftTerm/SwiftTerm/TerminalApp",
            "** BUILD SUCCEEDED **",
            "xcodebuild -project TerminalApp/iOSTerminal.xcodeproj -scheme iOSTerminal",
            compile_line, "    cd /Users/runner/work/SwiftTerm/SwiftTerm/TerminalApp",
            "** BUILD SUCCEEDED **"])
        self.assertEqual(summarise_build_log(log)["hosthelpers_projects"], ["MacTerminal", "iOSTerminal"])


class TreeEquivalenceTests(unittest.TestCase):
    def test_same_and_different_trees_between_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args: str) -> str:
                return subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            (Path(tmp) / "Sources").mkdir()
            (Path(tmp) / "Sources" / "a.swift").write_text("one\n")
            (Path(tmp) / "Package.swift").write_text("p\n")
            git("add", "-A")
            git("commit", "-q", "-m", "first")
            first = git("rev-parse", "HEAD")
            (Path(tmp) / "Sources" / "a.swift").write_text("two\n")
            (Path(tmp) / "notes.md").write_text("n\n")
            git("add", "-A")
            git("commit", "-q", "-m", "second")
            repo = GitRepo(tmp, "t")
            result = tree_equivalence(repo, first, "HEAD")
            self.assertEqual(result, {"Package.swift": True, "Sources": False, "Tests": True, "TerminalApp": True})
            self.assertIsNone(tree_equivalence(repo, "0" * 40, "HEAD"))


class MetaTests(unittest.TestCase):
    def test_no_test_is_shadowed_by_a_duplicate_name(self) -> None:
        import ast
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        self.assertEqual(len(classes), len(set(classes)), "duplicate test class names hide tests")
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [f.name for f in node.body if isinstance(f, ast.FunctionDef)]
                self.assertEqual(len(methods), len(set(methods)), f"duplicate methods in {node.name}")


class CatalogueRobustnessTests(unittest.TestCase):
    def test_short_catalogue_rows_are_recorded_and_do_not_abort_the_table(self) -> None:
        rows, bad = audit_commands.normalise_table({"ok": ["SELF", "sym", "", "none"], "bad": ["only-framework"], "odd": "text"})
        self.assertEqual(bad["bad"], "expected 4 strings, got 1 item(s)")
        self.assertIn("odd", bad)
        self.assertEqual(rows["bad"], ["only-framework", "", "", ""])
        snaps = {}
        for label in ("fork", "upstream", "pin"):
            snaps[label] = audit_commands.AshellSnapshot(
                label=label, ref=label, sha="s", tables={"full": rows, "mini": None, "extra": None, "llvm": None, "tex": None, "luatex": None, "sshStock": None},
                builtins=[], bins={}, mans=set(), xcfs_targets=set(), targets={}, absolute_refs=[], entries={}, sources={},
                malformed={"full": bad}, plist_errors={})
        results = run_audit.Results()
        run_audit.command_table(snaps, results)
        recorded = {c["command"]: c["defects"] for c in results.commands}
        self.assertIn("D08", recorded["bad"])
        self.assertNotIn("D01", recorded["ok"])

    def test_group_relative_paths_select_the_mini_catalogue(self) -> None:
        objects = {
            "ROOT": {"isa": "PBXGroup", "children": ["MINI", "FULL"], "sourceTree": "<group>"},
            "MINI": {"isa": "PBXGroup", "path": "Resources_mini", "children": ["F"], "sourceTree": "<group>"},
            "F": {"isa": "PBXFileReference", "path": "commandDictionary.plist", "sourceTree": "<group>"},
            "FULL": {"isa": "PBXFileReference", "path": "Resources/commandDictionary.plist", "sourceTree": "<group>"},
        }
        paths = audit_commands.pbx_paths(objects)
        self.assertEqual(paths["F"], "Resources_mini/commandDictionary.plist")
        self.assertEqual(audit_commands.catalogue_key(paths["F"]), "mini")
        self.assertEqual(audit_commands.catalogue_key(paths["FULL"]), "full")
        bare = audit_commands.AshellSnapshot(
            label="t", ref="t", sha="s", tables={}, builtins=[], bins={}, mans=set(), xcfs_targets=set(),
            targets={"a-Shell": audit_commands.TargetInfo("a-Shell", "commandDictionary.plist"),
                     "a-Shell-mini": audit_commands.TargetInfo("a-Shell-mini", "Resources_mini/commandDictionary.plist")},
            absolute_refs=[], entries={}, sources={})
        self.assertEqual(audit_commands.target_catalogues(bare), {"a-Shell-mini": "mini"})

    def test_suite_verdicts_come_from_the_runs_that_exist(self) -> None:
        runs = [{"suite": "a-Shell tests/worker-binding.sh", "ref": "upstream", "result": "PASS"},
                {"suite": "a-Shell tests/worker-binding.sh", "ref": "fork", "result": "FAIL"},
                {"suite": "a-Shell tests/worker-binding.sh", "ref": "pin", "result": "NOT_RUN"}]
        binding = suite_results(runs, "worker-binding.sh")
        self.assertEqual(suite_summary(binding), "upstream PASS; fork FAIL; pin NOT_RUN")
        self.assertEqual(suite_verdict(binding), "KHÔNG ĐẠT (fork)")
        self.assertEqual(suite_verdict({}), "CHƯA CHẠY")
        self.assertEqual(suite_verdict({"upstream": "PASS"}), "CHƯA ĐỦ DỮ LIỆU")


class RegistryTests(unittest.TestCase):
    def test_ids_follow_severity_order(self) -> None:
        registry = FindingRegistry()
        registry.add("LOW", "c", "r", "l", "low", "e", "r", "x")
        registry.add("CRITICAL", "c", "r", "l", "crit", "e", "r", "x")
        ordered = registry.finalize()
        self.assertEqual([(f.id, f.severity) for f in ordered], [("F-001", "CRITICAL"), ("F-002", "LOW")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
