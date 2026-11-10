# Linjaus ja minimiprototyypin rajaukset

## Linjaus

Uuden suoran riippuvuuden pitää löytyä hyväksyttyjen kirjastojen rekisteristä tai sillä pitää olla dokumentoitu ja hyväksytty poikkeus.

## Tarkastussääntö

Jokainen `requirements.txt`-tiedoston aktiivinen riippuvuus normalisoidaan ja sitä verrataan hyväksyttyjen kirjastojen rekisteriin. Tuntematon kirjasto hylkää pipeline-ajon.

## Rajaukset

- Tarkastus koskee vain suoria riippuvuuksia.
- Ainoa hyväksytty nimi on `arcgis`.
- Tarkastus ei arvioi pakettiversiota.
- Tarkastus ei arvioi tunnettuja haavoittuvuuksia.
- Tarkastus ei arvioi lisenssejä.
- Tarkastus ei arvioi transitiivisia riippuvuuksia.
- Poikkeus käsitellään tässä minimimallissa manuaalisesti.
- Lista on vain koulutusprototyyppi, ei virallinen hyväksyntälista.
