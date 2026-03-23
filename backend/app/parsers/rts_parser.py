"""
RTS-tender Parser — rts-tender.ru
Scrapes commercial tenders from RTS electronic trading platform.
Uses their public search API/HTML pages.
"""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

BASE_URL = "https://www.rts-tender.ru"
SEARCH_URL = f"{BASE_URL}/poisk/poisk"


class RTSParser:
    """Parser for rts-tender.ru commercial tenders."""

    def __init__(self, db_session_factory):
        self.session_factory = db_session_factory
        self.stats = {"found": 0, "new": 0, "updated": 0, "errors": 0}

    async def run(self, pages: int = 10):
        """Scrape RTS tender search results."""
        logger.info(f"Starting RTS parser, {pages} pages")

        async with httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
            follow_redirects=True,
        ) as http:
            for page in range(1, pages + 1):
                try:
                    tenders = await self._parse_page(http, page)
                    if tenders:
                        await self._save_batch(tenders)
                    else:
                        logger.info(f"  No results on page {page}, stopping")
                        break

                    # Rate limiting
                    import asyncio
                    await asyncio.sleep(1.5)

                except Exception as e:
                    logger.error(f"  RTS page {page} error: {e}")
                    self.stats["errors"] += 1

        logger.info(f"RTS parser done: {self.stats}")
        return self.stats

    async def _parse_page(self, http: httpx.AsyncClient, page: int) -> list[dict]:
        """Parse a single search results page."""
        resp = await http.get(SEARCH_URL, params={
            "page": page,
            "perPage": 50,
            "sortField": "PublishDate",
            "sortDirection": "desc",
        })

        if resp.status_code != 200:
            logger.warning(f"  RTS returned {resp.status_code} for page {page}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        tenders = []

        # Parse tender cards from search results
        for card in soup.select(".search-results__item, .tender-card, .lot-item"):
            try:
                tender = self._extract_tender(card)
                if tender and tender.get("source_number"):
                    tenders.append(tender)
                    self.stats["found"] += 1
            except Exception as e:
                logger.debug(f"  Card parse error: {e}")
                self.stats["errors"] += 1

        logger.info(f"  RTS page {page}: {len(tenders)} tenders")
        return tenders

    def _extract_tender(self, card) -> Optional[dict]:
        """Extract tender data from HTML card element."""
        # Try various selectors (RTS changes layout periodically)
        title_el = card.select_one("a.tender-title, .search-results__title a, h3 a, .lot-title a")
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        source_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Extract tender number from URL or text
        number_match = re.search(r"(\d{10,})", href) or re.search(r"№\s*(\S+)", card.get_text())
        source_number = number_match.group(1) if number_match else ""

        if not source_number:
            return None

        # Price
        price_el = card.select_one(".price, .tender-price, .nmck, .lot-price")
        nmck = self._parse_price(price_el.get_text() if price_el else "")

        # Customer
        org_el = card.select_one(".organization, .customer, .tender-org, .lot-customer")
        customer_name = org_el.get_text(strip=True) if org_el else None

        # Region
        region_el = card.select_one(".region, .tender-region, .lot-region, .address")
        region = region_el.get_text(strip=True) if region_el else None

        # Date
        date_el = card.select_one(".date, .publish-date, .tender-date")
        publish_date = self._parse_date(date_el.get_text(strip=True) if date_el else "")

        # Deadline
        deadline_el = card.select_one(".deadline, .end-date, .tender-deadline")
        deadline = self._parse_date(deadline_el.get_text(strip=True) if deadline_el else "")

        return {
            "source_id": "rts",
            "source_number": f"RTS-{source_number}",
            "source_url": source_url,
            "title": title[:5000],
            "description": None,
            "law_type": "commercial",
            "purchase_type": "auction",
            "okved_codes": [],
            "okpd_codes": [],
            "nmck": nmck,
            "currency": "RUB",
            "customer_name": customer_name,
            "customer_inn": None,
            "region": region,
            "publish_date": publish_date,
            "deadline": deadline,
            "status": "active",
        }

    def _parse_price(self, text: str) -> Optional[Decimal]:
        """Parse price from text like '12 500 000,00 руб.' or '1.500.000'"""
        if not text:
            return None
        # Remove all whitespace (including non-breaking)
        cleaned = text.replace("\xa0", " ").replace("\u202f", " ")
        # Remove non-numeric except comma, dot, space
        cleaned = re.sub(r"[^\d,. ]", "", cleaned).strip()
        if not cleaned:
            return None
        # Remove spaces (thousand separators)
        cleaned = cleaned.replace(" ", "")
        # Handle formats:
        # 12500000,00 -> 12500000.00 (comma = decimal)
        # 1.500.000 -> 1500000 (dots = thousand separators)
        # 12500000.00 -> 12500000.00 (dot = decimal)
        # 1.500.000,00 -> 1500000.00 (dots = thousands, comma = decimal)
        if "," in cleaned and "." in cleaned:
            # Both present: dots are thousands, comma is decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            # Only comma: it's decimal separator
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif cleaned.count(".") > 1:
            # Multiple dots: thousand separators
            cleaned = cleaned.replace(".", "")
        # else: single dot = decimal, leave as is
        try:
            val = Decimal(cleaned)
            return val if val > 0 else None
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse date from various formats."""
        if not text:
            return None
        for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(text.strip()[:16], fmt)
            except ValueError:
                continue
        return None

    async def _save_batch(self, tenders: list[dict]):
        """Upsert batch of tenders."""
        from app.models.database import Tender

        async with self.session_factory() as session:
            for td in tenders:
                try:
                    stmt = pg_insert(Tender.__table__).values(**td)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_tender_source",
                        set_={"title": stmt.excluded.title, "nmck": stmt.excluded.nmck, "updated_at": datetime.utcnow()},
                    )
                    await session.execute(stmt)
                    self.stats["new"] += 1
                except Exception as e:
                    logger.debug(f"  Upsert error: {e}")
                    self.stats["errors"] += 1
            await session.commit()
