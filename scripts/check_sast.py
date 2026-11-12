"""Tarkasta oma koodi tunnettujen riskialttiiden koodimallien varalta (SAST).

Työkaluna on Bandit. Jokainen löydös hylkää tarkastuksen vakavuudesta
riippumatta, koska Bandit luokittelee esimerkiksi koodiin kirjoitetun salasanan
vain vakavuudeltaan matalaksi (LOW).

Perusteltu poikkeus merkitään riville kommentilla `# nosec <tunniste>`, ja
perustelu kirjoitetaan edelliselle riville. Poikkeusten määrä näkyy raportissa.

    python scripts/check_sast.py              # oletuksena src/ ja scripts/
    python scripts/check_sast.py tiedosto.py  # vain annetut tiedostot (commit-hook)

Raportit: artifacts/sast-report.txt ja artifacts/sast-report.json.
Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
# Bandit ajetaan kiinteällä komennolla ilman shelliä; ks. run_bandit.
import subprocess  # nosec B404
import sys
from typing import Any, Callable

from azure_devops import failure_commands

DEFAULT_TARGETS = ["src", "scripts"]
DEFAULT_OUTPUT_DIR = Path("artifacts")
REPORT_BASENAME = "sast-report"
APPROVED = "HYVAKSYTTY"
REJECTED = "HYLATTY"

RunBandit = Callable[[list[str]], dict[str, Any]]


def run_bandit(paths: list[str]) -> dict[str, Any]:
    """Aja Bandit annetuille tiedostoille ja kansioille ja palauta JSON-tulos."""
    # Kiinteä komento ilman shelliä; polut ovat repositorion tiedostoja.
    result = subprocess.run(  # nosec B603
        [sys.executable, "-m", "bandit", "-r", *paths, "-f", "json", "-q"],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"bandit epäonnistui: {result.stderr.strip()}") from None


def _targets(paths: list[str]) -> list[str]:
    """Pidä .py-tiedostot ja kansiot (polut ilman tiedostopäätettä), ohita muut."""
    return [p for p in paths if p.endswith(".py") or Path(p).suffix == ""]


def run_check(paths: list[str], run: RunBandit) -> dict[str, Any]:
    report: dict[str, Any] = {
        "check": "Oman koodin tietoturvatarkastus (SAST, Bandit)",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "targets": [],
        "findings": [],
        "suppressed": 0,
        "error": None,
    }
    targets = _targets(paths)
    report["targets"] = targets
    if not targets:
        report.update(result=APPROVED, exit_code=0, remediation="Ei tarkastettavia tiedostoja.")
        return report

    try:
        output = run(targets)
    except RuntimeError as error:
        report.update(result=REJECTED, exit_code=1, error=str(error),
                      remediation="Korjaa virhe ja aja tarkastus uudelleen.")
        return report

    report["suppressed"] = output.get("metrics", {}).get("_totals", {}).get("skipped_tests", 0)
    for item in sorted(output.get("results", []),
                       key=lambda r: (r["filename"], r["line_number"], r["test_id"])):
        report["findings"].append({
            # Bandit lisää yksittäisen tiedoston eteen "./".
            "file": item["filename"].removeprefix("./"),
            "line": item["line_number"],
            "test_id": item["test_id"],
            "severity": item["issue_severity"],
            "confidence": item["issue_confidence"],
            "text": item["issue_text"],
            "more_info": item.get("more_info", ""),
        })

    errors = output.get("errors", [])
    if errors:
        report["error"] = "; ".join(f"{e['filename']}: {e['reason']}" for e in errors)

    if report["findings"] or report["error"]:
        report.update(
            result=REJECTED,
            exit_code=1,
            remediation=(
                "Korjaa koodi. Jos löydös on perusteltu poikkeus, merkitse rivi "
                "kommentilla `# nosec <tunniste>` ja kirjoita perustelu edelliselle riville."
            ),
        )
    else:
        report.update(result=APPROVED, exit_code=0, remediation="Ei korjaustarvetta.")
    return report


def _describe(finding: dict[str, Any]) -> str:
    return f"{finding['test_id']} ({finding['severity']}): {finding['text']}"


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        f"TARKASTUS: {report['check']}",
        f"AIKA_UTC: {report['timestamp_utc']}",
        f"KOHTEET: {', '.join(report['targets']) or 'ei ole'}",
        f"TULOS: {report['result']}",
    ]
    if report["error"]:
        lines.append(f"SYY: {report['error']}")
    lines.extend(
        f"LOYDOS: {f['file']}:{f['line']} {f['test_id']} ({f['severity']}) {f['text']}"
        for f in report["findings"]
    )
    lines.append(f"OHITETUT_NOSEC: {report['suppressed']}")
    lines.append(f"KORJAUSOHJE: {report['remediation']}")
    return "\n".join(lines) + "\n"


def format_azure_devops_commands(report: dict[str, Any]) -> list[str]:
    if report["result"] == APPROVED:
        return []
    errors: list[Any] = []
    if report["error"]:
        errors.append(report["error"])
    errors.extend((_describe(f), f["file"], f["line"]) for f in report["findings"])
    errors.append(f"Korjausohje: {report['remediation']}")
    return failure_commands(errors, "Oman koodin tietoturvatarkastus hylkäsi muutoksen")


def main(argv: list[str] | None = None, run_bandit: RunBandit = run_bandit) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="Tarkastettavat tiedostot tai kansiot.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä löydökset Azure DevOpsin PR-näkymässä (exit-koodi 0).",
    )
    args = parser.parse_args(argv)

    report = run_check(args.paths or DEFAULT_TARGETS, run_bandit)
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
