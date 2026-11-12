"""Päivitä ja tarkasta lukitustiedostot (vrt. npm:n package-lock.json).

    python scripts/lock_files.py update   # luo lukitustiedostot uudelleen uv:llä
    python scripts/lock_files.py update --upgrade-package requests   # päivitä yksi paketti
    python scripts/lock_files.py check    # tarkasta, että ne vastaavat requirements-tiedostoja

Jokaisesta käsin muokattavasta requirements-tiedostosta luodaan lukitustiedosto,
jossa on koko riippuvuuspuu (myös transitiiviset riippuvuudet) tarkkoine
versioineen ja hasheineen. Lukitustiedosto toimii Windowsissa, macOS:ssä ja
Linuxissa (--universal), ja sen voi asentaa tavallisella pipillä:

    python -m pip install --require-hashes --only-binary :all: -r requirements.lock.txt

Tarkastus luo lukitustiedostot uudelleen väliaikaiseen kansioon ja vertaa niitä
versionhallinnassa oleviin. Näin PR ei voi lisätä pakettia suoraan
lukitustiedostoon ohi requirements-tiedoston ja hyväksyntätarkastuksen.

Exit-koodi 0 = hyväksytty, 1 = hylätty.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
# uv ajetaan kiinteällä komennolla ilman shelliä; ks. uv_compile.
import subprocess  # nosec B404
import sys
import tempfile
from typing import Callable

from azure_devops import failure_commands


@dataclass(frozen=True)
class LockFile:
    source: str  # käsin muokattava requirements-tiedosto
    lock: str  # uv:n generoima lukitustiedosto


LOCKS = [
    LockFile("requirements.txt", "requirements.lock.txt"),
    LockFile("requirements-dev.txt", "requirements-dev.lock.txt"),
    LockFile("requirements-bootstrap.txt", "requirements-bootstrap.lock.txt"),
]

UPDATE_COMMAND = "python scripts/lock_files.py update"
UV_COMPILE_OPTIONS = [
    "--universal",  # yksi lukitustiedosto kaikille käyttöjärjestelmille
    "--python-version", "3.11",  # pienin tuettu Python-versio (sama kuin pipelinessa)
    "--generate-hashes",  # pip --require-hashes tarvitsee nämä
    "--no-build",  # vain valmiit paketit (wheel): pakettien build-koodia ei ajeta
    "--custom-compile-command", UPDATE_COMMAND,
    "--quiet",
]

CompileLock = Callable[..., None]
LockEntries = dict[tuple[str, str], tuple[str, frozenset[str]]]

HASH = re.compile(r"--hash=(\S+)")
PINNED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+?)\s*(?:;\s*(.*?))?\s*$")


def uv_compile(source: Path, output: Path, upgrade: tuple[str, ...] = ()) -> None:
    """Luo lukitustiedosto uv:llä.

    uv säilyttää output-tiedostossa jo olevat versiot. `upgrade` päivittää
    nimetyt paketit uusimpaan sopivaan versioon (esim. haavoittuvuuden korjaus
    transitiiviseen riippuvuuteen).
    """
    upgrade_options = [option for name in upgrade for option in ("--upgrade-package", name)]
    # Kiinteä komento ilman shelliä; polut ovat repositorion tiedostoja.
    result = subprocess.run(  # nosec B603
        [sys.executable, "-m", "uv", "pip", "compile", str(source), "-o", str(output),
         *UV_COMPILE_OPTIONS, *upgrade_options],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv pip compile {source} epäonnistui: {result.stderr.strip()}")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(text: str) -> LockEntries:
    """Lue lukitustiedoston paketit: (nimi, ympäristöehto) -> (versio, hashit)."""
    logical_lines: list[str] = []
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not current and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        logical_lines.append(current + line)
        current = ""
    if current:
        logical_lines.append(current)

    entries: LockEntries = {}
    for line in logical_lines:
        hashes = frozenset(HASH.findall(line))
        requirement = HASH.sub("", line).strip()
        match = PINNED.match(requirement)
        if not match:
            raise ValueError(f"Lukitustiedoston riviä ei voitu tulkita: {line}")
        name, version, marker = match.groups()
        entries[(_normalize(name), marker or "")] = (version, hashes)
    return entries


def _describe(name: str, marker: str, version: str) -> str:
    return f"{name}=={version}" + (f" ; {marker}" if marker else "")


def compare_locks(committed: str, expected: str) -> list[str]:
    """Vertaa versionhallinnan lukitustiedostoa juuri generoituun."""
    have, want = parse_lock(committed), parse_lock(expected)
    problems: list[str] = []
    for key in sorted(have.keys() | want.keys()):
        name, marker = key
        if key not in want:
            problems.append(
                "Lukitustiedostossa on paketti, jota requirements-tiedosto ei vaadi: "
                + _describe(name, marker, have[key][0])
            )
        elif key not in have:
            problems.append(
                "Lukitustiedostosta puuttuu paketti: " + _describe(name, marker, want[key][0])
            )
        elif have[key][0] != want[key][0]:
            problems.append(
                "Lukitustiedoston versio ei vastaa requirements-tiedostoa: "
                f"{name} on {have[key][0]}, pitäisi olla {want[key][0]}"
            )
        elif have[key][1] != want[key][1]:
            problems.append(
                "Lukitustiedoston hash ei vastaa pakettirekisteriä: "
                + _describe(name, marker, have[key][0])
            )
    return problems


def _versions_only(lock_text: str) -> str:
    """Lukitustiedoston versiot ilman hasheja, uv:lle lähtötiedoksi.

    uv säilyttää output-tiedostossa jo olevat versiot. Ilman niitä jokainen uusi
    julkaisu PyPI:ssä saisi tarkastuksen epäonnistumaan. uv säilyttää kuitenkin
    myös löytämänsä hashit, jolloin muokattu hash jäisi huomaamatta. Siksi uv saa
    vain versiot ja hakee hashit itse pakettirekisteristä.
    """
    return "".join(
        _describe(name, marker, version) + "\n"
        for (name, marker), (version, _hashes) in parse_lock(lock_text).items()
    )


def check_locks(locks: list[LockFile], root: Path, compile_lock: CompileLock) -> list[str]:
    """Luo lukitustiedostot uudelleen väliaikaiseen kansioon ja vertaa."""
    problems: list[str] = []
    for lock in locks:
        committed_path = root / lock.lock
        if not committed_path.exists():
            problems.append(f"{lock.lock} puuttuu")
            continue
        committed = committed_path.read_text(encoding="utf-8")
        try:
            pinned_versions = _versions_only(committed)
        except ValueError as error:
            problems.append(f"{lock.lock}: {error}")
            continue
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / lock.lock
            output.write_text(pinned_versions, encoding="utf-8")
            try:
                compile_lock(root / lock.source, output)
            except RuntimeError as error:
                problems.append(f"{lock.lock}: {error}")
                continue
            expected = output.read_text(encoding="utf-8")
        try:
            problems.extend(f"{lock.lock}: {p}" for p in compare_locks(committed, expected))
        except ValueError as error:
            problems.append(f"{lock.lock}: {error}")
    return problems


def main(
    argv: list[str] | None = None,
    locks: list[LockFile] = LOCKS,
    compile_lock: CompileLock = uv_compile,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    update = commands.add_parser("update", help="Luo lukitustiedostot uudelleen.")
    update.add_argument(
        "--upgrade-package",
        action="append",
        default=[],
        metavar="PAKETTI",
        help="Päivitä paketti uusimpaan sopivaan versioon. Muut versiot säilyvät. "
        "Voidaan antaa useita kertoja.",
    )
    check = commands.add_parser("check", help="Tarkasta, että lukitustiedostot ovat ajan tasalla.")
    check.add_argument(
        "--azure-devops",
        action="store_true",
        help="Näytä hylkäyksen syyt Azure DevOpsin PR-näkymässä (exit-koodi 0).",
    )
    args = parser.parse_args(argv)
    root = Path(".")

    if args.command == "update":
        for lock in locks:
            print(f"Päivitetään {lock.lock} ({lock.source})")
            if args.upgrade_package:
                compile_lock(root / lock.source, root / lock.lock,
                             upgrade=tuple(args.upgrade_package))
            else:
                compile_lock(root / lock.source, root / lock.lock)
        return 0

    problems = check_locks(locks, root, compile_lock)
    remediation = f"Päivitä lukitustiedostot: {UPDATE_COMMAND}"
    print("TARKASTUS: lukitustiedostot")
    print(f"TULOS: {'HYLATTY' if problems else 'HYVAKSYTTY'}")
    for problem in problems:
        print(f"SYY: {problem}")
    if problems:
        print(f"KORJAUSOHJE: {remediation}")

    if args.azure_devops:
        if problems:
            commands_out = failure_commands(
                [*problems, f"Korjausohje: {remediation}"],
                "Lukitustiedostot eivät vastaa requirements-tiedostoja",
            )
            print("\n".join(commands_out))
        return 0
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
