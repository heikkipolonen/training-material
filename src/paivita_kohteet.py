"""Esimerkki: ArcGIS-skripti, joka listaa käyttäjän sisältökohteet.

Tunnistetiedot luetaan ympäristömuuttujista, ei koskaan koodista:

    ARCGIS_URL       esim. https://organisaatio.maps.arcgis.com
    ARCGIS_API_KEY   API-avain (AAPT...)

PowerShell:

    $env:ARCGIS_URL = "https://organisaatio.maps.arcgis.com"
    $env:ARCGIS_API_KEY = "<avain>"
    python src/paivita_kohteet.py

Avainta ei tallenneta mihinkään tiedostoon, joka voi päätyä versionhallintaan.
"""

from __future__ import annotations

import os

from arcgis.gis import GIS


def connect() -> GIS:
    """Yhdistä ArcGIS-portaaliin ympäristömuuttujien tunnistetiedoilla."""
    url = os.environ["ARCGIS_URL"]
    api_key = os.environ["ARCGIS_API_KEY"]
    return GIS(url, api_key=api_key)


def main() -> None:
    gis = connect()
    for item in gis.content.search(query="owner:me", max_items=10):
        print(f"{item.type}: {item.title}")


if __name__ == "__main__":
    main()
