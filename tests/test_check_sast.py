"""Tests for the SAST check (Bandit).

The tests replace Bandit with a fake that returns Bandit-style JSON, so they
test only our own logic: which files are scanned, the rule and the reports.
"""

from __future__ import annotations

import json

from check_sast import main, run_check

PASSWORD_FINDING = {
    "filename": "src/app.py",
    "line_number": 8,
    "test_id": "B105",
    "test_name": "hardcoded_password_string",
    "issue_severity": "LOW",
    "issue_confidence": "MEDIUM",
    # Example Bandit message, not a real password.
    "issue_text": "Possible hardcoded password: 'Salasana123'",  # pragma: allowlist secret
    "more_info": "https://bandit.readthedocs.io/en/1.9.4/plugins/b105_hardcoded_password_string.html",
}


def bandit_output(results=(), errors=(), skipped=0):
    return {
        "results": list(results),
        "errors": list(errors),
        "metrics": {"_totals": {"skipped_tests": skipped, "nosec": 0}},
    }


def fake_bandit(output):
    calls = []

    def run(paths):
        calls.append(paths)
        return output

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_clean_code_is_accepted():
    report = run_check(["src", "scripts"], fake_bandit(bandit_output()))
    assert report["result"] == "HYVAKSYTTY"
    assert report["exit_code"] == 0
    assert report["findings"] == []


def test_low_severity_finding_is_rejected():
    # Bandit rates hard-coded passwords as LOW. Every finding fails.
    report = run_check(["src"], fake_bandit(bandit_output([PASSWORD_FINDING])))
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1
    assert report["findings"] == [
        {
            "file": "src/app.py",
            "line": 8,
            "test_id": "B105",
            "severity": "LOW",
            "confidence": "MEDIUM",
            "text": PASSWORD_FINDING["issue_text"],
            "more_info": PASSWORD_FINDING["more_info"],
        }
    ]


def test_leading_dot_slash_is_removed_from_paths():
    # Bandit reports "./src/app.py" when given a single file.
    finding = {**PASSWORD_FINDING, "filename": "./src/app.py"}
    report = run_check(["src/app.py"], fake_bandit(bandit_output([finding])))
    assert report["findings"][0]["file"] == "src/app.py"


def test_suppressed_findings_are_counted():
    # `# nosec` exceptions are allowed, but they must stay visible.
    report = run_check(["src"], fake_bandit(bandit_output(skipped=4)))
    assert report["result"] == "HYVAKSYTTY"
    assert report["suppressed"] == 4


def test_file_bandit_could_not_read_is_rejected():
    errors = [{"filename": "src/broken.py", "reason": "syntax error while parsing AST"}]
    report = run_check(["src"], fake_bandit(bandit_output(errors=errors)))
    assert report["result"] == "HYLATTY"
    assert "src/broken.py" in report["error"]


def test_bandit_failure_is_rejected():
    def failing(paths):
        raise RuntimeError("bandit epäonnistui: boom")

    report = run_check(["src"], failing)
    assert report["result"] == "HYLATTY"
    assert "boom" in report["error"]


def test_only_python_files_are_passed_to_bandit():
    # The commit hook passes changed files; only .py files are scanned.
    run = fake_bandit(bandit_output())
    run_check(["README.md", "src/app.py", "scripts/x.py"], run)
    assert run.calls == [["src/app.py", "scripts/x.py"]]


def test_directories_are_passed_as_they_are():
    run = fake_bandit(bandit_output())
    run_check(["src", "scripts"], run)
    assert run.calls == [["src", "scripts"]]


def test_no_python_files_means_nothing_to_scan():
    run = fake_bandit(bandit_output())
    report = run_check(["README.md"], run)
    assert run.calls == []
    assert report["result"] == "HYVAKSYTTY"


def test_main_writes_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        ["src/app.py", "--output-dir", "artifacts"],
        run_bandit=fake_bandit(bandit_output([PASSWORD_FINDING], skipped=2)),
    )
    assert exit_code == 1
    text = (tmp_path / "artifacts/sast-report.txt").read_text("utf-8")
    data = json.loads((tmp_path / "artifacts/sast-report.json").read_text("utf-8"))
    assert "TULOS: HYLATTY" in text
    assert (
        f"LOYDOS: src/app.py:8 B105 (LOW) {PASSWORD_FINDING['issue_text']}"
    ) in text
    assert "OHITETUT_NOSEC: 2" in text
    assert data["findings"][0]["test_id"] == "B105"


def test_main_azure_devops_points_to_file_and_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        ["src/app.py", "--azure-devops"],
        run_bandit=fake_bandit(bandit_output([PASSWORD_FINDING])),
    )
    vso = [l for l in capsys.readouterr().out.splitlines() if l.startswith("##vso[")]
    assert exit_code == 0
    assert vso[0] == (
        "##vso[task.logissue type=error;sourcepath=src/app.py;linenumber=8]"
        f"B105 (LOW): {PASSWORD_FINDING['issue_text']}"
    )
    assert vso[-1].startswith("##vso[task.complete result=Failed;]")
