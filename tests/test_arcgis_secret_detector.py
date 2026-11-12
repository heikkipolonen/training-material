"""Tests for the custom ArcGIS API key rule (uses the real detect-secrets)."""

from __future__ import annotations

import pytest

from arcgis_secret_detector import ArcGISApiKeyDetector

# Randomly generated example tokens, not real keys. The secret scan flags them
# as random-looking strings, so they are marked as accepted test data.
CURRENT_KEY = "AAPT" + "x7Kq_2mZ-pL9vB4nR8tY1wE6uI3oA5sD0fG" * 3  # pragma: allowlist secret
LEGACY_KEY = "AAPK" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8" * 2  # pragma: allowlist secret


def found(text: str) -> list[str]:
    return list(ArcGISApiKeyDetector().analyze_string(text))


@pytest.mark.parametrize(
    "line",
    [
        f'gis = GIS(url, api_key="{CURRENT_KEY}")',  # function argument
        f'api_key: {CURRENT_KEY}',  # YAML config
        f'"source": ["key = \\"{CURRENT_KEY}\\""]',  # notebook (JSON)
        f'token = "{LEGACY_KEY}"',  # legacy AAPK key
    ],
)
def test_arcgis_keys_are_found(line):
    assert found(line)


@pytest.mark.parametrize(
    "line",
    [
        'api_key = os.environ["ARCGIS_API_KEY"]',  # the correct way
        'key = "AAPK1234"',  # too short to be a key
        f'key = "AAPX{CURRENT_KEY[4:]}"',  # different prefix
    ],
)
def test_other_text_is_not_found(line):
    assert not found(line)
