"""Tarkasta lukitustiedostojen paketit tunnettuja haavoittuvuuksia vasten.

Jokaisen lukitustiedoston jokainen paketti (myös transitiiviset) tarkastetaan
pip-auditilla julkisia haavoittuvuustietokantoja vasten. Mitään ei asenneta.

Pip-audit ohittaisi omin päin ne lukitustiedoston rivit, joiden ehto ei koske
konetta, jolla se ajetaan (esim. Windows-paketit Linux-pipelinessa). Siksi
tämä skripti lukee paketit itse ilman ehtoja ja antaa ne pip-auditille.

Tunnetun haavoittuvuuden voi hyväksyä määräaikaisesti tiedostossa
policy/vulnerability-exceptions.yml (tunniste, tiketti ja päättymispäivä).

Tarkastus tuottaa kaksi raporttia samasta datasta:

- artifacts/vulnerability-report.txt  (ihmisen luettava)
- artifacts/vulnerability-report.json (koneluettava auditointievidenssi)

Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
# pip-audit ajetaan kiinteällä komennolla ilman shelliä; ks. pip_audit.
import subprocess  # nosec B404
import sys
import tempfile
from typing import Any, Callable

import yaml

from azure_devops import failure_commands
from lock_files import LOCKS, parse_lock

DEFAULT_LOCK_FILES = [Path(lock.lock) for lock in LOCKS]
DEFAULT_POLICY_FILE = Path("policy/vulnerability-exceptions.yml")
DEFAULT_OUTPUT_DIR = Path("artifacts")
REPORT_BASENAME = "vulnerability-report"
APPROVED = "HYVAKSYTTY"
REJECTED = "HYLATTY"

Pin = tuple[str, str]  # (paketti, versio)
Audit = Callable[[list[Pin]], list[dict[str, Any]]]


@dataclass(frozen=True)
class VulnerabilityException:
    id: str
    ticket: str
    expires: date


def pip_audit(pins: list[Pin]) -> list[dict[str, Any]]:
    """Tarkasta paketit pip-auditilla. Mitään ei asenneta (--disable-pip)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        requirements = Path(temp_dir) / "pins.txt"
        requirements.write_text("".join(f"{n}=={v}\n" for n, v in pins), encoding="utf-8")
        # Kiinteä komento ilman shelliä; syötteenä on itse luotu väliaikaistiedosto.
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "pip_audit", "-r", str(requirements),
             "--disable-pip", "--no-deps", "--progress-spinner", "off", "-f", "json"],
            capture_output=True,
            text=True,
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"pip-audit epäonnistui: {result.stderr.strip()}") from None

    findings: list[dict[str, Any]] = []
    for dependency in data.get("dependencies", []):
        for vuln in dependency.get("vulns", []):
            findings.append({
                "name": dependency["name"],
                "version": dependency["version"],
                "id": vuln["id"],
                "aliases": sorted(vuln.get("aliases", [])),  # pip-audit ei järjestä näitä
                "fix_versions": vuln.get("fix_versions", []),
            })
    return findings


def read_pins(lock_paths: list[Path]) -> dict[Pin, list[str]]:
    """Lue kaikkien lukitustiedostojen paketit ilman ympäristöehtoja."""
    pins: dict[Pin, list[str]] = {}
    for path in lock_paths:
        entries = parse_lock(path.read_text(encoding="utf-8"))
        for (name, _marker), (version, _hashes) in entries.items():
            files = pins.setdefault((name, version), [])
            if path.name not in files:
                files.append(path.name)
    return pins


def split_unique(pins: list[Pin]) -> list[list[Pin]]:
    """Jaa paketit ryhmiin, joissa sama paketti on vain kerran.

    pip-audit ei hyväksy samaa pakettia kahdesti, mutta lukitustiedostossa voi
    olla saman paketin kaksi versiota eri Python-versioille.
    """
    groups: list[list[Pin]] = []
    for pin in pins:
        for group in groups:
            if all(name != pin[0] for name, _ in group):
                group.append(pin)
                break
        else:
            groups.append([pin])
    return groups


def load_exceptions(path: Path) -> list[VulnerabilityException]:
    """Lue hyväksytyt haavoittuvuuspoikkeukset. Puuttuva tiedosto = ei poikkeuksia."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"Poikkeustiedoston YAML on virheellinen: {error}") from None

    exceptions: list[VulnerabilityException] = []
    for entry in data.get("vulnerability_exceptions") or []:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ValueError(f"Poikkeukselta puuttuu 'id': {entry}")
        for field in ("ticket", "expires"):
            if not entry.get(field):
                raise ValueError(f"Poikkeukselta '{entry['id']}' puuttuu '{field}'")
        expires = entry["expires"]
        if not isinstance(expires, date):
            try:
                expires = date.fromisoformat(str(expires))
            except ValueError:
                raise ValueError(
                    f"Poikkeuksen '{entry['id']}' kentän 'expires' pitää olla päivämäärä"
                ) from None
        exceptions.append(
            VulnerabilityException(str(entry["id"]), str(entry["ticket"]), expires)
        )
    return exceptions


def run_scan(
    lock_paths: list[Path], policy_path: Path, today: date, audit: Audit
) -> dict[str, Any]:
    """Suorita tarkastus ja palauta tulos raporttidatana."""
    report: dict[str, Any] = {
        "check": "Tunnetut haavoittuvuudet",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "lock_files": [path.name for path in lock_paths],
        "policy_file": str(policy_path),
        "scanned_packages": 0,
        "vulnerabilities": [],
        "accepted_vulnerabilities": [],
        "expired_exceptions": [],
        "error": None,
    }

    def reject_with_error(message: str) -> dict[str, Any]:
        report.update(
            result=REJECTED, exit_code=1, error=message,
            remediation="Korjaa virhe ja aja tarkastus uudelleen.",
        )
        return report

    for path in lock_paths:
        if not path.exists():
            return reject_with_error(f"{path} puuttuu")
    try:
        exceptions = load_exceptions(policy_path)
        pins = read_pins(lock_paths)
    except ValueError as error:
        return reject_with_error(str(error))
    report["scanned_packages"] = len(pins)

    findings: dict[tuple[str, str, str], dict[str, Any]] = {}
    try:
        for group in split_unique(sorted(pins)):
            for finding in audit(group):
                key = (finding["name"], finding["version"], finding["id"])
                findings.setdefault(key, finding)  # pip-audit voi raportoida saman kahdesti
    except RuntimeError as error:
        return reject_with_error(str(error))

    for key in sorted(findings):
        finding = findings[key]
        ids = {finding["id"], *finding["aliases"]}
        exception = next((e for e in exceptions if e.id in ids), None)
        if exception is None:
            files = pins.get((finding["name"], finding["version"]), [])
            report["vulnerabilities"].append({**finding, "files": files})
            continue
        summary = {
            "name": finding["name"], "version": finding["version"], "id": finding["id"],
            "ticket": exception.ticket, "expires": exception.expires.isoformat(),
        }
        if exception.expires >= today:
            report["accepted_vulnerabilities"].append(summary)
        else:
            report["expired_exceptions"].append(summary)

    if report["vulnerabilities"] or report["expired_exceptions"]:
        report.update(
            result=REJECTED,
            exit_code=1,
            remediation=(
                "Päivitä haavoittuva paketti korjattuun versioon tai kirjaa "
                "määräaikainen poikkeus (policy/vulnerability-exceptions.yml)."
            ),
        )
    else:
        report.update(result=APPROVED, exit_code=0, remediation="Ei korjaustarvetta.")
    return report


def describe(finding: dict[str, Any]) -> str:
    text = f"{finding['name']}=={finding['version']} {finding['id']}"
    if finding["aliases"]:
        text += f" ({', '.join(finding['aliases'])})"
    if finding["fix_versions"]:
        text += f", korjattu versiossa {', '.join(finding['fix_versions'])}"
    else:
        text += ", korjattua versiota ei ole"
    return text


def _exception_line(item: dict[str, Any]) -> str:
    return (
        f"{item['name']}=={item['version']} {item['id']} "
        f"({item['ticket']}, voimassa {item['expires']} asti)"
    )


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        f"TARKASTUS: {report['check']}",
        f"AIKA_UTC: {report['timestamp_utc']}",
        f"LUKITUSTIEDOSTOT: {', '.join(report['lock_files'])}",
        f"TARKASTETUT_PAKETIT: {report['scanned_packages']}",
        f"TULOS: {report['result']}",
    ]
    if report["error"]:
        lines.append(f"SYY: {report['error']}")
    lines.extend(f"HAAVOITTUVUUS: {describe(v)}" for v in report["vulnerabilities"])
    if not report["error"] and not report["vulnerabilities"]:
        lines.append("HAAVOITTUVUUDET: ei ole")
    lines.extend(
        f"HYVAKSYTTY_POIKKEUKSELLA: {_exception_line(v)}"
        for v in report["accepted_vulnerabilities"]
    )
    lines.extend(
        f"VANHENTUNUT_POIKKEUS: {_exception_line(v)}" for v in report["expired_exceptions"]
    )
    lines.append(f"KORJAUSOHJE: {report['remediation']}")
    return "\n".join(lines) + "\n"


def format_azure_devops_commands(report: dict[str, Any]) -> list[str]:
    if report["result"] == APPROVED:
        return []
    messages: list[str] = []
    if report["error"]:
        messages.append(report["error"])
    for vuln in report["vulnerabilities"]:
        messages.append(f"Haavoittuvuus: {describe(vuln)} ({', '.join(vuln['files'])})")
    for item in report["expired_exceptions"]:
        messages.append(f"Poikkeus vanhentunut: {_exception_line(item)}")
    messages.append(f"Korjausohje: {report['remediation']}")
    return failure_commands(messages, "Lukitustiedostoissa on tunnettuja haavoittuvuuksia")


def main(argv: list[str] | None = None, audit: Audit = pip_audit) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lock",
        type=Path,
        action="append",
        help="Tarkastettava lukitustiedosto. Voidaan antaa useita kertoja. "
        "Oletus: kaikki repositorion lukitustiedostot.",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä hylkäyksen syyt Azure DevOpsin PR-näkymässä (exit-koodi 0).",
    )
    args = parser.parse_args(argv)

    report = run_scan(args.lock or DEFAULT_LOCK_FILES, args.policy, date.today(), audit)
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
