"""Tests for the Azure DevOps logging commands."""

from __future__ import annotations

from azure_devops import failure_commands


def test_plain_errors_and_failed_task():
    assert failure_commands(["First", "Second"], "Summary") == [
        "##vso[task.logissue type=error]First",
        "##vso[task.logissue type=error]Second",
        "##vso[task.complete result=Failed;]Summary",
    ]


def test_error_can_point_to_a_file_and_line():
    # Azure DevOps shows these as annotations on the right line.
    assert failure_commands([("B105: hardcoded password", "src/app.py", 12)], "Summary") == [
        "##vso[task.logissue type=error;sourcepath=src/app.py;linenumber=12]"
        "B105: hardcoded password",
        "##vso[task.complete result=Failed;]Summary",
    ]


def test_special_characters_are_escaped():
    assert failure_commands(["100% done\nnext"], "ok")[0] == (
        "##vso[task.logissue type=error]100%AZP25 done%0Anext"
    )
