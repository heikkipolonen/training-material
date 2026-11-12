"""Tests for the rule "only local pre-commit hooks are allowed"."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_precommit_config import check_config, main

REPO_ROOT = Path(__file__).parent.parent

LOCAL_ONLY = """\
repos:
  - repo: local
    hooks:
      - id: approved-libraries
        name: Approved libraries
        language: python
        entry: python scripts/check_approved_libraries.py
"""

WITH_THIRD_PARTY = """\
repos:
  - repo: local
    hooks:
      - id: approved-libraries
        name: Approved libraries
        language: python
        entry: python scripts/check_approved_libraries.py
  - repo: https://github.com/example/some-hooks
    rev: v1.0.0
    hooks:
      - id: some-hook
"""


def write_config(tmp_path, content: str) -> Path:
    path = tmp_path / ".pre-commit-config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_local_hooks_are_allowed(tmp_path):
    assert check_config(write_config(tmp_path, LOCAL_ONLY)) == []


def test_third_party_hook_repository_is_rejected(tmp_path):
    problems = check_config(write_config(tmp_path, WITH_THIRD_PARTY))
    assert len(problems) == 1
    assert "https://github.com/example/some-hooks" in problems[0]


def test_missing_config_file_is_allowed(tmp_path):
    # No config means no hooks, so there is nothing to reject.
    assert check_config(tmp_path / ".pre-commit-config.yaml") == []


def test_invalid_yaml_is_rejected(tmp_path):
    problems = check_config(write_config(tmp_path, "repos: [unclosed\n"))
    assert len(problems) == 1
    assert "YAML" in problems[0]


@pytest.mark.parametrize(
    "content",
    [
        "something_else: true\n",
        "repos: not-a-list\n",
        "repos:\n  - hooks: []\n",  # entry without 'repo'
    ],
)
def test_unexpected_structure_is_rejected(tmp_path, content):
    assert check_config(write_config(tmp_path, content)) != []


def test_this_repositorys_own_config_follows_the_rule():
    assert check_config(REPO_ROOT / ".pre-commit-config.yaml") == []


# --- main() ---------------------------------------------------------------


def test_main_rejects_third_party_hooks_with_exit_code(tmp_path, capsys):
    path = write_config(tmp_path, WITH_THIRD_PARTY)
    exit_code = main(["--config", str(path)])
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "TULOS: HYLATTY" in output
    assert "https://github.com/example/some-hooks" in output


def test_main_accepts_local_hooks(tmp_path, capsys):
    path = write_config(tmp_path, LOCAL_ONLY)
    assert main(["--config", str(path)]) == 0
    assert "TULOS: HYVAKSYTTY" in capsys.readouterr().out


def test_main_azure_devops_shows_readable_error(tmp_path, capsys):
    path = write_config(tmp_path, WITH_THIRD_PARTY)
    exit_code = main(["--config", str(path), "--azure-devops"])
    vso = [l for l in capsys.readouterr().out.splitlines() if l.startswith("##vso[")]
    assert exit_code == 0
    assert vso[0].startswith("##vso[task.logissue type=error]")
    assert "https://github.com/example/some-hooks" in vso[0]
    assert vso[-1].startswith("##vso[task.complete result=Failed;]")
