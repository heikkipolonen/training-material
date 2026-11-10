"""Tarkasta suorat riippuvuudet koulutuksen hyväksyntärekisteriä vasten."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sys

REQUIREMENTS_FILE = Path("requirements.txt")
REPORT_FILE = Path("artifacts/approved-libraries-report.txt")

# KOULUTUSPROTOTYYPPI. EI VIRALLINEN YRITYS- TAI ASIAKASTASON HYVÄKSYNTÄLISTA.
APPROVED_LIBRARIES = {"arcgis"}

PACKAGE_NAME_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)")


def normalize_package_name(name: str) -> str:
    """Normalisoi kirjainkoko sekä piste-, alaviiva- ja yhdysmerkkierot."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_direct_dependencies(path: Path) -> list[str]:
    """Lue aktiivisten requirements-rivien pakettien nimet."""
    dependencies: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = PACKAGE_NAME_PATTERN.match(line)
        if not match:
            raise ValueError(f"Rivia ei voitu tulkita: {raw_line}")

        dependencies.append(normalize_package_name(match.group(1)))

    return dependencies


def build_report() -> tuple[list[str], int]:
    """Muodosta raporttirivit ja prosessin exit-koodi."""
    timestamp = datetime.now(timezone.utc).isoformat()

    if not REQUIREMENTS_FILE.exists():
        return [
            "TARKASTUS: ArcGIS Python -projektin hyväksytyt kirjastot",
            f"AIKA_UTC: {timestamp}",
            "SUORAT_RIIPPUVUUDET: ei voitu tarkastaa",
            "TULOS: HYLATTY",
            "SYY: requirements.txt puuttuu",
            "KORJAUSOHJE: lisää requirements.txt ja suorita tarkastus uudelleen.",
        ], 1

    try:
        dependencies = read_direct_dependencies(REQUIREMENTS_FILE)
    except ValueError as error:
        return [
            "TARKASTUS: ArcGIS Python -projektin hyväksytyt kirjastot",
            f"AIKA_UTC: {timestamp}",
            "SUORAT_RIIPPUVUUDET: tiedostoa ei voitu tulkita",
            "TULOS: HYLATTY",
            f"SYY: {error}",
            "KORJAUSOHJE: korjaa requirements.txt-tiedoston virheellinen rivi.",
        ], 1

    unknown = sorted(set(dependencies) - APPROVED_LIBRARIES)
    lines = [
        "TARKASTUS: ArcGIS Python -projektin hyväksytyt kirjastot",
        f"AIKA_UTC: {timestamp}",
        f"SUORAT_RIIPPUVUUDET: {', '.join(dependencies) or 'ei riippuvuuksia'}",
    ]

    if unknown:
        lines.extend([
            "TULOS: HYLATTY",
            "TUNTEMATTOMAT_KIRJASTOT: " + ", ".join(unknown),
            "Tuntemattomat kirjastot: " + ", ".join(unknown),
            "KORJAUSOHJE: poista riippuvuus tai dokumentoi ja hyväksytä poikkeus ennen mergeä.",
        ])
        return lines, 1

    lines.extend([
        "TULOS: HYVAKSYTTY",
        "TUNTEMATTOMAT_KIRJASTOT: ei ole",
        "KORJAUSOHJE: ei korjaustarvetta.",
    ])
    return lines, 0


def main() -> int:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines, exit_code = build_report()
    report = "\n".join(lines) + "\n"
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
