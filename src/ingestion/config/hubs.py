"""Logistics hubs configuration registry.

Defines spatial coordinates, climatic tracking metadata, and geographical identifiers
for multi-region distribution centers across Brazil.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DistributionHub:
    """Immutable representation of a regional distribution center.

    Attributes:
        hub_id: Unique alphanumeric identifier for the logistics hub.
        name: Human-readable hub facility name.
        city: City where the hub is located.
        state: Two-letter Brazilian state abbreviation (UF).
        latitude: Geographic latitude in decimal degrees.
        longitude: Geographic longitude in decimal degrees.
        timezone: Canonical IANA timezone identifier.
    """

    hub_id: str
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    timezone: str = "America/Sao_Paulo"


DISTRIBUTION_HUBS: tuple[DistributionHub, ...] = (
    DistributionHub(
        hub_id="HUB-SP",
        name="São Paulo Central Hub",
        city="São Paulo",
        state="SP",
        latitude=-23.5505,
        longitude=-46.6333,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-RJ",
        name="Rio de Janeiro Coastal Hub",
        city="Rio de Janeiro",
        state="RJ",
        latitude=-22.9068,
        longitude=-43.1729,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-BH",
        name="Belo Horizonte Hub",
        city="Belo Horizonte",
        state="MG",
        latitude=-19.9167,
        longitude=-43.9345,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-PR",
        name="Curitiba Southern Hub",
        city="Curitiba",
        state="PR",
        latitude=-25.4290,
        longitude=-49.2671,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-RS",
        name="Porto Alegre Far-South Hub",
        city="Porto Alegre",
        state="RS",
        latitude=-30.0346,
        longitude=-51.2177,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-BA",
        name="Salvador Northeast Hub",
        city="Salvador",
        state="BA",
        latitude=-12.9714,
        longitude=-38.5014,
        timezone="America/Bahia",
    ),
    DistributionHub(
        hub_id="HUB-PE",
        name="Recife Coastal Northeast Hub",
        city="Recife",
        state="PE",
        latitude=-8.0476,
        longitude=-34.8770,
        timezone="America/Recife",
    ),
    DistributionHub(
        hub_id="HUB-CE",
        name="Fortaleza Northern Hub",
        city="Fortaleza",
        state="CE",
        latitude=-3.7319,
        longitude=-38.5267,
        timezone="America/Fortaleza",
    ),
    DistributionHub(
        hub_id="HUB-GO",
        name="Goiânia Center-West Hub",
        city="Goiânia",
        state="GO",
        latitude=-16.6869,
        longitude=-49.2648,
        timezone="America/Sao_Paulo",
    ),
    DistributionHub(
        hub_id="HUB-MT",
        name="Cuiabá Pantanal Hub",
        city="Cuiabá",
        state="MT",
        latitude=-15.6014,
        longitude=-56.0979,
        timezone="America/Cuiaba",
    ),
)


def get_all_hubs() -> list[DistributionHub]:
    """Retrieve list of all configured logistics distribution hubs.

    Returns:
        list[DistributionHub]: Registered distribution hubs.
    """
    return list(DISTRIBUTION_HUBS)


def get_hub_by_id(hub_id: str) -> DistributionHub | None:
    """Look up distribution hub by unique identifier.

    Args:
        hub_id: Unique hub identifier (e.g., 'HUB-SP' or 'SP').

    Returns:
        DistributionHub | None: Matching hub or None if not found.
    """
    normalized = hub_id.strip().upper()
    for hub in DISTRIBUTION_HUBS:
        if hub.hub_id.upper() == normalized or hub.state.upper() == normalized:
            return hub
    return None
