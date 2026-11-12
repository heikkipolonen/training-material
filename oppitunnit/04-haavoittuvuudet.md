# Oppitunti 4: Tunnetut haavoittuvuudet

## Tavoite

Oppitunnilla 3 lukitustiedostoon tuli 65 pakettia yhdestä suorasta riippuvuudesta. Ihminen hyväksyi niistä yhden. Muut ovat lukittuja ja näkyvissä, mutta kukaan ei ole tarkastanut, onko niissä tunnettuja haavoittuvuuksia.

Tällä oppitunnilla jokainen lukitustiedostojen paketti tarkastetaan automaattisesti julkisia haavoittuvuustietokantoja vasten: ennen pushia, PR:ssä ja joka yö.

## Keskeinen viesti

**Ihminen hyväksyy valinnat, työkalu tarkastaa loput.** Lisäksi: eilen turvallinen lukitustiedosto voi olla tänään haavoittuva, vaikka kukaan ei ole muuttanut mitään.

## Lähtötilanne

| Haara | Sisältö |
| --- | --- |
| `lesson/03-pinning` | Oppitunnin 3 lopputulos ja tämän oppitunnin lähtötilanne |
| `lesson/04-vulnerability-scanning` | Tämän oppitunnin valmis lopputulos |

```powershell
git fetch github-template
git checkout -b lesson/04-vulnerability-scanning github-template/lesson/04-vulnerability-scanning
git push -u origin lesson/04-vulnerability-scanning
```

Kehitystyökaluihin tuli uusi työkalu ja git-hookeihin uusi hook, joten asenna molemmat uudelleen:

```powershell
python -m pip install --require-hashes --only-binary :all: -r requirements-dev.lock.txt
python -m pre_commit install --install-hooks
```

## A. Uusi työkalu: pip-audit

[pip-audit](https://pypi.org/project/pip-audit/) vertaa paketteja ja versioita julkisiin haavoittuvuustietokantoihin. Sitä ylläpitää PyPA, sama ryhmä, joka ylläpitää pipiä.

- pip-audit kulki saman hyväksyntäprosessin läpi kuin muutkin työkalut: rekisteriin `pip-audit` versiolla `2.10.1`, `requirements-dev.txt`:hen ja lukitustiedostoon.
- pip-audit lukee lukitustiedostot **asentamatta mitään**, koska jokainen versio on jo lukittu. Oppitunti 3 teki tämän mahdolliseksi: työkalu ei voi tarkastaa sitä, mitä se ei näe.

> **Pohdittavaa:** `requirements-dev.lock.txt`:ssä oli ennen 17 pakettia, nyt 42. Yksi uusi tietoturvatyökalu toi 25 uutta pakettia. Mitä tästä seuraa?

## B. Aja tarkastus

```powershell
python scripts/check_vulnerabilities.py
```

```text
TARKASTUS: Tunnetut haavoittuvuudet
LUKITUSTIEDOSTOT: requirements.lock.txt, requirements-dev.lock.txt, requirements-bootstrap.lock.txt
TARKASTETUT_PAKETIT: 101
TULOS: HYVAKSYTTY
HAAVOITTUVUUDET: ei ole
```

Tuloksesi voi olla eri, jos jollekin paketille on julkaistu haavoittuvuus tämän ohjeen kirjoittamisen jälkeen. Juuri siksi tarkastus ajetaan myös joka yö (kohta G).

### Miksi oma skripti eikä suoraan pip-audit?

Ajettuna suoraan lukitustiedostoon pip-audit ohittaa ilman ilmoitusta paketit, joiden ehto ei koske sitä konetta, jolla se ajetaan. Macilla se tarkasti 68 rivistä vain 60: Windows-paketit kuten `pywin32` jäivät pois. Linux-pipelinessa pois jäisivät taas muut. Windows-käyttäjien paketin haavoittuvuus ei näkyisi koskaan.

`scripts/check_vulnerabilities.py` lukee lukitustiedostot itse ilman ehtoja ja antaa pip-auditille kaikki paketit. Tarkastustyökalunkin toiminta pitää tarkastaa.

## C. Harjoitus: haavoittuva versio

Luo tiedosto `demo.lock.txt`, jossa on vanha `requests`-versio:

```text
requests==2.31.0
```

```powershell
python scripts/check_vulnerabilities.py --lock demo.lock.txt
```

```text
TARKASTETUT_PAKETIT: 1
TULOS: HYLATTY
HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-1872 (CVE-2024-47081, GHSA-9hjg-9r4m-mvj7), korjattu versiossa 2.32.4
HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-1873 (CVE-2024-35195, GHSA-9wx4-h78v-vm56), korjattu versiossa 2.32.0
HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-2275 (CVE-2026-25645, GHSA-gc5v-m9x4-r6x2), korjattu versiossa 2.33.0
```

Samalla haavoittuvuudella on useita tunnisteita: `PYSEC` (Pythonin oma tietokanta), `CVE` (yleinen) ja `GHSA` (GitHub).

1. Mikä versio korjaa kaikki kolme? Kokeile vaihtaa tiedostoon `requests==2.32.4` ja sitten `requests==2.33.0`.
2. Avaa jokin `GHSA`-tunniste osoitteessa `https://github.com/advisories/<tunniste>`. Koskeeko haavoittuvuus tapaa, jolla `arcgis` käyttää `requests`-pakettia? Tätä työkalu ei osaa arvioida.

## D. Harjoitus: määräaikainen poikkeus

Joskus korjattua versiota ei ole vielä olemassa, tai sitä ei voi heti ottaa käyttöön. Silloin haavoittuvuuden voi hyväksyä määräaikaisesti, kuten kirjastonkin (oppitunti 1).

Palauta `demo.lock.txt`-tiedostoon `requests==2.31.0` ja luo tiedosto `demo-poikkeukset.yml`:

```yaml
vulnerability_exceptions:
  - id: CVE-2024-35195
    ticket: SEC-200
    expires: 2026-12-31
    reason: Harjoitus
```

```powershell
python scripts/check_vulnerabilities.py --lock demo.lock.txt --policy demo-poikkeukset.yml
```

```text
TULOS: HYLATTY
HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-1872 (CVE-2024-47081, GHSA-9hjg-9r4m-mvj7), korjattu versiossa 2.32.4
HAAVOITTUVUUS: requests==2.31.0 PYSEC-2026-2275 (CVE-2026-25645, GHSA-gc5v-m9x4-r6x2), korjattu versiossa 2.33.0
HYVAKSYTTY_POIKKEUKSELLA: requests==2.31.0 PYSEC-2026-1873 (SEC-200, voimassa 2026-12-31 asti)
```

- Poikkeus koskee vain yhtä haavoittuvuutta, ei koko pakettia. Kaksi muuta hylätään edelleen.
- Poikkeuksen tunnisteeksi kelpaa mikä tahansa tunnisteista (tässä `CVE`).
- Vaihda `expires`-päivä menneisyyteen ja aja uudelleen. Mitä tapahtuu?

Oikeassa projektissa poikkeukset kirjataan tiedostoon `policy/vulnerability-exceptions.yml`, jolla on pakollinen katselmoija (polku `/policy/*`).

Poista lopuksi harjoitustiedostot `demo.lock.txt` ja `demo-poikkeukset.yml`.

## E. Haavoittuvuuden korjaaminen oikeassa projektissa

| Haavoittuva paketti | Korjaus |
| --- | --- |
| Suora riippuvuus (esim. `arcgis`) | Oppitunnin 3 päivitysprosessi: uusi versio `requirements.txt`:hen, version hyväksyntä rekisteriin, lukitustiedoston päivitys |
| Transitiivinen riippuvuus (esim. `requests`) | `python scripts/lock_files.py update --upgrade-package requests`. uv päivittää vain kyseisen paketin uusimpaan sopivaan versioon, muut versiot säilyvät. |

Tarkasta korjauksen jälkeen: `python scripts/lock_files.py check` ja `python scripts/check_vulnerabilities.py`.

## F. Tarkastus ennen pushia

Sama tarkastus ajetaan pre-push-hookina testien rinnalla:

```text
Aja testit...............................................................Passed
Tarkasta tunnetut haavoittuvuudet........................................Passed
```

Jos `main`-haaraan päätynyt paketti on saanut uuden haavoittuvuuden, myös push epäonnistuu, vaikka muutoksesi olisi pelkkä README-korjaus. PR:n pipeline hylkäisi sen joka tapauksessa samasta syystä. Hook vain kertoo sen aiemmin.

Tämä on tarkoituksellista: kun `main`-haarassa on tunnettu haavoittuvuus, sen korjaaminen on ensimmäinen tehtävä.

## G. Yöllinen tarkastus

Uusia haavoittuvuuksia julkaistaan joka päivä. PR:n tarkastus kertoo vain, että paketeissa ei ollut tunnettuja haavoittuvuuksia **mergen hetkellä**.

Siksi `azure-pipelines.yml` ajaa koko pipelinen joka yö `main`-haarasta:

```yaml
schedules:
- cron: '0 3 * * *'
  displayName: Yöllinen haavoittuvuustarkastus
  branches:
    include:
      - main
  always: true
```

`always: true` tarkoittaa, että ajo tehdään, vaikka koodi ei olisi muuttunut. Ilman sitä Azure DevOps ohittaisi yöajon, ja juuri muuttumaton koodi on se, joka pitää tarkastaa uudelleen.

Ajastetut ajot näkyvät Azure DevOpsissa pipelinen ajojen listassa. Epäonnistunut yöajo tarkoittaa, että `main`-haarassa on paketti, jolle on julkaistu haavoittuvuus.

## Mitä tarkastus ei ratkaise

- **Vain tunnetut haavoittuvuudet.** Jos paketin uusi versio on kaapattu ja siihen on lisätty haitallista koodia, siitä ei ole vielä ilmoitusta tietokannassa. Tähän auttavat oppitunnin 1 hyväksyntä ja oppitunnin 3 odotusaika uusien versioiden kanssa.
- **Työkalu ei arvioi, koskeeko haavoittuvuus juuri sinun käyttötapaasi.** Sen arvioi ihminen, ja päätös kirjataan poikkeukseen.
- **Lisenssejä ei tarkasteta.**

## Pohdittavaa

1. Miksi haavoittuvuustarkastus ajetaan pushissa eikä jokaisessa commitissa?
2. Yöajo epäonnistuu maanantaiaamuna. Kuka korjaa sen, ja mistä hän saa tiedon?
3. Milloin poikkeus on parempi ratkaisu kuin päivitys?

## Yhteenveto

| Ketjun osa | Oppitunti 4 |
| --- | --- |
| Linjaus | Lukitustiedostoissa ei saa olla tunnettuja haavoittuvuuksia, paitsi määräaikaisella poikkeuksella |
| Tarkastussääntö | `check_vulnerabilities.py`: kaikki lukitustiedostojen paketit kaikilta käyttöjärjestelmiltä |
| Hook | pre-push-hook: sama tulos kuin PR:ssä, mutta ennen pushia |
| Pipeline | Jokaisessa PR:ssä ja joka yö `main`-haarasta |
| PR-kontrolli | Poikkeukset tiedostossa `policy/vulnerability-exceptions.yml`, jolla on pakollinen katselmoija |
| Auditointievidenssi | `vulnerability-report.txt` ja `.json` pipeline-artifactissa |
