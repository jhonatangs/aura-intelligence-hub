"""Unit tests for competitor price scraper and HTML parsing."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.ingestion.scrapers.competitor_scraper import (
    CompetitorPriceScraper,
    detect_brand,
    extract_volume_ml,
    parse_price_brl,
)


def test_parse_price_brl_valid() -> None:
    """Verify BRL price parsing across various currency formats."""
    assert parse_price_brl("R$ 9,99") == 9.99
    assert parse_price_brl("R$9,90") == 9.90
    assert parse_price_brl("R$ 1.250,50") == 1250.50
    assert parse_price_brl("14.75") == 14.75
    assert parse_price_brl(" 8,49 ") == 8.49


def test_parse_price_brl_invalid() -> None:
    """Verify ValueError is raised for non-numeric or non-positive amounts."""
    with pytest.raises(ValueError):
        parse_price_brl("grátis")
    with pytest.raises(ValueError):
        parse_price_brl("R$ 0,00")
    with pytest.raises(ValueError):
        parse_price_brl("")


def test_extract_volume_ml() -> None:
    """Verify extraction of fluid volume across unit specifications."""
    assert extract_volume_ml("Red Bull Energy Drink 250ml") == 250
    assert extract_volume_ml("Red Bull Sugarfree 355 ml Lata") == 355
    assert extract_volume_ml("Monster Energy Ultra Paradise 473mL") == 473
    assert extract_volume_ml("Monster Energy Mega 1 Litro") == 1000
    assert extract_volume_ml("Red Bull Melancia") == 250  # Default


def test_detect_brand() -> None:
    """Verify brand detection and normalization."""
    assert detect_brand("Red Bull Energy Drink Lata") == "RED_BULL"
    assert detect_brand("RedBull Sugar Free 250ml") == "RED_BULL"
    assert detect_brand("Monster Energy Green 473ml") == "MONSTER"
    assert detect_brand("Guaraná Antarctica 350ml") is None


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="product-card">
        <h2 class="product-title">Red Bull Energy Drink 250ml</h2>
        <span class="price">R$ 9,89</span>
        <span class="stock-status">Disponível</span>
    </div>
    <div class="product-card">
        <h2 class="product-title">Monster Energy Mango Loco 473ml</h2>
        <span class="price">R$ 11,50</span>
        <span class="stock-status">Esgotado</span>
    </div>
    <div class="product-card">
        <h2 class="product-title">Coca-Cola 350ml</h2>
        <span class="price">R$ 5,00</span>
    </div>
</body>
</html>
"""


def test_parse_html_products() -> None:
    """Verify structured parsing of product cards with stock status and brand filtering."""
    scraper = CompetitorPriceScraper()
    records = scraper.parse_html(SAMPLE_HTML, source_url="https://mock-shop.com")

    assert len(records) == 2

    red_bull = next(r for r in records if r.competitor_brand == "RED_BULL")
    assert red_bull.product_title == "Red Bull Energy Drink 250ml"
    assert red_bull.volume_ml == 250
    assert red_bull.price_brl == 9.89
    assert red_bull.stock_status == "IN_STOCK"
    assert red_bull.source_url == "https://mock-shop.com"

    monster = next(r for r in records if r.competitor_brand == "MONSTER")
    assert monster.product_title == "Monster Energy Mango Loco 473ml"
    assert monster.volume_ml == 473
    assert monster.price_brl == 11.50
    assert monster.stock_status == "OUT_OF_STOCK"


@pytest.mark.anyio
async def test_scrape_url_async_mock() -> None:
    """Verify async URL scraping with mocked httpx response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    scraper = CompetitorPriceScraper(client=mock_client)
    records = await scraper.scrape_url("https://mock-retailer.com/energy")

    assert len(records) == 2
    mock_client.get.assert_called_once_with(
        "https://mock-retailer.com/energy", follow_redirects=True
    )


@pytest.mark.anyio
async def test_scrape_urls_concurrent_fault_isolation() -> None:
    """Verify concurrent scraping isolates exceptions and gathers valid results."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # First URL succeeds, second URL fails
    async def _mock_get(url: str, **kwargs: dict) -> MagicMock:
        if "failing" in url:
            raise httpx.ConnectError("Network unreachable")
        return mock_response

    mock_client.get.side_effect = _mock_get

    scraper = CompetitorPriceScraper(client=mock_client, max_retries=1)
    records = await scraper.scrape_urls(["https://ok.com/energy", "https://failing.com/energy"])

    # Valid results from ok.com are preserved
    assert len(records) == 2


@pytest.mark.anyio
async def test_scraper_context_manager() -> None:
    """Verify async context manager lifecycle closes client."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    patch_target = "src.ingestion.scrapers.competitor_scraper.httpx.AsyncClient"
    with patch(patch_target, return_value=mock_client):
        async with CompetitorPriceScraper() as scraper:
            assert scraper.http_client is mock_client
        mock_client.aclose.assert_called_once()
