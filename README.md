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

## Linjaus

Uuden suoran Python-riippuvuuden (myös kehitystyökalun) pitää löytyä hyväksyttyjen kirjastojen rekisteristä tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus.

Hyväksyttyjen kirjastojen rekisteri on omassa tiedostossaan [`policy/approved-libraries.yml`](policy/approved-libraries.yml). Tässä koulutusprototyypissä ainoa hyväksytty esimerkkikirjasto on `arcgis`. Rekisteri ei ole virallinen yritys- tai asiakastason hyväksyntälista.

Rekisteri (politiikka) ja tarkastusskripti (sääntö) ovat erillään, jotta rekisterin muutoksille voidaan asettaa oma pakollinen katselmoija.

## Repositorion rakenne

| Tiedosto | Tarkoitus |
| --- | --- |
| `policy/approved-libraries.yml` | Hyväksytyt kirjastot ja määräaikaiset poikkeukset |
| `scripts/check_approved_libraries.py` | Tarkastussääntö |
| `scripts/check_precommit_config.py` | Sääntö: vain paikalliset git-hookit |
| `scripts/azure_devops.py` | Hylkäyksen syyt Azure DevOpsin PR-näkymään |
| `.pre-commit-config.yaml` | Git-hookit: tarkastukset commitissa, testit pushissa |
| `tests/` | Tarkastussääntöjen testit (pytest) |
| `requirements.txt` | Tarkastettavan projektin riippuvuudet |
| `requirements-dev.txt` | Kehitystyökalujen riippuvuudet (tarkastetaan samalla linjauksella) |
| `azure-pipelines.yml` | Pipeline: tarkastus → kehitystyökalujen asennus → testit → auditointievidenssi |

## Paikallinen käyttö VS Codessa

Avaa repository VS Codessa ja luo virtuaaliympäristö. Toimi samassa järjestyksessä kuin pipeline: tarkasta riippuvuudet ennen kuin asennat kehitystyökalut.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install pyyaml                  # vain tarkastusskriptin tarve
python scripts/check_approved_libraries.py    # tarkastaa requirements.txt ja requirements-dev.txt
python -m pip install -r requirements-dev.txt # vasta hyväksytyn tarkastuksen jälkeen
python -m pytest
```

Samat vaiheet löytyvät myös VS Code -taskeina (**Terminal → Run Task…**). Taskit käyttävät VS Codessa valittua Python-tulkkia, joten valitse ensin `.venv` (**Python: Select Interpreter**). Repository suosittelee tähän Python-laajennusta.

| Task | Pikanäppäin |
| --- | --- |
| **Koko ketju (kuten pipeline)**: kaikki alla olevat järjestyksessä | – |
| **Asenna tarkastusskriptin riippuvuus** | – |
| **Tarkasta hyväksytty kirjasto** | `Ctrl+Shift+B` (oletus-build-task) |
| **Asenna kehitystyökalut**: ajaa tarkastuksen ensin | – |
| **Aja testit** | oletus-test-task |
| **Asenna git-hookit**: asentaa kehitystyökalut ensin | – |
| **Aja git-hookit kaikille tiedostoille** | – |

Raportit syntyvät kansioon `artifacts/` (ei versionhallinnassa):

```text
artifacts/approved-libraries-report.txt   # ihmisen luettava
artifacts/approved-libraries-report.json  # koneluettava auditointievidenssi
```

## Hyväksytty tapaus

`requirements.txt` sisältää aktiivisena riippuvuutena vain `arcgis`. Skripti palauttaa exit-koodin 0 ja tulostaa `TULOS: HYVAKSYTTY`.

## Hylätty tapaus

Poista `requirements.txt`-tiedostossa kommenttimerkki riviltä:

```text
unknown-demo-package==1.0.0
```

Skripti palauttaa exit-koodin 1 ja tulostaa `TULOS: HYLATTY`.

Myös hyväksytyn nimen URL-viittaus hylätään, koska paketti tulisi silloin muualta kuin pakettirekisteristä:

```text
arcgis @ https://example.com/arcgis-9.9-py3-none-any.whl
```

## Määräaikainen poikkeus

Poikkeus lisätään rekisterin `exceptions`-listaan. Kentät `name`, `ticket` ja `expires` ovat pakollisia. Kun `expires`-päivä on ohitettu, tarkastus hylkää riippuvuuden ja raportoi sen kohdassa `VANHENTUNEET_POIKKEUKSET`.

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

`git commit` tarkastaa riippuvuudet ja hook-asetukset, ja `git push` ajaa testit. Hookit antavat nopean palautteen, mutta ne eivät korvaa pipelinea: `--no-verify` ohittaa ne. Katso [oppitunnit/02-git-hookit.md](oppitunnit/02-git-hookit.md).
