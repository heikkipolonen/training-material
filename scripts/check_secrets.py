"""Tarkasta, ettei repositorioon päädy salaisuuksia (salasanoja, API-avaimia).

Työkaluna on detect-secrets ja oma ArcGIS-avaintunnistin
(scripts/arcgis_secret_detector.py). Tarkastus ajetaan aina valitsimella
--no-verify: löydettyjä avaimia ei koskaan kokeilla palveluntarjoajan
rajapintaa vasten.

Perusteltu poikkeus (väärä hälytys) merkitään riville kommentilla
`# pragma: allowlist secret`, ja perustelu kirjoitetaan edelliselle riville.

    python scripts/check_secrets.py              # kaikki versionhallinnan tiedostot
    python scripts/check_secrets.py tiedosto     # vain annetut tiedostot (commit-hook)

Raportissa ei ole salaisuutta eikä sen tiivistettä, vain tiedosto, rivi ja tyyppi.
Raportit: artifacts/secrets-report.txt ja artifacts/secrets-report.json.
Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
# detect-secrets ja git ajetaan kiinteillä komennoilla ilman shelliä.
import subprocess  # nosec B404
import sys
from typing import Any, Callable

from azure_devops import failure_commands

DETECTOR = Path(__file__).resolve().parent / "arcgis_secret_detector.py"
DETECT_SECRETS_OPTIONS = [
    "--no-verify",  # älä koskaan kokeile löydettyjä avaimia verkossa
    "--plugin", str(DETECTOR),
    # Tämä suodatin ohittaisi rivit, jotka näyttävät funktiokutsuilta, kuten
    # GIS(url, api_key="..."), eli juuri yleisimmän ArcGIS-virheen.
    "--disable-filter", "detect_secrets.filters.heuristic.is_indirect_reference",
]
DEFAULT_OUTPUT_DIR = Path("artifacts")
REPORT_BASENAME = "secrets-report"
APPROVED = "HYVAKSYTTY"
REJECTED = "HYLATTY"

Scan = Callable[[list[str]], dict[str, list[dict[str, Any]]]]


def detect_secrets_scan(files: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Aja detect-secrets annetuille tiedostoille ja palauta löydökset tiedostoittain."""
    # Kiinteä komento ilman shelliä; tiedostot ovat repositorion tiedostoja.
    result = subprocess.run(  # nosec B603
        [sys.executable, "-m", "detect_secrets.pre_commit_hook", *DETECT_SECRETS_OPTIONS,
         "--json", *files],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)["results"]
    except (json.JSONDecodeError, KeyError):
        raise RuntimeError(f"detect-secrets epäonnistui: {result.stderr.strip()}") from None


def git_tracked_files() -> list[str]:
    """Versionhallinnassa olevat tiedostot."""
    # Kiinteä komento ilman shelliä.
    result = subprocess.run(  # nosec B603 B607
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def run_check(files: list[str], scan: Scan) -> dict[str, Any]:
    report: dict[str, Any] = {
        "check": "Salaisuudet (detect-secrets)",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_files": len(files),
        "findings": [],
        "error": None,
    }
    if not files:
        report.update(result=APPROVED, exit_code=0, remediation="Ei tarkastettavia tiedostoja.")
        return report

    try:
        results = scan(files)
    except RuntimeError as error:
        report.update(result=REJECTED, exit_code=1, error=str(error),
                      remediation="Korjaa virhe ja aja tarkastus uudelleen.")
        return report

    # Sama rivi voi laukaista useita tunnistimia; ne yhdistetään yhdeksi löydökseksi.
    by_line: dict[tuple[str, int], set[str]] = {}
    for filename, items in results.items():
        for item in items:
            by_line.setdefault((filename, item["line_number"]), set()).add(item["type"])
    report["findings"] = [
        {"file": file, "line": line, "types": sorted(types)}
        for (file, line), types in sorted(by_line.items())
    ]

    if report["findings"]:
        report.update(
            result=REJECTED,
            exit_code=1,
            remediation=(
                "Poista salaisuus koodista ja lue se ympäristömuuttujasta. Jos salaisuus on "
                "jo pushattu, se on vuotanut: mitätöi se ja luo uusi. Väärä hälytys merkitään "
                "kommentilla `# pragma: allowlist secret` ja perustelulla edellisellä rivillä."
            ),
        )
    else:
        report.update(result=APPROVED, exit_code=0, remediation="Ei korjaustarvetta.")
    return report


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        f"TARKASTUS: {report['check']}",
        f"AIKA_UTC: {report['timestamp_utc']}",
        f"TARKASTETUT_TIEDOSTOT: {report['scanned_files']}",
        f"TULOS: {report['result']}",
    ]
    if report["error"]:
        lines.append(f"SYY: {report['error']}")
    lines.extend(
        f"SALAISUUS: {f['file']}:{f['line']} ({', '.join(f['types'])})"
        for f in report["findings"]
    )
    lines.append(f"KORJAUSOHJE: {report['remediation']}")
    return "\n".join(lines) + "\n"


def format_azure_devops_commands(report: dict[str, Any]) -> list[str]:
    if report["result"] == APPROVED:
        return []
    errors: list[Any] = []
    if report["error"]:
        errors.append(report["error"])
    errors.extend(
        (f"Mahdollinen salaisuus: {', '.join(f['types'])}", f["file"], f["line"])
        for f in report["findings"]
    )
    errors.append(f"Korjausohje: {report['remediation']}")
    return failure_commands(errors, "Tarkastus löysi mahdollisia salaisuuksia")


def main(
    argv: list[str] | None = None,
    scan: Scan = detect_secrets_scan,
    tracked_files: Callable[[], list[str]] = git_tracked_files,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="Tarkastettavat tiedostot.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä löydökset Azure DevOpsin PR-näkymässä (exit-koodi 0).",
    )
    args = parser.parse_args(argv)

    report = run_check(args.files or tracked_files(), scan)
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
