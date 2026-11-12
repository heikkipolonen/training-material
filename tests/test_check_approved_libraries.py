"""Tests for the approved-library checker.

Each test writes small input files into pytest's temporary directory
(``tmp_path``), runs the checker against them and verifies the outcome.
"""

from __future__ import annotations

from datetime import date
import json

import pytest

from check_approved_libraries import (
    load_policy,
    main,
    normalize_package_name,
    read_direct_dependencies,
    run_check,
)

TODAY = date(2026, 11, 12)

POLICY_YAML = """\
approved:
  - name: arcgis
    approved_by: training-security-team
    approved_on: 2026-11-01
    reason: Esri ArcGIS API for Python
exceptions:
  - name: temporary-package
    ticket: SEC-123
    approved_by: training-security-team
    expires: 2026-12-31
    reason: Short-term exception for training purposes
  - name: expired-package
    ticket: SEC-100
    approved_by: training-security-team
    expires: 2026-01-31
    reason: This exception has already expired
"""


@pytest.fixture
def policy_file(tmp_path):
    path = tmp_path / "approved-libraries.yml"
    path.write_text(POLICY_YAML, encoding="utf-8")
    return path


def write_requirements(tmp_path, content: str, name: str = "requirements.txt"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


# --- Package name normalization -------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("arcgis", "arcgis"),
        ("ArcGIS", "arcgis"),
        ("my_package", "my-package"),
        ("my.package", "my-package"),
        ("My__Package", "my-package"),
    ],
)
def test_normalize_package_name(raw, expected):
    assert normalize_package_name(raw) == expected


# --- Reading requirements.txt ---------------------------------------------


def test_comments_and_blank_lines_are_ignored(tmp_path):
    path = write_requirements(tmp_path, "# comment\n\narcgis\n   \n# other==1.0\n")
    assert read_direct_dependencies(path) == ["arcgis"]


def test_version_specifiers_extras_and_markers_are_stripped(tmp_path):
    path = write_requirements(
        tmp_path,
        "arcgis==2.4.0\n"
        "Requests[security]>=2.0\n"
        "pywin32; sys_platform == 'win32'\n",
    )
    assert read_direct_dependencies(path) == ["arcgis", "requests", "pywin32"]


def test_inline_comment_is_ignored(tmp_path):
    path = write_requirements(tmp_path, "arcgis  # GIS library\n")
    assert read_direct_dependencies(path) == ["arcgis"]


@pytest.mark.parametrize(
    "line",
    [
        # Approved name, but the package is downloaded from an arbitrary URL.
        "arcgis @ https://evil.example/arcgis-9.9-py3-none-any.whl",
        # Package installed directly from a version control system.
        "git+https://github.com/example/arcgis.git",
        # A local file or directory.
        "./local-package",
        # pip options can change the package source or pull in other files.
        "--extra-index-url https://evil.example/simple",
        "-r other-requirements.txt",
        "-e .",
    ],
)
def test_lines_that_bypass_the_package_index_are_rejected(tmp_path, line):
    path = write_requirements(tmp_path, f"{line}\n")
    with pytest.raises(ValueError):
        read_direct_dependencies(path)


# --- Loading the policy file ------------------------------------------------


def test_policy_lists_approved_libraries_and_exceptions(policy_file):
    policy = load_policy(policy_file)
    assert policy.approved == {"arcgis"}
    assert set(policy.exceptions) == {"temporary-package", "expired-package"}
    assert policy.exceptions["temporary-package"].expires == date(2026, 12, 31)
    assert policy.exceptions["temporary-package"].ticket == "SEC-123"


def test_policy_names_are_normalized(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("approved:\n  - name: My_Package\n", encoding="utf-8")
    assert load_policy(path).approved == {"my-package"}


def test_exception_without_expiry_date_is_invalid(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text(
        "approved: []\nexceptions:\n  - name: forever\n    ticket: SEC-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expires"):
        load_policy(path)


def test_policy_without_approved_list_is_invalid(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("something_else: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="approved"):
        load_policy(path)


# --- The whole check ------------------------------------------------------


def test_only_approved_libraries_are_accepted(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYVAKSYTTY"
    assert report["exit_code"] == 0
    assert report["dependencies"] == {str(requirements): ["arcgis"]}
    assert report["unknown_libraries"] == []


def test_all_requirement_files_are_checked(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\n")
    dev_requirements = write_requirements(
        tmp_path, "unknown-dev-tool\n", name="requirements-dev.txt"
    )
    report = run_check([requirements, dev_requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["unknown_libraries"] == ["unknown-dev-tool"]
    assert report["dependencies"] == {
        str(requirements): ["arcgis"],
        str(dev_requirements): ["unknown-dev-tool"],
    }


def test_missing_second_requirements_file_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\n")
    report = run_check(
        [requirements, tmp_path / "requirements-dev.txt"], policy_file, TODAY
    )
    assert report["result"] == "HYLATTY"
    assert "requirements-dev.txt" in report["error"]


def test_unknown_library_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(
        tmp_path, "arcgis\nunknown-demo-package==1.0.0\n"
    )
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1
    assert report["unknown_libraries"] == ["unknown-demo-package"]


def test_valid_exception_is_accepted_and_reported(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\ntemporary-package\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYVAKSYTTY"
    assert report["exceptions_used"] == [
        {"name": "temporary-package", "ticket": "SEC-123", "expires": "2026-12-31"}
    ]


def test_exception_is_valid_on_its_expiry_date(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "temporary-package\n")
    report = run_check([requirements], policy_file, date(2026, 12, 31))
    assert report["result"] == "HYVAKSYTTY"


def test_expired_exception_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\nexpired-package\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["expired_exceptions"] == [
        {"name": "expired-package", "ticket": "SEC-100", "expires": "2026-01-31"}
    ]


def test_missing_requirements_file_is_rejected(tmp_path, policy_file):
    report = run_check([tmp_path / "missing.txt"], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert "missing.txt" in report["error"]


def test_missing_policy_file_is_rejected(tmp_path):
    requirements = write_requirements(tmp_path, "arcgis\n")
    report = run_check([requirements], tmp_path / "missing.yml", TODAY)
    assert report["result"] == "HYLATTY"
    assert "missing.yml" in report["error"]


def test_url_dependency_is_rejected_even_for_approved_name(tmp_path, policy_file):
    requirements = write_requirements(
        tmp_path, "arcgis @ https://evil.example/arcgis-9.9-py3-none-any.whl\n"
    )
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1


# --- Reports written by main() ------------------------------------------------


def test_main_writes_text_and_json_reports(tmp_path, policy_file, monkeypatch):
    write_requirements(tmp_path, "arcgis\nunknown-demo-package\n")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--requirements", "requirements.txt",
            "--policy", str(policy_file),
            "--output-dir", "artifacts",
        ]
    )

    assert exit_code == 1
    text = (tmp_path / "artifacts/approved-libraries-report.txt").read_text("utf-8")
    data = json.loads(
        (tmp_path / "artifacts/approved-libraries-report.json").read_text("utf-8")
    )
    assert "TULOS: HYLATTY" in text
    assert "TUNTEMATTOMAT_KIRJASTOT: unknown-demo-package" in text
    # Every line in the text report is unique (no duplicated information).
    lines = text.splitlines()
    assert len(lines) == len(set(lines))
    assert data["result"] == "HYLATTY"
    assert data["unknown_libraries"] == ["unknown-demo-package"]


def test_main_checks_project_and_dev_requirements_by_default(
    tmp_path, policy_file, monkeypatch
):
    write_requirements(tmp_path, "arcgis\n")
    write_requirements(tmp_path, "unknown-dev-tool\n", name="requirements-dev.txt")
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy/approved-libraries.yml").write_text(
        policy_file.read_text("utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    assert exit_code == 1
    text = (tmp_path / "artifacts/approved-libraries-report.txt").read_text("utf-8")
    assert "SUORAT_RIIPPUVUUDET (requirements.txt): arcgis" in text
    assert "SUORAT_RIIPPUVUUDET (requirements-dev.txt): unknown-dev-tool" in text
    assert "TUNTEMATTOMAT_KIRJASTOT: unknown-dev-tool" in text
