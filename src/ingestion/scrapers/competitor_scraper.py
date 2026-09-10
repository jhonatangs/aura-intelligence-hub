"""Competitor price scraper for Red Bull and Monster Energy.

Uses asynchronous httpx and BeautifulSoup4 to harvest competitive pricing, volume,
and stock status from retail e-commerce channels with fault-tolerant parsing.
"""

import asyncio
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from types import TracebackType

import httpx
from bs4 import BeautifulSoup

from src.ingestion.models.multimodal import CompetitorPriceRecord

logger = logging.getLogger(__name__)


def parse_price_brl(price_str: str) -> float:
    """Parse monetary string in Brazilian Reais (BRL) to float.

    Handles formats:
        - 'R$ 10,99' -> 10.99
        - 'R$ 1.250,50' -> 1250.50
        - '10.99' -> 10.99
        - 'R$9,90' -> 9.90

    Args:
        price_str: Raw price text.

    Returns:
        float: Parsed price amount.

    Raises:
        ValueError: If no valid numerical amount can be parsed.
    """
    cleaned = re.sub(r"[^\d,\.]", "", price_str.strip())
    if not cleaned:
        raise ValueError(f"Unable to extract price from: '{price_str}'")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        val = float(cleaned)
        if val <= 0:
            raise ValueError(f"Parsed price must be positive, got {val}")
        return round(val, 2)
    except ValueError as err:
        raise ValueError(f"Could not convert '{price_str}' to float: {err}") from err


def extract_volume_ml(text: str) -> int:
    """Extract liquid volume in milliliters from product description text.

    Handles formats:
        - '250ml', '250 ml', '250ML' -> 250
        - '355ml' -> 355
        - '473ml' -> 473
        - '1l', '1 L', '1,5l', '2L' -> 1000, 1500, 2000

    Args:
        text: Product title or description.

    Returns:
        int: Volume in milliliters (defaults to 250 if not specified).
    """
    ml_match = re.search(r"(\d+)\s*(?:ml|m\b)", text, re.IGNORECASE)
    if ml_match:
        return int(ml_match.group(1))

    liter_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:l|litro|litros)\b", text, re.IGNORECASE)
    if liter_match:
        liters = float(liter_match.group(1).replace(",", "."))
        return int(round(liters * 1000))

    return 250


def detect_brand(text: str) -> str | None:
    """Detect competitor brand from product text.

    Args:
        text: Product text.

    Returns:
        str | None: 'RED_BULL' or 'MONSTER' if detected, else None.
    """
    lower = text.lower()
    if "red bull" in lower or "redbull" in lower:
        return "RED_BULL"
    if "monster" in lower:
        return "MONSTER"
    return None


class CompetitorPriceScraper:
    """Asynchronous competitor price scraper with error boundaries and HTML extraction.

    Attributes:
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on network error.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        user_agent: str | None = None,
    ) -> None:
        """Initialize competitor scraper.

        Args:
            client: Optional httpx.AsyncClient for connection pooling and mocking.
            timeout: Request timeout in seconds.
            max_retries: Retry attempts for transient request failures.
            user_agent: Custom User-Agent header string.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36 AuraMarketIntel/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self._external_client = client
        self._client = client or httpx.AsyncClient(timeout=timeout, headers=self.headers)

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Underlying async HTTP client."""
        return self._client

    async def fetch_html(self, url: str) -> str:
        """Fetch raw HTML content from target URL with retry logic.

        Args:
            url: Target web page URL.

        Returns:
            str: Raw HTML body string.

        Raises:
            httpx.HTTPError: If all retries fail.
        """
        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.text
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_exception = exc
                logger.warning(
                    "Scraper fetch attempt %d/%d failed for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)

        raise RuntimeError(
            f"Failed to fetch HTML from '{url}' after {self.max_retries} attempts: {last_exception}"
        ) from last_exception

    def parse_html(
        self,
        html_content: str,
        source_url: str = "",
        observation_time: datetime | None = None,
    ) -> list[CompetitorPriceRecord]:
        """Parse HTML string into validated CompetitorPriceRecord list.

        Inspects common retail card patterns, table structures, and fallback elements.

        Args:
            html_content: Raw HTML text.
            source_url: Origin URL identifier.
            observation_time: Optional explicit timestamp (defaults to current UTC).

        Returns:
            list[CompetitorPriceRecord]: Extracted and validated competitor price records.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        now = observation_time or datetime.now(UTC)
        records: list[CompetitorPriceRecord] = []

        # Strategy 1: Look for common card containers
        card_selectors = [
            ".product-card",
            ".product-item",
            ".item-card",
            "article.product",
            "li.product",
            ".ui-search-result",
            "[data-component='product-card']",
            ".product",
        ]

        card_elements = []
        for selector in card_selectors:
            matches = soup.select(selector)
            if matches:
                card_elements = matches
                break

        if card_elements:
            for card in card_elements:
                rec = self._parse_card_element(card, source_url, now)
                if rec:
                    records.append(rec)

        # Strategy 2: Fallback if no cards found - inspect all links or headings with brand keywords
        if not records:
            for heading in soup.find_all(["h1", "h2", "h3", "h4", "a", "div"]):
                title_text = heading.get_text(strip=True)
                brand = detect_brand(title_text)
                if brand and len(title_text) < 120:
                    parent = heading.find_parent(["article", "li", "div", "section"]) or heading
                    rec = self._parse_card_element(parent, source_url, now, forced_title=title_text)
                    if rec and rec not in records:
                        records.append(rec)

        logger.info("Parsed %d competitor price records from source '%s'", len(records), source_url)
        return records

    def _parse_card_element(
        self,
        element: BeautifulSoup,
        source_url: str,
        now: datetime,
        forced_title: str | None = None,
    ) -> CompetitorPriceRecord | None:
        """Extract structured record from an HTML fragment."""
        try:
            # Title extraction
            if forced_title:
                title = forced_title
            else:
                title_elem = element.select_one(
                    ".product-title, .title, h2, h3, h4, .name, [data-name]"
                )
                title = title_elem.get_text(strip=True) if title_elem else ""

            brand = detect_brand(title)
            if not brand:
                return None

            # Price extraction
            price_elem = element.select_one(
                ".price, .sales-price, .product-price, .andes-money-amount, [data-price]"
            )
            price_raw = ""
            if price_elem:
                price_attr = price_elem.get("data-price")
                price_raw = str(price_attr) if price_attr else price_elem.get_text(strip=True)
            if not price_raw:
                # Regex search within element text
                elem_text = element.get_text(" ")
                price_match = re.search(r"R\$\s*[\d\.,]+", elem_text)
                if price_match:
                    price_raw = price_match.group(0)

            if not price_raw:
                return None

            price_brl = parse_price_brl(price_raw)
            volume_ml = extract_volume_ml(title)

            # Stock status
            elem_text = element.get_text(" ").lower()
            if any(term in elem_text for term in ["esgotado", "indisponível", "out of stock"]):
                stock_status = "OUT_OF_STOCK"
            else:
                stock_status = "IN_STOCK"

            return CompetitorPriceRecord(
                competitor_brand=brand,  # type: ignore[arg-type]
                product_title=title[:255],
                volume_ml=volume_ml,
                price_brl=price_brl,
                stock_status=stock_status,  # type: ignore[arg-type]
                timestamp=now,
                source_url=source_url,
            )
        except Exception as exc:
            logger.debug("Failed to extract record from element: %s", exc)
            return None

    async def scrape_url(self, url: str) -> list[CompetitorPriceRecord]:
        """Scrape and parse competitor price records from a given URL.

        Args:
            url: Target web page URL.

        Returns:
            list[CompetitorPriceRecord]: Extracted records.
        """
        html = await self.fetch_html(url)
        return self.parse_html(html, source_url=url)

    async def scrape_urls(self, urls: Sequence[str]) -> list[CompetitorPriceRecord]:
        """Scrape multiple competitor URLs concurrently with fault isolation.

        Args:
            urls: Target URLs sequence.

        Returns:
            list[CompetitorPriceRecord]: Aggregated records.
        """
        tasks = [self.scrape_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated: list[CompetitorPriceRecord] = []
        for url, res in zip(urls, results, strict=True):
            if isinstance(res, Exception):
                logger.error("Scraping URL %s encountered error: %s", url, res)
            else:
                aggregated.extend(res)

        return aggregated

    async def __aenter__(self) -> "CompetitorPriceScraper":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self._external_client is None:
            await self._client.aclose()
