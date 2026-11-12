"""detect-secrets-tunnistin ArcGIS API -avaimille.

detect-secrets ei tunne ArcGIS-avaimia. Sen sisäänrakennetut tunnistimet
löytävät avaimen vain, jos se on nimetyssä muuttujassa (esim. api_key = "...")
tai konfiguraatiotiedostossa, mutta eivät esimerkiksi funktion argumentista
GIS(url, api_key="...") tai notebookista.

Tämä tunnistin löytää avaimen sen muodon perusteella mistä tahansa:

- AAPT...  nykyiset API-avaimet (API key credentials)
- AAPK...  vanhat API-avaimet (legacy), joita voi vielä olla vanhassa koodissa

Lähde: https://developers.arcgis.com/documentation/security-and-authentication/
"""

from __future__ import annotations

import re

from detect_secrets.plugins.base import RegexBasedDetector


class ArcGISApiKeyDetector(RegexBasedDetector):
    """ArcGIS API -avain: AAPT tai AAPK ja vähintään 60 merkkiä."""

    # Tunnistimen nimi, ei salaisuus. Sekä Bandit (B105) että detect-secrets
    # luulevat sitä salasanaksi, joten rivillä on molempien poikkeusmerkinnät.
    secret_type = "ArcGIS API Key"  # nosec B105  # pragma: allowlist secret
    denylist = (re.compile(r"\bAAP[KT][A-Za-z0-9_\-.]{60,}"),)
