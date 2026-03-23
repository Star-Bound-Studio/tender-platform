"""
Vsem Podryad Parser — vsem-podryad.ru
Scrapes subcontract requests (direct orders from general contractors).
"""

import logging
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

BASE_URL = "https://vsem-podryad.ru"
REQUEST_URL = f"{BASE_URL}/request"


class VsemPodryadParser:
    """Parser for vsem-podryad.ru subcontract requests."""

    def __init__(self, db_session_factory):
        self.session_factory = db_session_factory
        self.stats = {"found": 0, "new": 0, "updated": 0, "errors": 0}

    async def run(self, pages: int = 10):
        """Scrape subcontract requests."""
        logger.info(f"Starting VsemPodryad parser, {pages} pages")

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
                    requests = await self._parse_page(http, page)
                    if requests:
                        await self._save_batch(requests)
                    else:
                        break

                    import asyncio
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"  VsemPodryad page {page}: {e}")
                    self.stats["errors"] += 1

        logger.info(f"VsemPodryad done: {self.stats}")
        return self.stats

    async def _parse_page(self, http: httpx.AsyncClient, page: int) -> list[dict]:
        """Parse a page of subcontract requests."""
        resp = await http.get(REQUEST_URL, params={"page": page})
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        requests = []

        # Vsem Podryad uses card-based layout for requests
        for card in soup.select(".request-card, .order-item, .card, article"):
            try:
                req = self._extract_request(card)
                if req and req.get("title"):
                    requests.append(req)
                    self.stats["found"] += 1
            except Exception as e:
                logger.debug(f"  Card error: {e}")
                self.stats["errors"] += 1

        logger.info(f"  VsemPodryad page {page}: {len(requests)} requests")
        return requests

    def _extract_request(self, card) -> Optional[dict]:
        """Extract request data from HTML card."""
        title_el = card.select_one("h2 a, h3 a, .request-title a, .card-title a, a.title")
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        source_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Extract UUID or ID from URL
        id_match = re.search(r"([a-f0-9-]{36}|\d{5,})", href)
        source_id = id_match.group(1) if id_match else str(hash(title) % 10**10)

        # Description
        desc_el = card.select_one(".request-description, .card-text, .description, p")
        description = desc_el.get_text(strip=True) if desc_el else None

        # Category
        cat_el = card.select_one(".category, .badge, .tag, .request-category")
        category = cat_el.get_text(strip=True) if cat_el else None

        # Region
        region_el = card.select_one(".region, .location, .city, .address")
        region = region_el.get_text(strip=True) if region_el else self._extract_region(description or title)

        # Budget
        budget_text = None
        budget_min = None
        for price_el in card.select(".price, .budget, .sum, .cost"):
            price_text = price_el.get_text(strip=True)
            if price_text:
                budget_text = price_text
                budget_min = self._parse_price(price_text)
                break

        # Date
        date_el = card.select_one(".date, time, .publish-date")
        publish_date = None
        if date_el:
            date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            publish_date = self._parse_date(date_text)

        # Company name
        company_el = card.select_one(".company, .author, .customer, .organization")
        company_name = company_el.get_text(strip=True) if company_el else None

        return {
            "source_id": "vsem_podryad",
            "source_url": source_url,
            "is_user_created": False,
            "title": title[:500],
            "description": description[:2000] if description else None,
            "category": category,
            "budget_min": budget_min,
            "budget_text": budget_text,
            "region": region,
            "company_name": company_name,
            "status": "active",
            "publish_date": publish_date or date.today(),
        }

    def _extract_region(self, text: str) -> Optional[str]:
        """Try to extract region from text. Handles Russian cases (Москва/Москве/Москвы)."""
        if not text:
            return None
        # Map word stems to canonical region names
        region_stems = {
            "москв": "Москва",
            "петербург": "Санкт-Петербург",
            "московск": "Московская обл.",
            "ленинградск": "Ленинградская обл.",
            "хмао": "ХМАО-Югра",
            "янао": "ЯНАО",
            "тюменск": "Тюменская обл.",
            "свердловск": "Свердловская обл.",
            "краснодарск": "Краснодарский край",
            "челябинск": "Челябинская обл.",
            "новосибирск": "Новосибирская обл.",
            "красноярск": "Красноярский край",
            "казан": "Казань",
            "пермск": "Пермский край",
            "оренбургск": "Оренбургская обл.",
            "сахалинск": "Сахалинская обл.",
            "хабаровск": "Хабаровский край",
        }
        text_lower = text.lower()
        for stem, name in region_stems.items():
            if stem in text_lower:
                return name
        return None

    def _parse_price(self, text: str) -> Optional[Decimal]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", "").replace("\xa0", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            val = Decimal(cleaned)
            return val if val > 0 else None
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, text: str) -> Optional[date]:
        if not text:
            return None
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(text.strip()[:10], fmt).date()
            except ValueError:
                continue
        return None

    async def _save_batch(self, requests: list[dict]):
        """Save subcontract requests to DB."""
        from app.models.database import SubcontractRequest

        async with self.session_factory() as session:
            for rd in requests:
                try:
                    # Simple insert (no upsert for requests — they're unique by title+date)
                    req = SubcontractRequest(**rd)
                    session.add(req)
                    self.stats["new"] += 1
                except Exception as e:
                    logger.debug(f"  Save error: {e}")
                    await session.rollback()
                    self.stats["errors"] += 1

            try:
                await session.commit()
            except Exception as e:
                logger.error(f"  Batch commit error: {e}")
                await session.rollback()
