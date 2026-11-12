"""Tests for the approved-library checker.

Each test writes small input files into pytest's temporary directory
(``tmp_path``), runs the checker against them and verifies the outcome.
"""

from __future__ import annotations

from datetime import date
import json

import pytest

from check_approved_libraries import (
    Requirement,
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
    versions: ["2.4.4"]
    approved_by: training-security-team
    approved_on: 2026-11-01
    reason: Esri ArcGIS API for Python
  - name: pytest
    versions: ["9.1.1"]
    approved_by: training-security-team
    approved_on: 2026-11-01
    reason: Testing
exceptions:
  - name: temporary-package
    versions: ["1.0.0"]
    ticket: SEC-123
    approved_by: training-security-team
    expires: 2026-12-31
    reason: Short-term exception for training purposes
  - name: expired-package
    versions: ["1.0.0"]
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


def write_policy(tmp_path, content: str):
    path = tmp_path / "policy.yml"
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
    path = write_requirements(
        tmp_path, "# comment\n\narcgis==2.4.4\n   \n# other==1.0\n"
    )
    assert read_direct_dependencies(path) == [Requirement("arcgis", "2.4.4")]


def test_exact_version_is_read_with_extras_and_markers(tmp_path):
    path = write_requirements(
        tmp_path,
        "arcgis==2.4.4\n"
        "Requests[security]==2.32.3\n"
        "pywin32==312 ; sys_platform == 'win32'\n",
    )
    assert read_direct_dependencies(path) == [
        Requirement("arcgis", "2.4.4"),
        Requirement("requests", "2.32.3"),
        Requirement("pywin32", "312"),
    ]


def test_inline_comment_is_ignored(tmp_path):
    path = write_requirements(tmp_path, "arcgis==2.4.4  # GIS library\n")
    assert read_direct_dependencies(path) == [Requirement("arcgis", "2.4.4")]


@pytest.mark.parametrize(
    "line",
    [
        "arcgis",            # no version at all
        "arcgis>=2.4",       # a range, not an exact version
        "arcgis~=2.4",
        "arcgis==2.*",       # wildcard
        "arcgis==2.4.4,<3",  # more than one specifier
    ],
)
def test_anything_but_an_exact_version_is_unpinned(tmp_path, line):
    path = write_requirements(tmp_path, f"{line}\n")
    assert read_direct_dependencies(path) == [Requirement("arcgis", None)]


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


def test_policy_lists_approved_versions_and_exceptions(policy_file):
    policy = load_policy(policy_file)
    assert policy.approved == {"arcgis": {"2.4.4"}, "pytest": {"9.1.1"}}
    assert set(policy.exceptions) == {"temporary-package", "expired-package"}
    exception = policy.exceptions["temporary-package"]
    assert exception.expires == date(2026, 12, 31)
    assert exception.ticket == "SEC-123"
    assert exception.versions == {"1.0.0"}


def test_policy_names_are_normalized(tmp_path):
    path = write_policy(tmp_path, 'approved:\n  - name: My_Package\n    versions: ["1.0"]\n')
    assert load_policy(path).approved == {"my-package": {"1.0"}}


def test_approved_library_without_versions_is_invalid(tmp_path):
    path = write_policy(tmp_path, "approved:\n  - name: arcgis\n")
    with pytest.raises(ValueError, match="versions"):
        load_policy(path)


def test_version_written_as_number_is_invalid(tmp_path):
    # YAML reads 1.10 as the number 1.1, which would silently approve the
    # wrong version. Versions must be quoted strings.
    path = write_policy(tmp_path, "approved:\n  - name: arcgis\n    versions: [1.10]\n")
    with pytest.raises(ValueError, match="lainausmerk"):
        load_policy(path)


def test_exception_without_versions_is_invalid(tmp_path):
    path = write_policy(
        tmp_path,
        "approved: []\nexceptions:\n"
        "  - name: x\n    ticket: SEC-1\n    expires: 2026-12-31\n",
    )
    with pytest.raises(ValueError, match="versions"):
        load_policy(path)


def test_exception_without_expiry_date_is_invalid(tmp_path):
    path = write_policy(
        tmp_path,
        'approved: []\nexceptions:\n'
        '  - name: forever\n    versions: ["1.0"]\n    ticket: SEC-1\n',
    )
    with pytest.raises(ValueError, match="expires"):
        load_policy(path)


def test_policy_without_approved_list_is_invalid(tmp_path):
    path = write_policy(tmp_path, "something_else: true\n")
    with pytest.raises(ValueError, match="approved"):
        load_policy(path)


# --- The whole check ------------------------------------------------------


def test_approved_version_is_accepted(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis==2.4.4\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYVAKSYTTY"
    assert report["exit_code"] == 0
    assert report["dependencies"] == {str(requirements): ["arcgis==2.4.4"]}
    assert report["unknown_libraries"] == []


def test_unpinned_library_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["unpinned_libraries"] == ["arcgis"]
    assert report["dependencies"] == {str(requirements): ["arcgis"]}


def test_unapproved_version_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis==2.5.0\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["unapproved_versions"] == [
        {"name": "arcgis", "version": "2.5.0", "approved_versions": ["2.4.4"]}
    ]


def test_all_requirement_files_are_checked(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis==2.4.4\n")
    dev_requirements = write_requirements(
        tmp_path, "unknown-dev-tool==1.0\n", name="requirements-dev.txt"
    )
    report = run_check([requirements, dev_requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["unknown_libraries"] == ["unknown-dev-tool"]
    assert report["dependencies"] == {
        str(requirements): ["arcgis==2.4.4"],
        str(dev_requirements): ["unknown-dev-tool==1.0"],
    }


def test_missing_second_requirements_file_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "arcgis==2.4.4\n")
    report = run_check(
        [requirements, tmp_path / "requirements-dev.txt"], policy_file, TODAY
    )
    assert report["result"] == "HYLATTY"
    assert "requirements-dev.txt" in report["error"]


def test_unknown_library_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(
        tmp_path, "arcgis==2.4.4\nunknown-demo-package==1.0.0\n"
    )
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["exit_code"] == 1
    assert report["unknown_libraries"] == ["unknown-demo-package"]


def test_valid_exception_is_accepted_and_reported(tmp_path, policy_file):
    requirements = write_requirements(
        tmp_path, "arcgis==2.4.4\ntemporary-package==1.0.0\n"
    )
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYVAKSYTTY"
    assert report["exceptions_used"] == [
        {"name": "temporary-package", "ticket": "SEC-123", "expires": "2026-12-31"}
    ]


def test_exception_covers_only_its_versions(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "temporary-package==2.0.0\n")
    report = run_check([requirements], policy_file, TODAY)
    assert report["result"] == "HYLATTY"
    assert report["unapproved_versions"] == [
        {"name": "temporary-package", "version": "2.0.0", "approved_versions": ["1.0.0"]}
    ]


def test_exception_is_valid_on_its_expiry_date(tmp_path, policy_file):
    requirements = write_requirements(tmp_path, "temporary-package==1.0.0\n")
    report = run_check([requirements], policy_file, date(2026, 12, 31))
    assert report["result"] == "HYVAKSYTTY"


def test_expired_exception_is_rejected(tmp_path, policy_file):
    requirements = write_requirements(
        tmp_path, "arcgis==2.4.4\nexpired-package==1.0.0\n"
    )
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
    requirements = write_requirements(tmp_path, "arcgis==2.4.4\n")
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
    write_requirements(
        tmp_path, "arcgis==2.5.0\nunknown-demo-package==1.0.0\npytest\n"
    )
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
    assert "LUKITSEMATTOMAT_VERSIOT: pytest" in text
    assert "HYVAKSYMATTOMAT_VERSIOT: arcgis==2.5.0" in text
    # Every line in the text report is unique (no duplicated information).
    lines = text.splitlines()
    assert len(lines) == len(set(lines))
    assert data["result"] == "HYLATTY"
    assert data["unknown_libraries"] == ["unknown-demo-package"]


def test_main_checks_all_default_requirement_files(tmp_path, policy_file, monkeypatch):
    write_requirements(tmp_path, "arcgis==2.4.4\n")
    write_requirements(tmp_path, "unknown-dev-tool==1.0\n", name="requirements-dev.txt")
    write_requirements(tmp_path, "arcgis==2.4.4\n", name="requirements-bootstrap.txt")
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy/approved-libraries.yml").write_text(
        policy_file.read_text("utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    assert exit_code == 1
    text = (tmp_path / "artifacts/approved-libraries-report.txt").read_text("utf-8")
    assert "SUORAT_RIIPPUVUUDET (requirements.txt): arcgis==2.4.4" in text
    assert "SUORAT_RIIPPUVUUDET (requirements-dev.txt): unknown-dev-tool==1.0" in text
    assert "SUORAT_RIIPPUVUUDET (requirements-bootstrap.txt): arcgis==2.4.4" in text
    assert "TUNTEMATTOMAT_KIRJASTOT: unknown-dev-tool" in text


# --- Azure DevOps output (--azure-devops) -------------------------------------


def vso_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("##vso[")]


def run_main_in(tmp_path, policy_file, monkeypatch, requirements: str, *extra):
    write_requirements(tmp_path, requirements)
    monkeypatch.chdir(tmp_path)
    return main(
        ["--requirements", "requirements.txt", "--policy", str(policy_file), *extra]
    )


def test_azure_devops_rejection_is_shown_as_readable_errors(
    tmp_path, policy_file, monkeypatch, capsys
):
    exit_code = run_main_in(
        tmp_path, policy_file, monkeypatch,
        "arcgis==2.4.4\nunknown-demo-package==1.0.0\nexpired-package==1.0.0\n",
        "--azure-devops",
    )

    lines = vso_lines(capsys.readouterr().out)
    assert lines == [
        "##vso[task.logissue type=error]Hyväksymätön kirjasto: "
        "unknown-demo-package (requirements.txt)",
        "##vso[task.logissue type=error]Poikkeus vanhentunut 2026-01-31: "
        "expired-package (requirements.txt, SEC-100)",
        "##vso[task.logissue type=error]Korjausohje: Poista riippuvuus tai "
        "dokumentoi ja hyväksytä poikkeus (policy/approved-libraries.yml) ennen mergeä.",
        "##vso[task.complete result=Failed;]Tarkastus hylkäsi riippuvuudet",
    ]
    # The task is failed via task.complete, so no generic "exited with code 1".
    assert exit_code == 0


def test_azure_devops_shows_version_problems(tmp_path, policy_file, monkeypatch, capsys):
    run_main_in(
        tmp_path, policy_file, monkeypatch,
        "arcgis==2.5.0\npytest\n",
        "--azure-devops",
    )

    lines = vso_lines(capsys.readouterr().out)
    assert (
        "##vso[task.logissue type=error]Versiota ei ole lukittu: pytest "
        "(requirements.txt). Käytä muotoa pytest==X.Y.Z"
    ) in lines
    assert (
        "##vso[task.logissue type=error]Versiota ei ole hyväksytty: arcgis==2.5.0 "
        "(requirements.txt). Hyväksytyt versiot: 2.4.4"
    ) in lines


def test_azure_devops_check_error_is_shown_as_readable_error(
    tmp_path, policy_file, monkeypatch, capsys
):
    exit_code = run_main_in(
        tmp_path, policy_file, monkeypatch,
        "arcgis @ https://evil.example/arcgis.whl\n",
        "--azure-devops",
    )

    lines = vso_lines(capsys.readouterr().out)
    assert lines[0].startswith("##vso[task.logissue type=error]requirements.txt: ")
    assert "URL- tai VCS-viittaus" in lines[0]
    assert lines[-1].startswith("##vso[task.complete result=Failed;]")
    assert exit_code == 0


def test_azure_devops_approved_check_prints_no_commands(
    tmp_path, policy_file, monkeypatch, capsys
):
    exit_code = run_main_in(
        tmp_path, policy_file, monkeypatch, "arcgis==2.4.4\n", "--azure-devops"
    )
    assert vso_lines(capsys.readouterr().out) == []
    assert exit_code == 0


def test_without_azure_devops_flag_rejection_uses_exit_code(
    tmp_path, policy_file, monkeypatch, capsys
):
    exit_code = run_main_in(
        tmp_path, policy_file, monkeypatch, "unknown-demo-package==1.0.0\n"
    )
    assert vso_lines(capsys.readouterr().out) == []
    assert exit_code == 1
