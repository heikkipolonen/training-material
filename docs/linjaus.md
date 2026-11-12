# Linjaus ja minimiprototyypin rajaukset

## Linjaus

Uuden suoran riippuvuuden pitää löytyä hyväksyttyjen kirjastojen rekisteristä hyväksytyssä versiossa tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus.

Jokainen asennus tehdään lukitustiedostosta hash-tarkistuksella, ja lukitustiedoston pitää vastata hyväksyttyjä riippuvuuksia.

## Tarkastussääntö

Linjaus koskee projektin (`requirements.txt`), kehitystyökalujen (`requirements-dev.txt`) ja pipelinen esivaiheen (`requirements-bootstrap.txt`) riippuvuuksia. Kehitystyökalut ajetaan pipeline-agentilla, jolla on pääsy lähdekoodiin, joten niiden riski on samaa luokkaa.

Jokainen aktiivinen riippuvuus normalisoidaan ja sitä verrataan hyväksyttyjen kirjastojen rekisteriin (`policy/approved-libraries.yml`). Pipeline-ajo hylätään, jos:

- kirjasto ei ole rekisterissä eikä sillä ole voimassa olevaa poikkeusta
- kirjaston versiota ei ole lukittu tarkkaan versioon (`nimi==X.Y.Z`)
- lukittua versiota ei ole hyväksytty rekisterissä
- kirjaston poikkeus on vanhentunut
- rivi viittaa pakettiin URL-osoitteella, VCS-osoitteella tai paikallisella polulla
- rivi sisältää pip-option (esim. `--extra-index-url`, `-r`, `-e`)
- rekisteri tai jokin requirements-tiedosto puuttuu tai on virheellinen.

## Lukitustiedostot

Jokaisesta requirements-tiedostosta generoidaan lukitustiedosto (`requirements*.lock.txt`) komennolla `python scripts/lock_files.py update`. Lukitustiedostossa on koko riippuvuuspuu, myös transitiiviset riippuvuudet, tarkkoine versioineen ja hasheineen. Se toimii Windowsissa, macOS:ssä ja Linuxissa.

- Asennukset tehdään vain lukitustiedostoista: `pip install --require-hashes --only-binary :all: -r <lukitustiedosto>`.
- Pipeline tarkastaa, että lukitustiedostot vastaavat requirements-tiedostoja (`python scripts/lock_files.py check`). Muuten PR voisi lisätä paketin suoraan lukitustiedostoon ohi hyväksyntätarkastuksen.
- Pipeline asentaa ennen tarkastuksia vain tarkastusten tarvitsemat paketit (`requirements-bootstrap.lock.txt`: PyYAML ja uv). Kehitystyökalut asennetaan vasta hyväksyttyjen tarkastusten jälkeen.
- Lukitustiedostot tallennetaan auditointievidenssiin: ne kertovat tarkalleen, mitä asennettiin.

## Haavoittuvuudet

Lukitustiedostoissa ei saa olla paketteja, joissa on tunnettu haavoittuvuus.

- Tarkastus koskee kaikkia lukitustiedostojen paketteja, myös transitiivisia ja vain muilla käyttöjärjestelmillä asennettavia (`scripts/check_vulnerabilities.py`).
- Tarkastus ajetaan pre-push-hookina, jokaisessa PR:ssä ja joka yö `main`-haarasta.
- Kun `main`-haarassa on tunnettu haavoittuvuus, myös siihen liittymättömät pushit ja PR:t hylätään, kunnes se on korjattu tai hyväksytty poikkeuksella.
- Ensisijainen korjaus on päivittää paketti korjattuun versioon. Transitiivinen riippuvuus päivitetään komennolla `python scripts/lock_files.py update --upgrade-package <paketti>`.
- Jos korjattua versiota ei voi ottaa käyttöön, haavoittuvuuden voi hyväksyä määräaikaisesti tiedostossa `policy/vulnerability-exceptions.yml` (tunniste, tiketti ja päättymispäivä).

## Poikkeukset

Poikkeus kirjataan rekisterin `exceptions`-listaan. Jokaisella poikkeuksella on pakollinen tikettiviite (`ticket`), päättymispäivä (`expires`) ja versiot (`versions`), joita se koskee. Poikkeus on voimassa päättymispäivään asti.

## Git-hookit

Git-hookit ovat kehittäjän apuväline, eivät tietoturvakontrolli: ne voi jättää asentamatta tai ohittaa (`--no-verify`). Jokainen hookina ajettava pakollinen sääntö tarkastetaan siksi myös pipelinessa.

- Vain paikalliset hookit (`repo: local`) ovat sallittuja. Kolmannen osapuolen hook-repositoriot hylätään (`scripts/check_precommit_config.py`).
- Hook-asetusten (`.pre-commit-config.yaml`) ja hook-skriptien muutoksilla on pakollinen katselmoija, koska ne ajautuvat katselmoijan koneella.
- Hookin käyttämät paketit kuuluvat hyväksyttyjen kirjastojen rekisteriin samoin kuin muut kehitystyökalut.

## Rajaukset

- Ihminen hyväksyy vain suorat riippuvuudet. Transitiiviset riippuvuudet on lukittu, ne näkyvät lukitustiedostossa ja niiden tunnetut haavoittuvuudet tarkastetaan, mutta niitä ei hyväksytä yksitellen.
- Haavoittuvuustarkastus löytää vain julkisesti raportoidut haavoittuvuudet. Se ei tunnista haitallista koodia, jolle ei ole vielä julkaistu ilmoitusta.
- Ainoa hyväksytty projektikirjasto on `arcgis`.
- Tarkastus ei arvioi lisenssejä.
- Versioita verrataan merkkijonoina: `2.4` ja `2.4.0` ovat eri versioita.
- Pull requestin muutokset tiedostoihin `azure-pipelines.yml` ja `requirements-bootstrap*` ajautuvat pipelinessa ennen tarkastuksia. Niille kannattaa asettaa pakollinen katselmoija.
- Lista on vain koulutusprototyyppi, ei virallinen hyväksyntälista.
