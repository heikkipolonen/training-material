# Oppitunti 1: Hyväksytyt kirjastot

## Tavoite

Kloonaat koulutuspohjan VS Codeen ja julkaiset oman kopiosi Azure Repos Gitiin. Rakennat Azure DevOpsiin pipelinen ja pakollisen PR-kontrollin, joka hylkää hyväksymättömän Python-kirjaston ennen mergeä.

## A. Paikallinen VS Code -työskentely

Kloonaa kouluttajan repository ja avaa se VS Codessa:

```powershell
git clone https://github.com/KOULUTTAJA/arcgis-approved-library-training-template.git
cd arcgis-approved-library-training-template
code .
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install pyyaml
python scripts/check_approved_libraries.py
python -m pip install -r requirements-dev.txt
python -m pytest
```

Tarkastuksen pitää palauttaa exit-koodi 0 ja tulostaa:

```text
SUORAT_RIIPPUVUUDET (requirements.txt): arcgis
SUORAT_RIIPPUVUUDET (requirements-dev.txt): pyyaml, pytest
TULOS: HYVAKSYTTY
```

Vaihtoehtoisesti: valitse `.venv` tulkiksi (**Python: Select Interpreter**) ja aja VS Code -task **Koko ketju (kuten pipeline)** (**Terminal → Run Task…**). Pelkän tarkastuksen saa ajettua pikanäppäimellä `Ctrl+Shift+B`.

## B. Oman kopion siirtäminen Azure Repos Gitiin

Luo Azure DevOpsiin tyhjä Git-repository ilman README-tiedostoa. Kopioi sen HTTPS-osoite ja vaihda paikalliseen repositoryyn uusi ensisijainen etärepositorio:

```powershell
git remote rename origin github-template
git remote add origin https://dev.azure.com/ORGANISAATIO/PROJEKTI/_git/REPOSITORIO
git push -u origin main
```

`github-template` voidaan säilyttää kouluttajan päivitysten hakemiseen. Projekti- tai asiakaskohtaisia muutoksia ei työnnetä takaisin kouluttajan GitHub-repositorioon.

## C. Azure Pipelinen luominen

1. Avaa Azure DevOpsissa **Pipelines**.
2. Valitse **New pipeline**.
3. Valitse **Azure Repos Git**.
4. Valitse oma repository.
5. Valitse **Existing Azure Pipelines YAML file**.
6. Valitse `/azure-pipelines.yml`.
7. Suorita pipeline.
8. Avaa artifact **approved-libraries-audit-evidence** ja tarkista raportit (`.txt` ja `.json`).
9. Avaa ajon **Tests**-välilehti ja tarkista tarkastussäännön testitulokset.

## D. Pakollinen PR-kontrolli

1. Avaa **Repos → Branches**.
2. Avaa `main`-haaran **Branch policies**.
3. Lisää luotu pipeline automaattiseksi ja pakolliseksi **Build validation** -kontrolliksi. Azure Repos Gitissä tämä on se, mikä käynnistää pipelinen PR:ssä; YAML:n `pr:`-triggeriä ei käytetä.
4. Vaadi vähintään yksi ihmiskatselmoija.
5. Lisää **Automatically included reviewers** -sääntö poluille `/policy/*` ja `/scripts/*` ja aseta katselmoija pakolliseksi. Muuten kehittäjä voisi samassa PR:ssä lisätä riippuvuuden ja hyväksyä sen itse muokkaamalla rekisteriä tai tarkastusskriptiä.

## E. Hyväksytty PR -harjoitus

Luo feature-haara:

```powershell
git checkout -b feature/approved-library-demo
```

Pidä `requirements.txt`-tiedostossa aktiivisena riippuvuutena vain `arcgis`. Tee esimerkiksi pieni README-muutos, commit ja push:

```powershell
git add .
git commit -m "Demonstrate approved dependency"
git push -u origin feature/approved-library-demo
```

Avaa PR kohti `main`-haaraa. Tuloksen pitää sisältää:

```text
SUORAT_RIIPPUVUUDET (requirements.txt): arcgis
SUORAT_RIIPPUVUUDET (requirements-dev.txt): pyyaml, pytest
TULOS: HYVAKSYTTY
```

Pipeline onnistuu ja auditointiraportti julkaistaan artifactina.

## F. Hylätty PR -harjoitus

Palaa `main`-haaraan, päivitä se ja luo toinen feature-haara:

```powershell
git checkout main
git pull
git checkout -b feature/unapproved-library-demo
```

Poista `requirements.txt`-tiedostossa kommenttimerkki riviltä:

```text
unknown-demo-package==1.0.0
```

Commitoi ja pushaa muutos:

```powershell
git add requirements.txt
git commit -m "Demonstrate rejected dependency"
git push -u origin feature/unapproved-library-demo
```

Avaa PR kohti `main`-haaraa. Tuloksen pitää sisältää:

```text
TULOS: HYLATTY
TUNTEMATTOMAT_KIRJASTOT: unknown-demo-package
```

Pipeline palauttaa exit-koodin 1. Pakollinen Build validation estää normaalin mergen. Tarkastusraportti löytyy silti pipeline artifactista, koska julkaisutehtävä käyttää ehtoa `condition: always()`.
