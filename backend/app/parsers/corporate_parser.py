"""
Corporate Parsers — Rosneft, Gazprom
Scrapes procurement pages from major Russian corporations.
Each corporation has its own subclass with specific selectors.
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


class BaseCorporateParser:
    """Base class for corporate procurement parsers."""

    source_id: str = ""
    base_url: str = ""
    search_path: str = ""

    def __init__(self, db_session_factory):
        self.session_factory = db_session_factory
        self.stats = {"found": 0, "new": 0, "updated": 0, "errors": 0}

    async def run(self, pages: int = 5):
        logger.info(f"Starting {self.source_id} parser")

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
                        break

                    import asyncio
                    await asyncio.sleep(2)  # Polite rate limiting
                except Exception as e:
                    logger.error(f"  {self.source_id} page {page}: {e}")
                    self.stats["errors"] += 1

        logger.info(f"{self.source_id} done: {self.stats}")
        return self.stats

    async def _parse_page(self, http: httpx.AsyncClient, page: int) -> list[dict]:
        """Override in subclass."""
        raise NotImplementedError

    def _parse_price(self, text: str) -> Optional[Decimal]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", "").replace("\xa0", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, text: str) -> Optional[datetime]:
        if not text:
            return None
        for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(text.strip()[:16], fmt)
            except ValueError:
                continue
        return None

    async def _save_batch(self, tenders: list[dict]):
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
                    self.stats["errors"] += 1
            await session.commit()


class RosneftParser(BaseCorporateParser):
    """Parser for tenders.rosneft.ru"""

    source_id = "rosneft"
    base_url = "https://tenders.rosneft.ru"
    search_path = "/tenders"

    async def _parse_page(self, http: httpx.AsyncClient, page: int) -> list[dict]:
        resp = await http.get(f"{self.base_url}{self.search_path}", params={
            "page": page, "status": "open",
        })
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        tenders = []

        for row in soup.select("table.tenders-table tbody tr, .tender-item, .procurement-item"):
            try:
                cells = row.select("td")
                if len(cells) < 3:
                    # Try div-based layout
                    title_el = row.select_one("a, .title, h3")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    number_match = re.search(r"(\d{6,})", href + title)
                    number = f"RSN-{number_match.group(1)}" if number_match else f"RSN-{hash(title) % 10**8}"

                    price_el = row.select_one(".price, .sum, .nmck")
                    region_el = row.select_one(".region, .location")

                    tenders.append({
                        "source_id": self.source_id,
                        "source_number": number,
                        "source_url": f"{self.base_url}{href}" if not href.startswith("http") else href,
                        "title": title[:5000],
                        "law_type": "corporate",
                        "purchase_type": "other",
                        "okved_codes": [],
                        "okpd_codes": [],
                        "nmck": self._parse_price(price_el.get_text() if price_el else ""),
                        "currency": "RUB",
                        "customer_name": "ПАО «НК «Роснефть»",
                        "region": region_el.get_text(strip=True) if region_el else None,
                        "status": "active",
                    })
                    self.stats["found"] += 1
                    continue

                # Table-based layout
                number = cells[0].get_text(strip=True) or f"RSN-{page}-{len(tenders)}"
                title = cells[1].get_text(strip=True) if len(cells) > 1 else "Закупка Роснефть"
                link_el = cells[1].select_one("a") if len(cells) > 1 else None
                href = link_el.get("href", "") if link_el else ""

                tenders.append({
                    "source_id": self.source_id,
                    "source_number": f"RSN-{number}",
                    "source_url": f"{self.base_url}{href}" if href and not href.startswith("http") else href or self.base_url,
                    "title": title[:5000],
                    "law_type": "corporate",
                    "purchase_type": "other",
                    "okved_codes": [],
                    "okpd_codes": [],
                    "nmck": self._parse_price(cells[2].get_text() if len(cells) > 2 else ""),
                    "currency": "RUB",
                    "customer_name": "ПАО «НК «Роснефть»",
                    "status": "active",
                })
                self.stats["found"] += 1

            except Exception as e:
                logger.debug(f"  Row parse error: {e}")
                self.stats["errors"] += 1

        logger.info(f"  Rosneft page {page}: {len(tenders)} tenders")
        return tenders


class GazpromParser(BaseCorporateParser):
    """Parser for zakupki.gazprom.ru"""

    source_id = "gazprom"
    base_url = "https://zakupki.gazprom.ru"
    search_path = "/tenderList"

    async def _parse_page(self, http: httpx.AsyncClient, page: int) -> list[dict]:
        resp = await http.get(f"{self.base_url}{self.search_path}", params={
            "page": page, "state": "PUBLISHED",
        })
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        tenders = []

        for item in soup.select(".tender-list-item, .purchase-row, tr.item"):
            try:
                title_el = item.select_one("a.tender-name, .purchase-title a, td:nth-child(2) a, a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                number_match = re.search(r"(\d{6,})", href + title)
                number = number_match.group(1) if number_match else str(hash(title) % 10**8)

                price_el = item.select_one(".tender-price, .purchase-sum, .price, td:nth-child(3)")
                region_el = item.select_one(".tender-region, .region, .location")
                date_el = item.select_one(".tender-date, .publish-date, td:nth-child(4)")

                tenders.append({
                    "source_id": self.source_id,
                    "source_number": f"GP-{number}",
                    "source_url": f"{self.base_url}{href}" if not href.startswith("http") else href,
                    "title": title[:5000],
                    "law_type": "corporate",
                    "purchase_type": "other",
                    "okved_codes": [],
                    "okpd_codes": [],
                    "nmck": self._parse_price(price_el.get_text() if price_el else ""),
                    "currency": "RUB",
                    "customer_name": "ПАО «Газпром»",
                    "region": region_el.get_text(strip=True) if region_el else None,
                    "publish_date": self._parse_date(date_el.get_text() if date_el else ""),
                    "status": "active",
                })
                self.stats["found"] += 1

            except Exception as e:
                logger.debug(f"  Item parse error: {e}")
                self.stats["errors"] += 1

        logger.info(f"  Gazprom page {page}: {len(tenders)} tenders")
        return tenders
