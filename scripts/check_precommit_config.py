"""Tarkasta, että .pre-commit-config.yaml käyttää vain paikallisia hookeja.

Linjaus: hookit ovat koodia, joka ajetaan jokaisen kehittäjän koneella. Siksi
sallitaan vain tämän repositorion omat hookit (`repo: local`), jotka
katselmoidaan PR:ssä kuten muukin koodi. Kolmannen osapuolen hook-repositoriot
hylätään.

Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from azure_devops import failure_commands

DEFAULT_CONFIG_FILE = Path(".pre-commit-config.yaml")
ALLOWED_REPOS = {"local"}
REMEDIATION = "Käytä vain paikallisia hookeja (repo: local)."


def check_config(path: Path) -> list[str]:
    """Palauta löydetyt ongelmat. Tyhjä lista tarkoittaa hyväksyttyä tiedostoa."""
    if not path.exists():
        return []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return [f"{path}: YAML on virheellinen: {error}"]

    if not isinstance(data, dict) or not isinstance(data.get("repos"), list):
        return [f"{path}: lista 'repos' puuttuu"]

    problems: list[str] = []
    for entry in data["repos"]:
        if not isinstance(entry, dict) or "repo" not in entry:
            problems.append(f"{path}: repos-listan kohdasta puuttuu 'repo': {entry}")
        elif entry["repo"] not in ALLOWED_REPOS:
            problems.append(
                f"Kolmannen osapuolen hook-repositorio ei ole sallittu: {entry['repo']}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä hylkäyksen syyt Azure DevOpsin PR-näkymässä (exit-koodi 0).",
    )
    args = parser.parse_args(argv)

    problems = check_config(args.config)
    print("TARKASTUS: pre-commit-hookien alkuperä")
    print(f"TULOS: {'HYLATTY' if problems else 'HYVAKSYTTY'}")
    for problem in problems:
        print(f"SYY: {problem}")
    if problems:
        print(f"KORJAUSOHJE: {REMEDIATION}")

    if args.azure_devops:
        if problems:
            commands = failure_commands(
                [*problems, f"Korjausohje: {REMEDIATION}"],
                "Tarkastus hylkäsi pre-commit-asetukset",
            )
            print("\n".join(commands))
        return 0
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
