# Oppitunti 3: Versioiden lukitus

## Tavoite

Oppitunneilla 1 ja 2 tarkastettiin, *mitkä* kirjastot ovat sallittuja. Versiota ei tarkastettu, joten `pip install arcgis` asensi sen version, joka sattui asennushetkellä olemaan uusin. Myöskään kirjastojen omia riippuvuuksia ei näkynyt missään.

Tällä oppitunnilla otetaan käyttöön sama malli kuin npm:ssä:

| npm | Tämä repositorio | Sisältö |
| --- | --- | --- |
| `package.json` | `requirements.txt` | Suorat riippuvuudet tarkkoine versioineen: `arcgis==2.4.4` |
| `package-lock.json` | `requirements.lock.txt` | Koko riippuvuuspuu versioineen ja hasheineen |
| `npm ci` | `pip install --require-hashes --only-binary :all: -r requirements.lock.txt` | Asentaa tarkalleen lukitustiedoston sisällön tai epäonnistuu |

Lisäksi rekisteri hyväksyy nyt **tietyt versiot**, ei pelkkää kirjaston nimeä.

## Keskeinen viesti

**`requirements.txt` kertoo, mitä halutaan. Lukitustiedosto kertoo, mitä asennetaan. Hash todistaa, ettei mitään ole vaihdettu.**

## Lähtötilanne

Tarvitset Python 3.11:n tai uudemman. Lukitustiedostot on luotu Python 3.11+:lle, ja vanhemmalla Pythonilla asennus epäonnistuu.

| Haara | Sisältö |
| --- | --- |
| `lesson/02-git-hooks` | Oppitunnin 2 lopputulos ja tämän oppitunnin lähtötilanne |
| `lesson/03-pinning` | Tämän oppitunnin valmis lopputulos |

```powershell
git fetch github-template
git checkout -b lesson/03-pinning github-template/lesson/03-pinning
git push -u origin lesson/03-pinning
```

## A. Uusi työkalu: uv

Lukitustiedoston luominen vaatii koko riippuvuuspuun selvittämistä: mitä kukin paketti tarvitsee, mitkä versiot sopivat yhteen ja mitkä hashit kuuluvat kuhunkin tiedostoon. Pip ei osaa kirjoittaa tällaista tiedostoa, joten siihen käytetään työkalua nimeltä [uv](https://docs.astral.sh/uv/).

- **uv vain luo lukitustiedostot.** Asennukset tehdään edelleen pipillä, koska uv kirjoittaa lukitustiedoston pipin ymmärtämässä muodossa.
- **Yksi lukitustiedosto kaikille käyttöjärjestelmille.** Osa paketeista asennetaan vain Windowsissa tai vain Linuxissa. uv merkitsee ne lukitustiedostoon ehdoilla, joten sama tiedosto toimii Windowsissa, macOS:ssä ja Linuxissa.
- **uv kulkee hyväksyntäprosessin läpi** kuten kaikki muutkin työkalut (oppitunti 1). Rekisterissä on hyväksytty `uv==0.13.5`. Se ei ole uusin versio: tuoreimman julkaisun sijaan valittiin yli kaksi viikkoa vanha versio. Odotusaika antaa yhteisölle aikaa huomata, jos uusi julkaisu on rikki tai kaapattu.

> Pythonin standardit ovat siirtymässä `pyproject.toml`- ja `pylock.toml`-tiedostoihin. Tässä koulutuksessa käytetään `requirements.txt`-tiedostoja, koska pip osaa asentaa niistä jo nyt hash-tarkistuksella.

## B. Asennus lukitustiedostoista

Luo uusi virtuaaliympäristö ja asenna kaikki lukitustiedostoista:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary :all: -r requirements-bootstrap.lock.txt
python scripts/check_approved_libraries.py
python scripts/lock_files.py check
python -m pip install --require-hashes --only-binary :all: -r requirements-dev.lock.txt
python -m pre_commit install --install-hooks
```

| Valitsin | Merkitys |
| --- | --- |
| `--require-hashes` | Jokaisen paketin, myös transitiivisen, hash tarkistetaan. Jos yksikin puuttuu tai ei täsmää, mitään ei asenneta. |
| `--only-binary :all:` | Vain valmiit paketit (wheel). Pakettien omaa build-koodia ei ajeta asennuksen aikana. |

Molempien tarkastusten pitää tulostaa `TULOS: HYVAKSYTTY`.

Viimeinen komento asentaa git-hookit uudelleen niin, että ne käyttävät uuden `.venv`-ympäristön Pythonia. Jos asensit hookit oppitunnilla 2 vanhemmalla Pythonilla, ensimmäinen push epäonnistuu muuten virheeseen `No matching distribution found for pytest==9.1.1`. Jos niin käy, aja `python -m pre_commit clean` ja sen jälkeen `python -m pre_commit install --install-hooks` uudelleen.

VS Codessa sama onnistuu taskilla **Koko ketju (kuten pipeline)**.

## C. Harjoitus: mitä `arcgis` toi mukanaan?

Avaa `requirements.txt` ja `requirements.lock.txt` vierekkäin VS Codessa.

1. `requirements.txt`-tiedostossa on yksi riippuvuus. Montako pakettia `requirements.lock.txt` sisältää?
2. Etsi rivi `requests==`. Mitä sen alla oleva `# via` -kommentti kertoo?
3. Etsi rivit, joissa on `sys_platform == 'win32'`. Mitä tapahtuisi Windows-käyttäjälle, jos nämä puuttuisivat?
4. `numpy` esiintyy tiedostossa kahdesti. Miksi?
5. Montako hash-riviä tiedostossa on? Kuinka moni niistä on katselmoitu PR:ssä?

Tee sama `requirements-dev.txt`:lle: neljästä kehitystyökalusta tulee 17 pakettia.

## D. Harjoitus: kirjaston päivitys

Päivitetään `pytest` versiosta 9.1.1 versioon 9.2.0 samalla prosessilla, jota käytettäisiin oikeassa projektissa.

```powershell
git checkout -b feature/upgrade-pytest
```

**1. Vaihda versio.** Muuta `requirements-dev.txt`-tiedostossa `pytest==9.1.1` muotoon `pytest==9.2.0` ja aja tarkastus:

```powershell
python scripts/check_approved_libraries.py
```

```text
TULOS: HYLATTY
HYVAKSYMATTOMAT_VERSIOT: pytest==9.2.0
KORJAUSOHJE: Käytä hyväksyttyä versiota tai hyväksytä uusi versio (policy/approved-libraries.yml) ennen mergeä.
```

Uusi versio on uusi riippuvuus, ja se pitää hyväksyä.

**2. Hyväksy versio.** Lisää versio rekisteriin `policy/approved-libraries.yml`. Oikeassa projektissa tämä on rekisterin katselmoijan päätös.

```yaml
  - name: pytest
    versions: ["9.1.1", "9.2.0"]
```

Tarkastus hyväksyy nyt versiot, mutta lukitustiedosto on vielä vanha:

```powershell
python scripts/lock_files.py check
```

```text
TULOS: HYLATTY
SYY: requirements-dev.lock.txt: Lukitustiedoston versio ei vastaa requirements-tiedostoa: pytest on 9.1.1, pitäisi olla 9.2.0
KORJAUSOHJE: Päivitä lukitustiedostot: python scripts/lock_files.py update
```

**3. Päivitä lukitustiedosto.**

```powershell
python scripts/lock_files.py update
python scripts/lock_files.py check
```

```text
TULOS: HYVAKSYTTY
```

**4. Katso muutos.** Aja `git diff requirements-dev.lock.txt`. Muuttuiko vain `pytest`, vai myös jotain muuta? PR:n katselmoija näkee täsmälleen saman.

## E. Harjoitus: muokattu hash

Etsi `requirements-dev.lock.txt`-tiedostosta paketti `cfgv==3.5.0` ja muuta sen **molempien** `--hash`-rivien viimeinen merkki joksikin muuksi.

Pip kieltäytyy asentamasta. `--dry-run` tarkistaa paketit asentamatta mitään, ja `--ignore-installed` pakottaa tarkistuksen, vaikka paketti olisi jo asennettu:

```powershell
python -m pip install --dry-run --ignore-installed --require-hashes --only-binary :all: -r requirements-dev.lock.txt
```

```text
ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE. ...
```

Myös tarkastus huomaa muutoksen:

```powershell
python scripts/lock_files.py check
```

```text
TULOS: HYLATTY
SYY: requirements-dev.lock.txt: Lukitustiedoston hash ei vastaa pakettirekisteriä: cfgv==3.5.0
```

Palauta tiedosto: `git checkout -- requirements-dev.lock.txt`.

## F. Harjoitus: paketti suoraan lukitustiedostoon

Lukitustiedostossa on satoja rivejä hasheja, eikä kukaan lue niitä PR:ssä rivi riviltä. Voisiko paketin lisätä suoraan lukitustiedostoon niin, että `requirements.txt` ja hyväksyntätarkastus ohitetaan?

Lisää `requirements-dev.lock.txt`-tiedoston loppuun:

```text
six==1.17.0 \
    --hash=sha256:4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274
```

`check_approved_libraries.py` ei huomaa mitään, koska se lukee vain requirements-tiedostoja. Siksi lukitustiedostoilla on oma tarkastuksensa:

```powershell
python scripts/lock_files.py check
```

```text
TULOS: HYLATTY
SYY: requirements-dev.lock.txt: Lukitustiedostossa on paketti, jota requirements-tiedosto ei vaadi: six==1.17.0
KORJAUSOHJE: Päivitä lukitustiedostot: python scripts/lock_files.py update
```

Sama tarkastus ajetaan commit-hookina ja pipelinessa. Palauta tiedosto: `git checkout -- requirements-dev.lock.txt`.

## G. PR-kontrollin täydennys

Pipeline asentaa `requirements-bootstrap.lock.txt`-tiedoston paketit **ennen** tarkastuksia, ja pipelinen vaiheet määritellään tiedostossa `azure-pipelines.yml`. Molemmat tulevat PR:n mukana, joten PR:n tekijä voisi muuttaa niitä. Lisää `main`-haaran Branch policyyn (ks. [01-hyvaksytyt-kirjastot.md](01-hyvaksytyt-kirjastot.md), kohta D) pakollinen katselmoija myös poluille:

```text
/azure-pipelines.yml
/requirements-bootstrap.txt
/requirements-bootstrap.lock.txt
```

## Mitä lukitus ei ratkaise

- **Transitiivisia riippuvuuksia ei hyväksytä yksitellen.** Ne on lukittu ja ne näkyvät, mutta kukaan ei ole arvioinut niitä. Tunnettujen haavoittuvuuksien automaattinen tarkastus koko lukitustiedostolle on seuraavan oppitunnin aihe.
- **Versiot ovat merkkijonoja.** `2.4` ja `2.4.0` ovat tarkastukselle eri versioita.

## Pohdittavaa

1. Miksi uusi versio pitää hyväksyä erikseen, vaikka kirjasto on jo hyväksytty?
2. Miksi pipeline ei asenna kehitystyökaluja suoraan `requirements-dev.txt`:stä, vaikka versiot on lukittu siellä?
3. Harjoituksessa D lukitustiedoston muutos näkyi PR:ssä. Mitä katselmoijan pitäisi siitä katsoa?
4. Mitä hyötyä on odottaa pari viikkoa ennen kuin ottaa uuden version käyttöön? Mitä haittaa?

## Yhteenveto

| Ketjun osa | Oppitunti 3 |
| --- | --- |
| Linjaus | Versiot hyväksytään, ja kaikki asennetaan lukitustiedostoista hash-tarkistuksella |
| Tarkastussääntö | `check_approved_libraries.py` (versiot) ja `lock_files.py check` (lukitustiedostot) |
| Hook | Molemmat tarkastukset commitissa, kun requirements-tiedostot muuttuvat |
| Pipeline | Asennukset vain lukitustiedostoista `--require-hashes`, molemmat tarkastukset |
| PR-kontrolli | Pakollinen katselmoija myös pipelinelle ja esivaiheen riippuvuuksille |
| Auditointievidenssi | Lukitustiedostot tallennetaan pipeline-artifactiin: tarkalleen mitä asennettiin |
