# Oppitunti 5: Oma koodi – SAST ja salaisuudet

## Tavoite

Oppitunnit 1–4 käsittelivät **muiden koodia**: kirjastoja, joista projekti riippuu (SCA, *Software Composition Analysis*). Tällä oppitunnilla tarkastetaan **omaa koodia**:

| Tarkastus | Työkalu | Etsii |
| --- | --- | --- |
| SAST (*Static Application Security Testing*) | [Bandit](https://pypi.org/project/bandit/) | Tunnettuja riskialttiita koodimalleja, esim. `verify=False`, `shell=True` |
| Salaisuudet | [detect-secrets](https://pypi.org/project/detect-secrets/) ja oma ArcGIS-tunnistin | Salasanoja ja API-avaimia koodissa, konfiguraatioissa ja notebookeissa |

Molemmat lukevat koodia ajamatta sitä.

## Keskeinen viesti

**Työkalut löytävät tunnetut mallit, eivät kaikkea.** Ne ovat hyvä verkko, mutta eivät korvaa koodikatselmointia.

**Pushattu salaisuus on vuotanut.** Sitä ei korjata poistamalla se koodista, vaan mitätöimällä se ja luomalla uusi.

## Lähtötilanne

| Haara | Sisältö |
| --- | --- |
| `lesson/04-vulnerability-scanning` | Oppitunnin 4 lopputulos ja tämän oppitunnin lähtötilanne |
| `lesson/05-sast-and-secrets` | Tämän oppitunnin valmis lopputulos |

```powershell
git fetch github-template
git checkout -b lesson/05-sast-and-secrets github-template/lesson/05-sast-and-secrets
git push -u origin lesson/05-sast-and-secrets
python -m pip install --require-hashes --only-binary :all: -r requirements-dev.lock.txt
python -m pre_commit install --install-hooks
```

## A. Työkalut

Molemmat työkalut kulkivat saman hyväksyntäprosessin läpi kuin muutkin (oppitunnit 1 ja 3): rekisteri, `requirements-dev.txt` ja lukitustiedosto.

**Bandit** on PyCQA:n ylläpitämä Python-koodin SAST-työkalu. Sen säännöt ovat sisäänrakennettuja, joten se ei lataa mitään verkosta.

**detect-secrets** (Yelp) tunnistaa salaisuudet avainsanoista (`password`, `api_key`, `token` …) ja satunnaisen näköisistä merkkijonoista. Huomioitavaa:

- **Ylläpito on hidastunut.** Viimeisin julkaisu on toukokuulta 2024. Tunnistus toimii, mutta uusia avainmuotoja ei lisätä. Tässä koulutuksessa se valittiin, koska se on Python-paketti ja kulkee saman hyväksyntä- ja lukitusprosessin läpi kuin muut työkalut.
- **Parempi vaihtoehto oikeaan projektiin on [Betterleaks](https://github.com/betterleaks/betterleaks)**, gitleaksin alkuperäisen tekijän aktiivisesti ylläpidetty työkalu. Se on Go-ohjelma, joten se asennetaan lataamalla ohjelma ja tarkistamalla sen tarkistussumma, ei pipillä.
- **Tarkastus ajetaan aina valitsimella `--no-verify`.** Ilman sitä detect-secrets voi kokeilla löytämiään avaimia palveluntarjoajan rajapintaa vasten.

### Oma ArcGIS-tunnistin

detect-secrets ei tunne ArcGIS-avaimia. Ilman omaa sääntöä se ei löydä avainta funktion argumentista (`GIS(url, api_key="...")`) eikä notebookista, eli juuri sieltä, minne ArcGIS-avain useimmiten päätyy.

`scripts/arcgis_secret_detector.py` tunnistaa avaimen sen muodon perusteella mistä tahansa tiedostosta:

- `AAPT…`: nykyiset API-avaimet
- `AAPK…`: vanhat (legacy) API-avaimet

Saman periaatteen mukaan organisaatio voi lisätä omien järjestelmiensä avainmuodot.

## B. Esimerkkikoodi

`src/paivita_kohteet.py` on lyhyt ArcGIS-skripti, joka lukee portaalin osoitteen ja API-avaimen ympäristömuuttujista:

```python
def connect() -> GIS:
    url = os.environ["ARCGIS_URL"]
    api_key = os.environ["ARCGIS_API_KEY"]
    return GIS(url, api_key=api_key)
```

Tämä on oikea tapa: avain ei ole koodissa eikä missään tiedostossa, joka voi päätyä versionhallintaan.

## C. Aja tarkastukset

```powershell
python scripts/check_secrets.py
python scripts/check_sast.py
```

```text
TARKASTUS: Salaisuudet (detect-secrets)
TULOS: HYVAKSYTTY

TARKASTUS: Oman koodin tietoturvatarkastus (SAST, Bandit)
KOHTEET: src, scripts
TULOS: HYVAKSYTTY
OHITETUT_NOSEC: 11
```

`OHITETUT_NOSEC: 11` kertoo, että koodissa on 11 perusteltua poikkeusta. Niistä lisää kohdassa G.

Molemmat ajetaan myös commit-hookeina ja pipelinessa. Pipelinessa löydös näkyy PR:ssä suoraan oikean tiedoston oikealla rivillä.

## D. Harjoitus: API-avain koodissa

```powershell
git checkout -b feature/secret-demo
```

Luo harjoitusta varten satunnainen, avaimen näköinen merkkijono. Se ei ole oikea avain:

```powershell
python -c "import secrets; print('AAPT' + secrets.token_urlsafe(72))"
```

Vaihda `src/paivita_kohteet.py`-tiedostossa rivi `return GIS(url, api_key=api_key)` muotoon `return GIS(url, api_key="<tulostunut merkkijono>")` ja yritä commitoida:

```powershell
git commit -am "Try a key in code"
```

```text
Tarkasta salaisuudet.....................................................Failed
SALAISUUS: src/paivita_kohteet.py:28 (ArcGIS API Key, Base64 High Entropy String, Secret Keyword)
```

Commit estyi ennen kuin avain päätyi versionhallintaan. Palauta tiedosto: `git checkout -- src/paivita_kohteet.py`.

## E. Harjoitus: varmenteen tarkistus pois päältä

Luo tiedosto `src/lataa.py`:

```python
import requests

requests.get("https://example.com", verify=False, timeout=10)
```

```powershell
git add src/lataa.py
git commit -m "Try verify=False"
```

```text
Tarkasta oma koodi (SAST)................................................Failed
LOYDOS: src/lataa.py:3 B501 (HIGH) Call to requests with verify=False disabling SSL certificate checks, security issue.
```

`verify=False` poistaa palvelimen varmenteen tarkistuksen, jolloin yhteys voidaan kaapata. Poista tiedosto.

## F. Harjoitus: mitä työkalut eivät löydä

Vaihda `src/paivita_kohteet.py`-tiedostossa rivi `return GIS(url, api_key=api_key)` muotoon, jossa käyttäjätunnus ja salasana annetaan suoraan argumentteina:

```python
    return GIS(url, "admin", "Salasana123")  # pragma: allowlist secret
```

Poista rivin lopusta `# pragma: allowlist secret` (se on tässä vain, jotta tämä ohje itse läpäisee tarkastuksen) ja commitoi.

**Commit menee läpi.** Kumpikaan työkalu ei tiedä, että toinen argumentti on salasana, koska sen vieressä ei ole nimeä kuten `password=`. Samoin ArcGIS-kohtainen `GIS(url, ..., verify_cert=False)` menee läpi, koska Bandit tuntee vain yleiset Python-kirjastot.

Työkalut ovat verkko, eivät takuu. Tämän rivin pitää jäädä kiinni koodikatselmoinnissa.

Peru commit: `git reset --hard HEAD~1`.

## G. Väärä hälytys ja perusteltu poikkeus

Joskus tarkastus löytää jotain, mikä ei ole ongelma. Poikkeus merkitään riville, ja **perustelu kirjoitetaan edelliselle riville**, jotta katselmoija näkee sen:

| Työkalu | Poikkeusmerkintä |
| --- | --- |
| Bandit | `# nosec B603` (löydöksen tunniste) |
| detect-secrets | `# pragma: allowlist secret` |

Repositoriossa on oikeita esimerkkejä. Avaa `scripts/lock_files.py` ja etsi `nosec`:

```python
# uv ajetaan kiinteällä komennolla ilman shelliä; ks. uv_compile.
import subprocess  # nosec B404
```

Ja `scripts/arcgis_secret_detector.py`, jonka yksi rivi hämää molempia työkaluja:

```python
    # Tunnistimen nimi, ei salaisuus. Sekä Bandit (B105) että detect-secrets
    # luulevat sitä salasanaksi, joten rivillä on molempien poikkeusmerkinnät.
    secret_type = "ArcGIS API Key"  # nosec B105  # pragma: allowlist secret
```

Poikkeusmerkintä on koodimuutos kuten muutkin, ja katselmoija arvioi sen perustelun. Banditin raportti kertoo poikkeusten määrän (`OHITETUT_NOSEC`), joten niiden lisääntyminen näkyy.

## H. Kun salaisuus on jo pushattu

Jos salaisuus on päätynyt etärepositorioon, se on vuotanut, vaikka se poistettaisiin heti:

- Se on edelleen git-historiassa ja jokaisessa kloonissa.
- Se on voinut jo päätyä välimuisteihin, lokeihin tai jonkun koneelle.

Oikea korjaus:

1. **Mitätöi avain heti** ja luo uusi (ArcGIS: portaalin *Developer credentials*).
2. Siirrä uusi avain ympäristömuuttujaan tai salaisuuksien hallintaan.
3. Selvitä, onko vanhaa avainta ehditty käyttää (portaalin käyttölokit).

Historian siivous on vasta viimeinen vaihe, eikä se yksin riitä. Siksi salaisuuksien tarkastus on commit-hook: halvin hetki pysäyttää salaisuus on ennen kuin se lähtee koneelta.

## Mitä tarkastukset eivät ratkaise

- Salaisuudet, joiden vieressä ei ole tunnistettavaa nimeä tai muotoa (harjoitus F).
- Kirjastokohtaiset vaaralliset asetukset, joita työkalu ei tunne (esim. ArcGISin `verify_cert=False`).
- Logiikkavirheet, kuten väärät käyttöoikeustarkistukset. Työkalu ei tiedä, mitä koodin pitäisi tehdä.
- Git-historiassa jo olevat salaisuudet. Tarkastus katsoo vain nykyisiä tiedostoja.

## Pohdittavaa

1. Bandit luokittelee koodiin kirjoitetun salasanan vakavuudeltaan matalaksi (LOW). Miksi tässä repositoriossa jokainen löydös silti hylkää tarkastuksen?
2. Milloin `# nosec` on perusteltu? Kuka sen hyväksyy?
3. detect-secrets on Python-paketti, jonka ylläpito on hidastunut. Betterleaks on aktiivisesti ylläpidetty, mutta asennetaan eri tavalla. Kumman valitsisit omaan projektiisi ja miksi?
4. Miksi salaisuuksien tarkastus ajetaan commitissa, mutta haavoittuvuustarkastus (oppitunti 4) vasta pushissa?

## Yhteenveto

| Ketjun osa | Oppitunti 5 |
| --- | --- |
| Linjaus | Koodissa ei saa olla salaisuuksia eikä tunnettuja riskialttiita koodimalleja, paitsi perustellulla poikkeuksella |
| Tarkastussääntö | `check_secrets.py` (detect-secrets ja ArcGIS-tunnistin) ja `check_sast.py` (Bandit, jokainen löydös hylkää) |
| Hook | Molemmat commitissa |
| Pipeline | Molemmat jokaisessa PR:ssä, löydökset oikealla rivillä |
| PR-kontrolli | Poikkeusmerkinnät katselmoidaan kuten muukin koodi |
| Auditointievidenssi | `secrets-report` ja `sast-report` pipeline-artifactissa, poikkeusten määrä raportissa |
