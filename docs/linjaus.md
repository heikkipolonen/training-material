# Linjaus ja minimiprototyypin rajaukset

## Linjaus

Uuden suoran riippuvuuden pitää löytyä hyväksyttyjen kirjastojen rekisteristä tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus.

## Tarkastussääntö

Linjaus koskee sekä projektin (`requirements.txt`) että kehitystyökalujen (`requirements-dev.txt`) riippuvuuksia. Kehitystyökalut ajetaan pipeline-agentilla, jolla on pääsy lähdekoodiin, joten niiden riski on samaa luokkaa.

Jokainen aktiivinen riippuvuus normalisoidaan ja sitä verrataan hyväksyttyjen kirjastojen rekisteriin (`policy/approved-libraries.yml`). Pipeline-ajo hylätään, jos:

- kirjasto ei ole rekisterissä eikä sillä ole voimassa olevaa poikkeusta
- kirjaston poikkeus on vanhentunut
- rivi viittaa pakettiin URL-osoitteella, VCS-osoitteella tai paikallisella polulla
- rivi sisältää pip-option (esim. `--extra-index-url`, `-r`, `-e`)
- rekisteri tai jokin requirements-tiedosto puuttuu tai on virheellinen.

Pipeline tarkastaa riippuvuudet ennen kuin asentaa kehitystyökalut. Ainoa ennen tarkastusta asennettava paketti on tarkastusskriptin tarvitsema PyYAML, joka on nimetty suoraan `azure-pipelines.yml`-tiedostossa.

## Poikkeukset

Poikkeus kirjataan rekisterin `exceptions`-listaan. Jokaisella poikkeuksella on pakollinen tikettiviite (`ticket`) ja päättymispäivä (`expires`). Poikkeus on voimassa päättymispäivään asti.

## Git-hookit

Git-hookit ovat kehittäjän apuväline, eivät tietoturvakontrolli: ne voi jättää asentamatta tai ohittaa (`--no-verify`). Jokainen hookina ajettava pakollinen sääntö tarkastetaan siksi myös pipelinessa.

- Vain paikalliset hookit (`repo: local`) ovat sallittuja. Kolmannen osapuolen hook-repositoriot hylätään (`scripts/check_precommit_config.py`).
- Hook-asetusten (`.pre-commit-config.yaml`) ja hook-skriptien muutoksilla on pakollinen katselmoija, koska ne ajautuvat katselmoijan koneella.
- Hookin käyttämät paketit (`additional_dependencies`) kuuluvat hyväksyttyjen kirjastojen rekisteriin samoin kuin muut kehitystyökalut.

## Rajaukset

- Tarkastus koskee vain suoria riippuvuuksia.
- Ainoa hyväksytty nimi on `arcgis`.
- Tarkastus ei arvioi pakettiversiota (versioiden lukitus on seuraavan osion aihe).
- Tarkastus ei arvioi tunnettuja haavoittuvuuksia.
- Tarkastus ei arvioi lisenssejä.
- Tarkastus ei arvioi transitiivisia riippuvuuksia (esim. `pre-commit`in omia riippuvuuksia).
- Hookien `additional_dependencies` ei tarkasteta automaattisesti rekisteriä vasten.
- Lista on vain koulutusprototyyppi, ei virallinen hyväksyntälista.
