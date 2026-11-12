"""Azure DevOpsin logging-komennot tarkastusskripteille.

`task.logissue`-rivit näkyvät pipeline-ajon ja PR:n tarkastuksen yhteenvedossa.
`task.complete result=Failed` merkitsee taskin epäonnistuneeksi ilman
geneeristä "Bash exited with code '1'" -viestiä.

https://learn.microsoft.com/azure/devops/pipelines/scripts/logging-commands
"""

from __future__ import annotations


def _escape(message: str) -> str:
    """Koodaa merkit, joilla on erityismerkitys logging-komennoissa."""
    return message.replace("%", "%AZP25").replace("\r", "%0D").replace("\n", "%0A")


def failure_commands(errors: list[str], summary: str) -> list[str]:
    """Palauta virheriveistä logging-komennot, jotka hylkäävät taskin."""
    commands = [f"##vso[task.logissue type=error]{_escape(error)}" for error in errors]
    commands.append(f"##vso[task.complete result=Failed;]{_escape(summary)}")
    return commands
