"""Tests for the secret scan (detect-secrets).

The tests replace detect-secrets with a fake that returns its JSON results,
so they test only our own logic: which files are scanned and the reports.
"""

from __future__ import annotations

import json

from check_secrets import main, run_check

KEY_FINDINGS = {
    "src/app.py": [
        {"type": "ArcGIS API Key", "line_number": 6, "hashed_secret": "abc"},
        {"type": "Secret Keyword", "line_number": 6, "hashed_secret": "abc"},
    ]
}


def fake_scanner(results):
    calls = []

    def scan(files):
        calls.append(files)
        return results

    scan.calls = calls  # type: ignore[attr-defined]
    return scan


def test_no_secrets_is_accepted():
    report = run_check(["src/app.py"], fake_scanner({}))
    assert report["result"] == "HYVAKSYTTY"
    assert report["exit_code"] == 0
    assert report["scanned_files"] == 1


def test_secret_is_rejected():
    report = run_check(["src/app.py"], fake_scanner(KEY_FINDINGS))
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1
    assert report["findings"] == [
        {"file": "src/app.py", "line": 6, "types": ["ArcGIS API Key", "Secret Keyword"]}
    ]


def test_report_never_contains_the_secret_or_its_hash():
    report = run_check(["src/app.py"], fake_scanner(KEY_FINDINGS))
    assert "abc" not in json.dumps(report)


def test_scanner_failure_is_rejected():
    def failing(files):
        raise RuntimeError("detect-secrets epäonnistui: boom")

    report = run_check(["src/app.py"], failing)
    assert report["result"] == "HYLATTY"
    assert "boom" in report["error"]


def test_no_files_means_nothing_to_scan():
    scan = fake_scanner({})
    report = run_check([], scan)
    assert scan.calls == []
    assert report["result"] == "HYVAKSYTTY"


def test_main_scans_all_tracked_files_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scan = fake_scanner({})
    main([], scan=scan, tracked_files=lambda: ["README.md", "src/app.py"])
    assert scan.calls == [["README.md", "src/app.py"]]


def test_main_scans_given_files(tmp_path, monkeypatch):
    # The commit hook passes the changed files.
    monkeypatch.chdir(tmp_path)
    scan = fake_scanner({})
    main(["config.yml"], scan=scan, tracked_files=lambda: ["should-not-be-used"])
    assert scan.calls == [["config.yml"]]


def test_main_writes_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["src/app.py", "--output-dir", "artifacts"], scan=fake_scanner(KEY_FINDINGS))
    assert exit_code == 1
    text = (tmp_path / "artifacts/secrets-report.txt").read_text("utf-8")
    assert "TULOS: HYLATTY" in text
    assert "SALAISUUS: src/app.py:6 (ArcGIS API Key, Secret Keyword)" in text
    data = json.loads((tmp_path / "artifacts/secrets-report.json").read_text("utf-8"))
    assert data["findings"][0]["file"] == "src/app.py"


def test_main_azure_devops_points_to_file_and_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["src/app.py", "--azure-devops"], scan=fake_scanner(KEY_FINDINGS))
    vso = [l for l in capsys.readouterr().out.splitlines() if l.startswith("##vso[")]
    assert exit_code == 0
    assert vso[0] == (
        "##vso[task.logissue type=error;sourcepath=src/app.py;linenumber=6]"
        "Mahdollinen salaisuus: ArcGIS API Key, Secret Keyword"
    )
    assert vso[-1].startswith("##vso[task.complete result=Failed;]")
