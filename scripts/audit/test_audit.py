#!/usr/bin/env python3
"""Positive/negative controls for the audit detectors.

A detector that never fires proves nothing, so every check is exercised on a known-bad
input (must fire) and a known-good input (must stay silent). Run: python3 -m unittest -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_invocations as inv  # noqa: E402
import audit_scripts as scripts  # noqa: E402
import audit_security as sec  # noqa: E402
import openstep  # noqa: E402
from audit_lib import FindingRegistry, TreeEntry, classify  # noqa: E402


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
        self.assertEqual(kinds, ["ci-runner-never-runs", "workflow-permissions", "workflow-unpinned-actions"])
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
            "Docs/evidence/old.md": f"{wrong}\n",
        }
        got = sorted((p.location.split(":")[0], p.severity) for p in scripts.domain_references("t", texts))
        self.assertEqual(got, [("note.md", "LOW"), ("wf.yml", "MEDIUM")])


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


class RegistryTests(unittest.TestCase):
    def test_ids_follow_severity_order(self) -> None:
        registry = FindingRegistry()
        registry.add("LOW", "c", "r", "l", "low", "e", "r", "x")
        registry.add("CRITICAL", "c", "r", "l", "crit", "e", "r", "x")
        ordered = registry.finalize()
        self.assertEqual([(f.id, f.severity) for f in ordered], [("F-001", "CRITICAL"), ("F-002", "LOW")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
