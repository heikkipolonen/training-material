"""Azure DevOpsin logging-komennot tarkastusskripteille.

`task.logissue`-rivit näkyvät pipeline-ajon ja PR:n tarkastuksen yhteenvedossa.
Jos virheellä on tiedosto ja rivi, Azure DevOps näyttää sen kyseisen rivin
kohdalla. `task.complete result=Failed` merkitsee taskin epäonnistuneeksi ilman
geneeristä "Bash exited with code '1'" -viestiä.

https://learn.microsoft.com/azure/devops/pipelines/scripts/logging-commands
"""

from __future__ import annotations

from typing import Union

# Virhe on joko pelkkä viesti tai (viesti, tiedosto, rivi).
Error = Union[str, tuple[str, str, int]]


def _escape(message: str) -> str:
    """Koodaa merkit, joilla on erityismerkitys logging-komennoissa."""
    return message.replace("%", "%AZP25").replace("\r", "%0D").replace("\n", "%0A")


def _issue(error: Error) -> str:
    if isinstance(error, tuple):
        message, sourcepath, linenumber = error
        return (
            f"##vso[task.logissue type=error;sourcepath={_escape(sourcepath)};"
            f"linenumber={linenumber}]{_escape(message)}"
        )
    return f"##vso[task.logissue type=error]{_escape(error)}"


def failure_commands(errors: list[Error], summary: str) -> list[str]:
    """Palauta virheriveistä logging-komennot, jotka hylkäävät taskin."""
    commands = [_issue(error) for error in errors]
    commands.append(f"##vso[task.complete result=Failed;]{_escape(summary)}")
    return commands
