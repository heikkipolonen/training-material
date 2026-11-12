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

## Rajaukset

- Tarkastus koskee vain suoria riippuvuuksia.
- Ainoa hyväksytty nimi on `arcgis`.
- Tarkastus ei arvioi pakettiversiota (versioiden lukitus on seuraavan osion aihe).
- Tarkastus ei arvioi tunnettuja haavoittuvuuksia.
- Tarkastus ei arvioi lisenssejä.
- Tarkastus ei arvioi transitiivisia riippuvuuksia.
- Lista on vain koulutusprototyyppi, ei virallinen hyväksyntälista.
