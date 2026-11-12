# Oppitunti 2: Git-hookit

## Tavoite

Oppitunnilla 1 pipeline estää hyväksymättömän kirjaston pääsyn `main`-haaraan. Virhe huomataan kuitenkin vasta, kun muutos on jo pushattu ja PR avattu.

Tällä oppitunnilla sama tarkastus siirretään kehittäjän omalle koneelle git-hookeiksi (*shift left*):

| Milloin | Mitä ajetaan | Työkalu |
| --- | --- | --- |
| `git commit` | Hyväksytyt kirjastot, vain paikalliset hookit | pre-commit-hook |
| `git push` | Kaikki testit | pre-push-hook |
| PR | Kaikki edellä mainitut | Azure Pipeline + Build validation |

## Keskeinen viesti

**Hook antaa nopean palautteen, mutta se ei ole tietoturvakontrolli.**

- Hookit eivät asennu automaattisesti `git clone` -komennolla. Jokainen kehittäjä ottaa ne itse käyttöön.
- `git commit --no-verify` ja `git push --no-verify` ohittavat hookit.
- Varsinainen kontrolli on edelleen pipeline ja pakollinen Build validation, joita kehittäjä ei voi ohittaa.

Hook estää siis *vahingon*, pipeline estää *ohituksen*. Tarvitaan molemmat.

## Lähtötilanne

| Haara | Sisältö |
| --- | --- |
| `lesson/01-approved-libraries` | Oppitunnin 1 lopputulos ja tämän oppitunnin lähtötilanne |
| `lesson/02-git-hooks` | Tämän oppitunnin valmis lopputulos |

Hae valmis haara kouluttajan repositoriosta:

```powershell
git fetch github-template
git checkout -b lesson/02-git-hooks github-template/lesson/02-git-hooks
git push -u origin lesson/02-git-hooks
```

Haaran ero edelliseen oppituntiin näkyy komennolla:

```powershell
git diff github-template/lesson/01-approved-libraries github-template/lesson/02-git-hooks --stat
```

## A. Uusi kehitystyökalu kulkee hyväksyntäprosessin läpi

`pre-commit` on uusi kehitystyökalu, joten se käsitellään oppitunnin 1 linjauksen mukaisesti ennen käyttöönottoa:

1. `pre-commit` lisätään tiedostoon `requirements-dev.txt`.
2. `pre-commit` lisätään rekisteriin `policy/approved-libraries.yml` perusteluineen.
3. Muutos tehdään PR:nä, ja rekisterin pakollinen katselmoija hyväksyy sen.

Valmiissa haarassa nämä on jo tehty. Ilman rekisterimerkintää pipeline hylkäisi PR:n syyllä `Hyväksymätön kirjasto: pre-commit (requirements-dev.txt)`.

> **Pohdittavaa:** `pre-commit` tuo mukanaan omia riippuvuuksiaan, joita tarkastus ei näe. Tähän palataan oppitunnilla 3 (versioiden lukitus ja transitiiviset riippuvuudet).

## B. Hookien käyttöönotto

Asenna kehitystyökalut tutussa järjestyksessä (tarkastus ennen asennusta) ja ota hookit käyttöön:

```powershell
python -m pip install pyyaml
python scripts/check_approved_libraries.py
python -m pip install -r requirements-dev.txt
python -m pre_commit install
```

Tuloksen pitää sisältää:

```text
pre-commit installed at .git/hooks/pre-commit
pre-commit installed at .git/hooks/pre-push
```

Molemmat hook-tyypit asentuvat yhdellä komennolla, koska `.pre-commit-config.yaml` sisältää asetuksen `default_install_hook_types: [pre-commit, pre-push]`.

VS Codessa sama onnistuu taskilla **Asenna git-hookit**.

Lataa samalla hookien omat ympäristöt valmiiksi. Ensimmäinen lataus vie hetken ja vaatii verkkoyhteyden:

```powershell
python -m pre_commit install --install-hooks
```

### Miten hookit on määritelty

Kaikki hookit ovat tiedostossa [`.pre-commit-config.yaml`](../.pre-commit-config.yaml), ja ne ovat tämän repositorion omia (`repo: local`). Hookit kirjoitetaan Pythonilla, joten ne toimivat samoin Windowsissa ja macOS:ssä. `language: python` luo hookille oman eristetyn ympäristön, joten hook ei riipu siitä, mikä Python-tulkki VS Codessa on valittuna.

## C. Harjoitus: hook estää hyväksymättömän kirjaston commitin

Luo harjoitushaara ja poista `requirements.txt`-tiedostossa kommenttimerkki riviltä `unknown-demo-package==1.0.0`:

```powershell
git checkout -b feature/hook-demo
git add requirements.txt
git commit -m "Try unapproved dependency"
```

Commit hylätään ennen kuin se syntyy:

```text
Tarkasta hyväksytyt kirjastot............................................Failed
- hook id: approved-libraries
- exit code: 1

TARKASTUS: ArcGIS Python -projektin hyväksytyt kirjastot
...
TULOS: HYLATTY
TUNTEMATTOMAT_KIRJASTOT: unknown-demo-package
```

> **VS Coden Source Control -näkymä:** Kun hook hylkää commitin, VS Code näyttää ponnahdusikkunan. Valitse **Show Command Output**, niin näet saman raportin. Ponnahdusikkuna jää helposti lukematta.

Tavallinen commit, joka ei muuta riippuvuuksia, ei aja tarkastusta lainkaan:

```text
Tarkasta hyväksytyt kirjastot........................(no files to check)Skipped
```

Hook ajetaan vain, kun `requirements*.txt` tai `policy/` muuttuu. Näin commitit pysyvät nopeina.

Palauta lopuksi kommenttimerkki.

## D. Harjoitus: pre-push-hook ajaa testit

Riko tarkastussääntö tarkoituksella. Muuta tiedostossa `scripts/check_approved_libraries.py` funktion `normalize_package_name` viimeinen rivi muotoon:

```python
    return re.sub(r"[-_.]+", "-", name)   # .lower() poistettu
```

Commit menee läpi, koska commit-hookit eivät aja testejä. Push kuitenkin pysähtyy:

```powershell
git commit -am "Break normalization"
git push -u origin feature/hook-demo
```

```text
Aja testit...............................................................Failed
- hook id: tests
- exit code: 1
...
FAILED tests/test_check_approved_libraries.py::test_normalize_package_name[ArcGIS-arcgis]
```

Rikkinäinen sääntö ei päädy edes pipelineen. Peru muutos:

```powershell
git reset --hard HEAD~1
```

> **Pohdittavaa:** Miksi testit ajetaan pushissa eikä jokaisessa commitissa?

## E. Harjoitus: `--no-verify` ohittaa hookin, pipeline ei

Toista harjoitus C, mutta ohita hookit:

```powershell
git commit --no-verify -am "Bypass the hook"
git push --no-verify -u origin feature/hook-demo
```

Commit ja push menevät läpi. Avaa PR kohti `main`-haaraa: pipeline hylkää sen samalla syyllä kuin hook, ja pakollinen Build validation estää mergen.

```text
Hyväksymätön kirjasto: unknown-demo-package (requirements.txt)
```

Tämä on oppitunnin tärkein havainto: hook oli kehittäjän oma apuväline, ja hänellä oli oikeus ohittaa se. Pipelinea hän ei voi ohittaa.

## F. Kolmannen osapuolen hookit

Hookit ovat koodia, jota ajetaan jokaisen kehittäjän koneella hänen omilla oikeuksillaan. Siksi linjaus sallii vain paikalliset hookit (`repo: local`). Sääntö tarkastetaan skriptillä `scripts/check_precommit_config.py` sekä hookina että pipelinessa.

Kokeile sääntöä ajamalla tarkastus suoraan, **ilman committia**. Lisää tiedoston `.pre-commit-config.yaml` loppuun:

```yaml
  - repo: https://github.com/example/some-hooks
    rev: v1.0.0
    hooks:
      - id: some-hook
```

```powershell
python scripts/check_precommit_config.py
```

```text
TARKASTUS: pre-commit-hookien alkuperä
TULOS: HYLATTY
SYY: Kolmannen osapuolen hook-repositorio ei ole sallittu: https://github.com/example/some-hooks
KORJAUSOHJE: Käytä vain paikallisia hookeja (repo: local).
```

Palauta tiedosto: `git checkout -- .pre-commit-config.yaml`.

### Miksi sääntö tarkastetaan myös pipelinessa

pre-commit lataa ja asentaa **kaikki** asetustiedoston hookit ennen kuin ajaa yhdenkään niistä. Jos kolmannen osapuolen hook lisätään ja yritetään commitoida:

1. pre-commit lataa ja asentaa kolmannen osapuolen hookin. Asennus voi jo ajaa sen koodia.
2. Vasta sitten hookit ajetaan, ja paikallinen sääntö hylkää commitin.

Hook siis estää vahingossa tehdyn commitin, mutta ei suojaa konetta, jolla commitia yritetään. Hook ei voi valvoa omaa asetustiedostoaan, koska asetustiedosto luetaan ennen kuin yksikään hook ajetaan. Pipeline ajaa tarkastusskriptin suoraan ilman pre-commitia, joten mitään ei ladata.

## G. PR-kontrollin täydennys

Hook-asetukset ja hook-skriptit ovat koodia, joka ajautuu **katselmoijan** koneella, kun hän hakee PR-haaran ja tekee siinä commitin. Lisää siksi `main`-haaran Branch policyyn (ks. [01-hyvaksytyt-kirjastot.md](01-hyvaksytyt-kirjastot.md), kohta D) pakollinen katselmoija myös polulle:

```text
/.pre-commit-config.yaml
```

Polku `/scripts/*` on jo mukana oppitunnilta 1.

## Pohdittavaa

1. Kuka vastaa siitä, että hookit on asennettu? Mitä tapahtuu uudelle kehittäjälle, joka ei asenna niitä?
2. Miksi hookin hylkäys ei riitä todisteeksi auditoinnissa, mutta pipelinen raportti riittää?
3. `additional_dependencies: [pyyaml]` ja `[pytest, pyyaml]` asennetaan PyPI:stä ilman versiolukitusta. Mitä riskejä tästä seuraa? (Oppitunti 3.)
4. Mitä muita tarkastuksia kannattaisi ajaa hookeina? Mitkä niistä ovat niin tärkeitä, että ne kuuluvat myös pipelineen?

## Yhteenveto

| Kerros | Estää | Voiko kehittäjä ohittaa? |
| --- | --- | --- |
| pre-commit-hook | Hyväksymättömän kirjaston tai hookin commitin vahingossa | Kyllä (`--no-verify`) |
| pre-push-hook | Rikkinäisten testien pushin | Kyllä (`--no-verify`) |
| Pipeline + Build validation | Mergen `main`-haaraan | Ei |
| Pakollinen katselmoija | Säännön tai rekisterin muuttamisen itse | Ei |
