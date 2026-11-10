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

## Linjaus

Uuden suoran Python-riippuvuuden pitää löytyä hyväksyttyjen kirjastojen rekisteristä tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus.

Tässä koulutusprototyypissä ainoa hyväksytty esimerkkikirjasto on `arcgis`. Rekisteri ei ole virallinen yritys- tai asiakastason hyväksyntälista.

## Paikallinen käyttö VS Codessa

Avaa repository VS Codessa ja suorita joko VS Code -task **Tarkasta hyväksytty kirjasto** tai komento:

```powershell
python scripts/check_approved_libraries.py
```

Raportti syntyy tiedostoon:

```text
artifacts/approved-libraries-report.txt
```

## Hyväksytty tapaus

`requirements.txt` sisältää aktiivisena riippuvuutena vain `arcgis`. Skripti palauttaa exit-koodin 0 ja tulostaa `TULOS: HYVAKSYTTY`.

## Hylätty tapaus

Poista `requirements.txt`-tiedostossa kommenttimerkki riviltä:

```text
unknown-demo-package==1.0.0
```

Skripti palauttaa exit-koodin 1 ja tulostaa `TULOS: HYLATTY`. Azure DevOpsissa pakolliseksi asetettu Build validation estää normaalin mergen, mutta raportti julkaistaan silti pipeline artifactina.

Tarkemmat GitHub-, VS Code- ja Azure DevOps -vaiheet ovat tiedostossa [koulutusprosessi.md](koulutusprosessi.md).
