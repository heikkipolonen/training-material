# Koulutusprosessi

## Tavoite

Kouluttaja jakaa neutraalin koulutuspohjan GitHubissa. Osallistuja kloonaa sen VS Codeen ja julkaisee oman kopionsa Azure Repos Gitiin. Varsinainen pipeline sekä pakollinen PR-kontrolli toteutetaan Azure DevOpsissa.

## A. Kouluttajan GitHub-pohja

Alusta repository projektikansiossa PowerShellillä:

```powershell
git init
git add .
git commit -m "Initial approved library training template"
git branch -M main
git remote add origin https://github.com/KOULUTTAJA/arcgis-approved-library-training-template.git
git push -u origin main
```

GitHub toimii tässä vain neutraalin koulutuspohjan jakelupaikkana. Repositorioon ei luoda GitHub Actions -workflowta. Älä tallenna pohjaan asiakastietoja, tunnuksia, tokeneita tai todellisia poikkeuspäätöksiä.

## B. Osallistujan paikallinen VS Code -työskentely

Kloonaa kouluttajan repository ja avaa se VS Codessa:

```powershell
git clone https://github.com/KOULUTTAJA/arcgis-approved-library-training-template.git
cd arcgis-approved-library-training-template
code .
python scripts/check_approved_libraries.py
```

Tarkastuksen pitää palauttaa exit-koodi 0 ja tulostaa:

```text
SUORAT_RIIPPUVUUDET: arcgis
TULOS: HYVAKSYTTY
```

## C. Oman kopion siirtäminen Azure Repos Gitiin

Luo Azure DevOpsiin tyhjä Git-repository ilman README-tiedostoa. Kopioi sen HTTPS-osoite ja vaihda paikalliseen repositoryyn uusi ensisijainen etärepositorio:

```powershell
git remote rename origin github-template
git remote add origin https://dev.azure.com/ORGANISAATIO/PROJEKTI/_git/REPOSITORIO
git push -u origin main
```

`github-template` voidaan säilyttää kouluttajan päivitysten hakemiseen. Projekti- tai asiakaskohtaisia muutoksia ei työnnetä takaisin kouluttajan GitHub-repositorioon.

## D. Azure Pipelinen luominen

1. Avaa Azure DevOpsissa **Pipelines**.
2. Valitse **New pipeline**.
3. Valitse **Azure Repos Git**.
4. Valitse oma repository.
5. Valitse **Existing Azure Pipelines YAML file**.
6. Valitse `/azure-pipelines.yml`.
7. Suorita pipeline.
8. Avaa artifact **approved-libraries-audit-evidence** ja tarkista raportti.

## E. Pakollinen PR-kontrolli

1. Avaa **Repos → Branches**.
2. Avaa `main`-haaran **Branch policies**.
3. Lisää luotu pipeline automaattiseksi ja pakolliseksi **Build validation** -kontrolliksi.
4. Vaadi vähintään yksi ihmiskatselmoija.

## F. Hyväksytty PR -harjoitus

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
SUORAT_RIIPPUVUUDET: arcgis
TULOS: HYVAKSYTTY
```

Pipeline onnistuu ja auditointiraportti julkaistaan artifactina.

## G. Hylätty PR -harjoitus

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
Tuntemattomat kirjastot: unknown-demo-package
```

Pipeline palauttaa exit-koodin 1. Pakollinen Build validation estää normaalin mergen. Tarkastusraportti löytyy silti pipeline artifactista, koska julkaisutehtävä käyttää ehtoa `condition: always()`.
