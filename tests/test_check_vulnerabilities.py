"""Tests for the vulnerability scan.

The real scan runs pip-audit, which needs network access. These tests replace
it with a fake that returns known findings, so they test only our own logic:
which packages are scanned, exceptions, and the reports.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from check_vulnerabilities import (
    load_exceptions,
    main,
    read_pins,
    run_scan,
    split_unique,
)

TODAY = date(2026, 11, 12)

LOCK = """\
numpy==2.4.6 ; python_full_version < '3.12' \\
    --hash=sha256:aaa
    # via arcgis
numpy==2.5.4 ; python_full_version >= '3.12' \\
    --hash=sha256:bbb
    # via arcgis
pywin32==312 ; sys_platform == 'win32' \\
    --hash=sha256:ccc
requests==2.31.0 \\
    --hash=sha256:ddd
"""

REQUESTS_VULN = {
    "name": "requests",
    "version": "2.31.0",
    "id": "PYSEC-2026-1873",
    "aliases": ["CVE-2024-35195", "GHSA-9wx4-h78v-vm56"],
    "fix_versions": ["2.32.0"],
}

EXCEPTIONS_YAML = """\
vulnerability_exceptions:
  - id: CVE-2024-35195
    ticket: SEC-200
    expires: 2026-12-31
    reason: Accepted for training
  - id: PYSEC-OLD-1
    ticket: SEC-100
    expires: 2026-01-31
    reason: Already expired
"""


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def lock_file(tmp_path):
    return write(tmp_path / "requirements.lock.txt", LOCK)


@pytest.fixture
def no_exceptions(tmp_path):
    return write(tmp_path / "vulnerability-exceptions.yml", "vulnerability_exceptions: []\n")


@pytest.fixture
def exceptions_file(tmp_path):
    return write(tmp_path / "vulnerability-exceptions.yml", EXCEPTIONS_YAML)


def fake_audit(findings: list[dict]):
    """Return an audit function that reports the given findings and records calls."""
    calls: list[list[tuple[str, str]]] = []

    def audit(pins: list[tuple[str, str]]) -> list[dict]:
        calls.append(pins)
        return [f for f in findings if (f["name"], f["version"]) in pins]

    audit.calls = calls  # type: ignore[attr-defined]
    return audit


# --- Which packages are scanned --------------------------------------------


def test_every_lock_entry_is_scanned_regardless_of_platform(lock_file):
    # pip-audit on its own skips entries whose condition does not match the
    # machine it runs on (e.g. pywin32 on Linux). We read them all ourselves.
    pins = read_pins([lock_file])
    assert set(pins) == {
        ("numpy", "2.4.6"),
        ("numpy", "2.5.4"),
        ("pywin32", "312"),
        ("requests", "2.31.0"),
    }
    assert pins[("pywin32", "312")] == ["requirements.lock.txt"]


def test_same_package_in_several_lock_files_is_scanned_once(tmp_path, lock_file):
    dev_lock = write(tmp_path / "requirements-dev.lock.txt", "requests==2.31.0 \\\n    --hash=sha256:ddd\n")
    pins = read_pins([lock_file, dev_lock])
    assert pins[("requests", "2.31.0")] == ["requirements.lock.txt", "requirements-dev.lock.txt"]


def test_split_unique_puts_each_package_only_once_per_group():
    # pip-audit refuses a list that contains the same package twice.
    groups = split_unique([("numpy", "2.4.6"), ("numpy", "2.5.4"), ("requests", "2.31.0")])
    assert groups == [[("numpy", "2.4.6"), ("requests", "2.31.0")], [("numpy", "2.5.4")]]


def test_scan_audits_all_packages_in_unique_groups(lock_file, no_exceptions):
    audit = fake_audit([])
    report = run_scan([lock_file], no_exceptions, TODAY, audit)
    audited = [pin for call in audit.calls for pin in call]
    assert sorted(audited) == sorted(read_pins([lock_file]))
    for call in audit.calls:
        names = [name for name, _ in call]
        assert len(names) == len(set(names))
    assert report["scanned_packages"] == 4


# --- Results ------------------------------------------------------------------


def test_no_vulnerabilities_is_accepted(lock_file, no_exceptions):
    report = run_scan([lock_file], no_exceptions, TODAY, fake_audit([]))
    assert report["result"] == "HYVAKSYTTY"
    assert report["exit_code"] == 0
    assert report["vulnerabilities"] == []


def test_vulnerability_is_rejected(lock_file, no_exceptions):
    report = run_scan([lock_file], no_exceptions, TODAY, fake_audit([REQUESTS_VULN]))
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1
    assert report["vulnerabilities"] == [
        {**REQUESTS_VULN, "files": ["requirements.lock.txt"]}
    ]


def test_duplicate_findings_are_reported_once(lock_file, no_exceptions):
    report = run_scan(
        [lock_file], no_exceptions, TODAY, fake_audit([REQUESTS_VULN, REQUESTS_VULN])
    )
    assert len(report["vulnerabilities"]) == 1


def test_audit_failure_is_rejected(lock_file, no_exceptions):
    def failing_audit(pins):
        raise RuntimeError("pip-audit epäonnistui: network error")

    report = run_scan([lock_file], no_exceptions, TODAY, failing_audit)
    assert report["result"] == "HYLATTY"
    assert "network error" in report["error"]


def test_missing_lock_file_is_rejected(tmp_path, no_exceptions):
    report = run_scan([tmp_path / "missing.lock.txt"], no_exceptions, TODAY, fake_audit([]))
    assert report["result"] == "HYLATTY"
    assert "missing.lock.txt" in report["error"]


# --- Exceptions -------------------------------------------------------------


def test_exception_can_name_an_alias(lock_file, exceptions_file):
    # The exception says CVE-2024-35195; pip-audit reports PYSEC-2026-1873
    # with the CVE as an alias.
    report = run_scan([lock_file], exceptions_file, TODAY, fake_audit([REQUESTS_VULN]))
    assert report["result"] == "HYVAKSYTTY"
    assert report["vulnerabilities"] == []
    assert report["accepted_vulnerabilities"] == [
        {"name": "requests", "version": "2.31.0", "id": "PYSEC-2026-1873",
         "ticket": "SEC-200", "expires": "2026-12-31"}
    ]


def test_exception_can_name_the_main_id(lock_file, tmp_path):
    exceptions = write(
        tmp_path / "exc.yml",
        "vulnerability_exceptions:\n"
        "  - id: PYSEC-2026-1873\n    ticket: SEC-1\n    expires: 2026-12-31\n",
    )
    report = run_scan([lock_file], exceptions, TODAY, fake_audit([REQUESTS_VULN]))
    assert report["result"] == "HYVAKSYTTY"


def test_expired_exception_is_rejected(lock_file, exceptions_file):
    old_vuln = {**REQUESTS_VULN, "id": "PYSEC-OLD-1", "aliases": []}
    report = run_scan([lock_file], exceptions_file, TODAY, fake_audit([old_vuln]))
    assert report["result"] == "HYLATTY"
    assert report["expired_exceptions"] == [
        {"name": "requests", "version": "2.31.0", "id": "PYSEC-OLD-1",
         "ticket": "SEC-100", "expires": "2026-01-31"}
    ]


def test_missing_exceptions_file_means_no_exceptions(tmp_path):
    assert load_exceptions(tmp_path / "missing.yml") == []


@pytest.mark.parametrize("missing", ["ticket", "expires"])
def test_exception_without_required_field_is_invalid(tmp_path, missing):
    fields = {"id": "CVE-1", "ticket": "SEC-1", "expires": "2026-12-31"}
    del fields[missing]
    body = "".join(f"    {k}: {v}\n" for k, v in fields.items()).replace("    id", "  - id", 1)
    path = write(tmp_path / "exc.yml", "vulnerability_exceptions:\n" + body)
    with pytest.raises(ValueError, match=missing):
        load_exceptions(path)


# --- main() ---------------------------------------------------------------


def test_main_writes_text_and_json_reports(tmp_path, lock_file, no_exceptions, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        ["--lock", str(lock_file), "--policy", str(no_exceptions), "--output-dir", "artifacts"],
        audit=fake_audit([REQUESTS_VULN]),
    )
    assert exit_code == 1
    text = (tmp_path / "artifacts/vulnerability-report.txt").read_text("utf-8")
    data = json.loads((tmp_path / "artifacts/vulnerability-report.json").read_text("utf-8"))
    assert "TULOS: HYLATTY" in text
    assert "TARKASTETUT_PAKETIT: 4" in text
    assert (
        "HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-1873 (CVE-2024-35195, "
        "GHSA-9wx4-h78v-vm56), korjattu versiossa 2.32.0"
    ) in text
    assert data["vulnerabilities"][0]["id"] == "PYSEC-2026-1873"


def test_main_azure_devops(tmp_path, lock_file, no_exceptions, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        ["--lock", str(lock_file), "--policy", str(no_exceptions), "--azure-devops"],
        audit=fake_audit([REQUESTS_VULN]),
    )
    vso = [l for l in capsys.readouterr().out.splitlines() if l.startswith("##vso[")]
    assert exit_code == 0
    assert vso[0] == (
        "##vso[task.logissue type=error]Haavoittuvuus: requests==2.31.0 PYSEC-2026-1873 "
        "(CVE-2024-35195, GHSA-9wx4-h78v-vm56), korjattu versiossa 2.32.0 "
        "(requirements.lock.txt)"
    )
    assert vso[-1].startswith("##vso[task.complete result=Failed;]")


def test_main_passes_when_clean(tmp_path, lock_file, no_exceptions, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        ["--lock", str(lock_file), "--policy", str(no_exceptions)], audit=fake_audit([])
    )
    assert exit_code == 0
    assert "TULOS: HYVAKSYTTY" in capsys.readouterr().out
