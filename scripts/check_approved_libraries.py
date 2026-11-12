"""Tarkasta suorat riippuvuudet hyväksyttyjen kirjastojen rekisteriä vasten.

Oletuksena tarkastetaan sekä projektin (requirements.txt) että kehitystyökalujen
(requirements-dev.txt) riippuvuudet. Rekisteri luetaan tiedostosta
policy/approved-libraries.yml. Tarkastus tuottaa
kaksi raporttia samasta datasta:

- artifacts/approved-libraries-report.txt  (ihmisen luettava)
- artifacts/approved-libraries-report.json (koneluettava auditointievidenssi)

Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import yaml

from azure_devops import failure_commands

DEFAULT_REQUIREMENTS_FILES = [Path("requirements.txt"), Path("requirements-dev.txt")]
DEFAULT_POLICY_FILE = Path("policy/approved-libraries.yml")
DEFAULT_OUTPUT_DIR = Path("artifacts")
REPORT_BASENAME = "approved-libraries-report"

CHECK_NAME = "ArcGIS Python -projektin hyväksytyt kirjastot"
APPROVED = "HYVAKSYTTY"
REJECTED = "HYLATTY"

# PEP 508 -paketin nimi rivin alussa.
PACKAGE_NAME_PATTERN = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")
# Mitä nimen jälkeen saa tulla: extrat, versiorajaus, ympäristömerkki tai ei mitään.
ALLOWED_AFTER_NAME = re.compile(r"^(\s*$|\s*[\[<>=!~;])")
INLINE_COMMENT = re.compile(r"\s+#.*$")


@dataclass(frozen=True)
class PolicyException:
    name: str
    ticket: str
    expires: date


@dataclass(frozen=True)
class Policy:
    approved: set[str]
    exceptions: dict[str, PolicyException]


def normalize_package_name(name: str) -> str:
    """Normalisoi kirjainkoko sekä piste-, alaviiva- ja yhdysmerkkierot (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirement_line(line: str) -> str:
    """Palauta rivin paketin nimi tai nosta ValueError, jos rivi ei ole sallittu.

    Sallitaan vain pakettirekisteristä asennettavat nimetyt paketit. Hylätään
    rivit, jotka voivat ohittaa rekisterin: URL-viittaukset, VCS-osoitteet,
    paikalliset polut ja pip-optiot (esim. --extra-index-url, -r, -e).
    """
    if line.startswith("-"):
        raise ValueError(f"pip-optiot eivät ole sallittuja: {line}")

    requirement = line.split(";", 1)[0]
    if "@" in requirement or "://" in requirement:
        raise ValueError(f"URL- tai VCS-viittaus ei ole sallittu: {line}")

    match = PACKAGE_NAME_PATTERN.match(line)
    if not match or not ALLOWED_AFTER_NAME.match(line[match.end():]):
        raise ValueError(f"Riviä ei voitu tulkita paketin nimeksi: {line}")

    return normalize_package_name(match.group(1))


def read_direct_dependencies(path: Path) -> list[str]:
    """Lue aktiivisten requirements-rivien pakettien nimet."""
    dependencies: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = INLINE_COMMENT.sub("", raw_line).strip()
        if not line or line.startswith("#"):
            continue
        dependencies.append(parse_requirement_line(line))
    return dependencies


def _parse_date(value: Any, field: str, name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(
            f"Poikkeuksen '{name}' kentän '{field}' pitää olla päivämäärä (VVVV-KK-PP)"
        ) from None


def load_policy(path: Path) -> Policy:
    """Lue ja validoi hyväksyttyjen kirjastojen rekisteri YAML-tiedostosta."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Rekisterin YAML on virheellinen: {error}") from None

    if not isinstance(data, dict) or not isinstance(data.get("approved"), list):
        raise ValueError("Rekisteristä puuttuu lista 'approved'")

    approved: set[str] = set()
    for entry in data["approved"]:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise ValueError(f"Hyväksytyltä kirjastolta puuttuu 'name': {entry}")
        approved.add(normalize_package_name(str(entry["name"])))

    exceptions: dict[str, PolicyException] = {}
    for entry in data.get("exceptions") or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise ValueError(f"Poikkeukselta puuttuu 'name': {entry}")
        name = normalize_package_name(str(entry["name"]))
        for field in ("ticket", "expires"):
            if not entry.get(field):
                raise ValueError(f"Poikkeukselta '{name}' puuttuu '{field}'")
        exceptions[name] = PolicyException(
            name=name,
            ticket=str(entry["ticket"]),
            expires=_parse_date(entry["expires"], "expires", name),
        )

    return Policy(approved=approved, exceptions=exceptions)


def _exception_summary(exception: PolicyException) -> dict[str, str]:
    return {
        "name": exception.name,
        "ticket": exception.ticket,
        "expires": exception.expires.isoformat(),
    }


def run_check(
    requirements_paths: list[Path], policy_path: Path, today: date
) -> dict[str, Any]:
    """Suorita tarkastus kaikille requirements-tiedostoille ja palauta raporttidata."""
    report: dict[str, Any] = {
        "check": CHECK_NAME,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "requirements_files": [str(path) for path in requirements_paths],
        "policy_file": str(policy_path),
        "dependencies": {},
        "unknown_libraries": [],
        "exceptions_used": [],
        "expired_exceptions": [],
        "error": None,
    }

    def reject_with_error(message: str, remediation: str) -> dict[str, Any]:
        report.update(result=REJECTED, exit_code=1, error=message, remediation=remediation)
        return report

    for requirements_path in requirements_paths:
        if not requirements_path.exists():
            return reject_with_error(
                f"{requirements_path} puuttuu",
                f"Lisää {requirements_path.name} ja suorita tarkastus uudelleen.",
            )
    if not policy_path.exists():
        return reject_with_error(
            f"{policy_path} puuttuu",
            "Palauta hyväksyttyjen kirjastojen rekisteri ja suorita tarkastus uudelleen.",
        )

    try:
        policy = load_policy(policy_path)
    except ValueError as error:
        return reject_with_error(str(error), "Korjaa rekisteritiedoston virhe.")

    all_dependencies: set[str] = set()
    for requirements_path in requirements_paths:
        try:
            dependencies = read_direct_dependencies(requirements_path)
        except ValueError as error:
            return reject_with_error(
                f"{requirements_path}: {error}",
                "Käytä vain pakettirekisteristä asennettavia nimettyjä paketteja.",
            )
        report["dependencies"][str(requirements_path)] = dependencies
        all_dependencies.update(dependencies)

    for name in sorted(all_dependencies):
        if name in policy.approved:
            continue
        exception = policy.exceptions.get(name)
        if exception is None:
            report["unknown_libraries"].append(name)
        elif exception.expires >= today:
            report["exceptions_used"].append(_exception_summary(exception))
        else:
            report["expired_exceptions"].append(_exception_summary(exception))

    if report["unknown_libraries"] or report["expired_exceptions"]:
        report.update(
            result=REJECTED,
            exit_code=1,
            remediation=(
                "Poista riippuvuus tai dokumentoi ja hyväksytä poikkeus "
                "(policy/approved-libraries.yml) ennen mergeä."
            ),
        )
    else:
        report.update(result=APPROVED, exit_code=0, remediation="Ei korjaustarvetta.")
    return report


def _names(items: list[Any]) -> str:
    names = [item["name"] if isinstance(item, dict) else item for item in items]
    return ", ".join(names) or "ei ole"


def format_text_report(report: dict[str, Any]) -> str:
    """Muodosta ihmisen luettava raportti samasta datasta kuin JSON-raportti."""
    lines = [
        f"TARKASTUS: {report['check']}",
        f"AIKA_UTC: {report['timestamp_utc']}",
    ]
    if report["error"]:
        lines.append("SUORAT_RIIPPUVUUDET: ei voitu tarkastaa")
    for path, dependencies in report["dependencies"].items():
        names = ", ".join(dependencies) or "ei riippuvuuksia"
        lines.append(f"SUORAT_RIIPPUVUUDET ({Path(path).name}): {names}")
    lines.append(f"TULOS: {report['result']}")
    if report["error"]:
        lines.append(f"SYY: {report['error']}")
    else:
        lines.extend([
            f"TUNTEMATTOMAT_KIRJASTOT: {_names(report['unknown_libraries'])}",
            f"KAYTETYT_POIKKEUKSET: {_names(report['exceptions_used'])}",
            f"VANHENTUNEET_POIKKEUKSET: {_names(report['expired_exceptions'])}",
        ])
    lines.append(f"KORJAUSOHJE: {report['remediation']}")
    return "\n".join(lines) + "\n"


def _files_containing(report: dict[str, Any], name: str) -> str:
    files = [Path(path).name for path, deps in report["dependencies"].items() if name in deps]
    return ", ".join(files)


def format_azure_devops_commands(report: dict[str, Any]) -> list[str]:
    """Muodosta Azure DevOpsin logging-komennot hylätylle tarkastukselle."""
    if report["result"] == APPROVED:
        return []

    messages: list[str] = []
    if report["error"]:
        messages.append(report["error"])
    for name in report["unknown_libraries"]:
        messages.append(f"Hyväksymätön kirjasto: {name} ({_files_containing(report, name)})")
    for exception in report["expired_exceptions"]:
        messages.append(
            f"Poikkeus vanhentunut {exception['expires']}: {exception['name']} "
            f"({_files_containing(report, exception['name'])}, {exception['ticket']})"
        )
    messages.append(f"Korjausohje: {report['remediation']}")

    return failure_commands(messages, "Tarkastus hylkäsi riippuvuudet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--requirements",
        type=Path,
        action="append",
        help="Tarkastettava requirements-tiedosto. Voidaan antaa useita kertoja. "
        "Oletus: requirements.txt ja requirements-dev.txt.",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä hylkäyksen syyt Azure DevOpsin PR-näkymässä ja merkitse task "
        "epäonnistuneeksi logging-komennolla (exit-koodi 0).",
    )
    args = parser.parse_args(argv)

    requirements_paths = args.requirements or DEFAULT_REQUIREMENTS_FILES
    report = run_check(requirements_paths, args.policy, date.today())
    text = format_text_report(report)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / f"{REPORT_BASENAME}.txt").write_text(text, encoding="utf-8")
    (args.output_dir / f"{REPORT_BASENAME}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(text, end="")

    if args.azure_devops:
        for command in format_azure_devops_commands(report):
            print(command)
        return 0
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
