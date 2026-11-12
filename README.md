# DevSecOps Workshop Examples

> **ℹ️ Initial workshop template**
>
> This public repository contains initial examples for DevSecOps workshops aimed at trainers and Esri developers.
>
> The examples demonstrate the following workflow:
>
> **Policy → validation rule → pipeline → PR control → audit evidence**
>
> This code is intended for training, prototyping, and discussion. It is not a production-ready solution or an official Esri or Esri Finland security standard.

---

# ArcGIS Python: hyväksyttyjen kirjastojen koulutustemplate

Tämä pieni koulutusrepository näyttää käytännössä DevSecOps-ketjun:

**Linjaus → tarkastussääntö → requirements.txt-vertailu → Azure Pipeline → pakollinen PR-kontrolli → auditointievidenssi**

## Oppitunnit

Jokainen oppitunti on oma haaransa, ja seuraava oppitunti jatkaa edellisen lopputuloksesta.

| Haara | Aihe | Ohje |
| --- | --- | --- |
| `lesson/01-approved-libraries` | Hyväksytyt kirjastot, pipeline ja pakollinen PR-kontrolli | [oppitunnit/01-hyvaksytyt-kirjastot.md](oppitunnit/01-hyvaksytyt-kirjastot.md) |
| `lesson/02-git-hooks` | Git-hookit: sama tarkastus kehittäjän koneelle | [oppitunnit/02-git-hookit.md](oppitunnit/02-git-hookit.md) |
| `lesson/03-pinning` | Versioiden lukitus ja lukitustiedostot (vrt. `package-lock.json`) | [oppitunnit/03-versioiden-lukitus.md](oppitunnit/03-versioiden-lukitus.md) |

## Linjaus

Uuden suoran Python-riippuvuuden (myös kehitystyökalun) pitää löytyä hyväksyttyjen kirjastojen rekisteristä hyväksytyssä versiossa tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus. Jokainen asennus tehdään lukitustiedostosta hash-tarkistuksella.

Hyväksyttyjen kirjastojen rekisteri on omassa tiedostossaan [`policy/approved-libraries.yml`](policy/approved-libraries.yml). Tässä koulutusprototyypissä ainoa hyväksytty esimerkkikirjasto on `arcgis`. Rekisteri ei ole virallinen yritys- tai asiakastason hyväksyntälista.

Rekisteri (politiikka) ja tarkastusskripti (sääntö) ovat erillään, jotta rekisterin muutoksille voidaan asettaa oma pakollinen katselmoija.

## Repositorion rakenne

| Tiedosto | Tarkoitus |
| --- | --- |
| `policy/approved-libraries.yml` | Hyväksytyt kirjastot, niiden hyväksytyt versiot ja määräaikaiset poikkeukset |
| `requirements.txt` | Projektin suorat riippuvuudet tarkkoine versioineen (vrt. `package.json`) |
| `requirements-dev.txt` | Kehitystyökalujen suorat riippuvuudet |
| `requirements-bootstrap.txt` | Paketit, jotka pipeline asentaa ennen tarkastuksia (PyYAML ja uv) |
| `requirements*.lock.txt` | Generoidut lukitustiedostot: koko riippuvuuspuu versioineen ja hasheineen (vrt. `package-lock.json`) |
| `scripts/check_approved_libraries.py` | Sääntö: jokainen riippuvuus on lukittu hyväksyttyyn versioon |
| `scripts/lock_files.py` | Lukitustiedostojen päivitys (`update`) ja tarkastus (`check`) |
| `scripts/check_precommit_config.py` | Sääntö: vain paikalliset git-hookit, joiden riippuvuudet on lukittu |
| `scripts/azure_devops.py` | Hylkäyksen syyt Azure DevOpsin PR-näkymään |
| `.pre-commit-config.yaml` | Git-hookit: tarkastukset commitissa, testit pushissa |
| `tests/` | Tarkastussääntöjen testit (pytest) |
| `azure-pipelines.yml` | Pipeline: tarkastukset → kehitystyökalujen asennus → testit → auditointievidenssi |

## Paikallinen käyttö VS Codessa

Vaatii Python 3.11:n tai uudemman (lukitustiedostot on luotu Python 3.11+:lle).

Avaa repository VS Codessa ja luo virtuaaliympäristö. Toimi samassa järjestyksessä kuin pipeline: tarkasta riippuvuudet ennen kuin asennat kehitystyökalut. Kaikki asennukset tehdään lukitustiedostoista.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary :all: -r requirements-bootstrap.lock.txt
python scripts/check_approved_libraries.py   # versiot lukittu ja hyväksytty?
python scripts/lock_files.py check           # lukitustiedostot ajan tasalla?
python -m pip install --require-hashes --only-binary :all: -r requirements-dev.lock.txt
python -m pytest
```

Kun muutat requirements-tiedostoa, päivitä lukitustiedostot:

```powershell
python scripts/lock_files.py update
```

Samat vaiheet löytyvät myös VS Code -taskeina (**Terminal → Run Task…**). Taskit käyttävät VS Codessa valittua Python-tulkkia, joten valitse ensin `.venv` (**Python: Select Interpreter**). Repository suosittelee tähän Python-laajennusta.

| Task | Pikanäppäin |
| --- | --- |
| **Koko ketju (kuten pipeline)**: asennukset, tarkastukset ja testit järjestyksessä | – |
| **Asenna tarkastusten riippuvuudet** | – |
| **Tarkasta hyväksytty kirjasto** | `Ctrl+Shift+B` (oletus-build-task) |
| **Tarkasta lukitustiedostot** | – |
| **Päivitä lukitustiedostot** | – |
| **Asenna kehitystyökalut**: ajaa tarkastukset ensin | – |
| **Aja testit** | oletus-test-task |
| **Asenna git-hookit**: asentaa kehitystyökalut ensin | – |
| **Aja git-hookit kaikille tiedostoille** | – |

Raportit syntyvät kansioon `artifacts/` (ei versionhallinnassa):

```text
artifacts/approved-libraries-report.txt   # ihmisen luettava
artifacts/approved-libraries-report.json  # koneluettava auditointievidenssi
```

## Hyväksytty tapaus

`requirements.txt` sisältää aktiivisena riippuvuutena vain `arcgis==2.4.4`, joka on hyväksytty versio. Skripti palauttaa exit-koodin 0 ja tulostaa `TULOS: HYVAKSYTTY`.

## Hylätty tapaus

Poista `requirements.txt`-tiedostossa kommenttimerkki riviltä:

```text
unknown-demo-package==1.0.0
```

Skripti palauttaa exit-koodin 1 ja tulostaa `TULOS: HYLATTY`.

Myös hyväksytty kirjasto hylätään, jos sen versiota ei ole lukittu (`arcgis`) tai lukittua versiota ei ole hyväksytty (`arcgis==2.5.0`).

Myös hyväksytyn nimen URL-viittaus hylätään, koska paketti tulisi silloin muualta kuin pakettirekisteristä:

```text
arcgis @ https://example.com/arcgis-9.9-py3-none-any.whl
```

## Määräaikainen poikkeus

Poikkeus lisätään rekisterin `exceptions`-listaan. Kentät `name`, `versions`, `ticket` ja `expires` ovat pakollisia, ja poikkeus koskee vain lueteltuja versioita. Kun `expires`-päivä on ohitettu, tarkastus hylkää riippuvuuden ja raportoi sen kohdassa `VANHENTUNEET_POIKKEUKSET`.

## Pipeline

Azure DevOpsissa pakolliseksi asetettu Build validation estää normaalin mergen, mutta raportti julkaistaan silti pipeline artifactina.

Pipeline ajaa tarkastuksen valitsimella `--azure-devops`. Silloin hylkäyksen syyt näkyvät suoraan PR:n tarkastusnäkymässä, esimerkiksi:

```text
Hyväksymätön kirjasto: unknown-demo-package (requirements.txt)
Korjausohje: Poista riippuvuus tai dokumentoi ja hyväksytä poikkeus (policy/approved-libraries.yml) ennen mergeä.
```

Tämä tehdään Azure DevOpsin [logging-komennoilla](https://learn.microsoft.com/azure/devops/pipelines/scripts/logging-commands) (`##vso[task.logissue]` ja `##vso[task.complete result=Failed]`). Paikallisesti skripti käyttää tavallista exit-koodia 1.

Tarkemmat VS Code- ja Azure DevOps -vaiheet ovat tiedostossa [oppitunnit/01-hyvaksytyt-kirjastot.md](oppitunnit/01-hyvaksytyt-kirjastot.md).

## Git-hookit

Samat tarkastukset voi ajaa jo kehittäjän koneella git-hookeina:

```powershell
python -m pre_commit install
```

`git commit` tarkastaa riippuvuudet, lukitustiedostot ja hook-asetukset, ja `git push` ajaa testit. Hookit antavat nopean palautteen, mutta ne eivät korvaa pipelinea: `--no-verify` ohittaa ne. Katso [oppitunnit/02-git-hookit.md](oppitunnit/02-git-hookit.md).

## Lukitustiedostot

| npm | Tämä repositorio |
| --- | --- |
| `package.json` | `requirements.txt`: suorat riippuvuudet tarkkoine versioineen |
| `package-lock.json` | `requirements.lock.txt`: koko riippuvuuspuu versioineen ja hasheineen |
| `npm ci` | `pip install --require-hashes --only-binary :all: -r requirements.lock.txt` |

Lukitustiedostot luo [uv](https://docs.astral.sh/uv/), mutta asennukset tehdään edelleen pipillä. Katso [oppitunnit/03-versioiden-lukitus.md](oppitunnit/03-versioiden-lukitus.md).
