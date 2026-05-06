"""
GosplanService — REST API client for ГосПлан API v2.
Fetches real EIS tenders (44-ФЗ) via https://v2.gosplan.info

No auth needed until 01.07.2026.
Test server: https://v2test.gosplan.info (10 req/min, no key)
Prod server: https://v2.gosplan.info (600 req/min, free until Jul 2026)

API docs: https://swagger.gosplan.info
Wiki: https://wiki.gosplan.info

Flow:
  1. GET /fz44/purchases?limit=N&skip=M → list of purchases
  2. Map fields to our Tender model
  3. Upsert into database (insert or skip on conflict)
  4. Log results to parse_logs

Limited Flow (13 ОКВЭД, 3 groups):
  Group 1 — Строительство: 41.20, 42.11, 42.21, 43.21, 43.99
  Group 2 — IT и услуги: 62.01, 62.02, 63.11
  Group 3 — Промышленность и сервис: 09.10, 49.41, 71.12, 33.12, 46.90
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.database import Tender, Source, ParseLog

logger = logging.getLogger("gosplan")


# ============================================================
# OKVED groups for Limited Flow
# ============================================================

LIMITED_OKPD2_GROUPS = {
    "construction": {
        "name": "Строительство",
        "okpd2_prefixes": ["41", "42", "43"],
        "okved_codes": ["41.20", "42.11", "42.21", "43.21", "43.99"],
    },
    "it": {
        "name": "IT и услуги",
        "okpd2_prefixes": ["62", "63"],
        "okved_codes": ["62.01", "62.02", "63.11"],
    },
    "industry": {
        "name": "Промышленность и сервис",
        "okpd2_prefixes": ["09", "49", "71", "33", "46"],
        "okved_codes": ["09.10", "49.41", "71.12", "33.12", "46.90"],
    },
}


# ============================================================
# PURCHASE TYPE MAPPING
# ============================================================

PURCHASE_TYPE_MAP = {
    "epNotificationEF2020": "auction",
    "epNotificationEZK2020": "quotation",
    "epNotificationEZP2020": "contest",
    "epNotificationEOK2020": "contest",
    "epNotificationEOKOU2020": "contest",
    "fcsNotificationEF": "auction",
    "fcsNotificationEP": "single_source",
    "fcsNotificationOK": "contest",
    "fcsNotificationZakA": "auction",
    "fcsNotification111": "other",
}

STAGE_MAP = {
    "Подача заявок": "active",
    "Работа комиссии": "active",
    "Закупка завершена": "completed",
    "Закупка отменена": "cancelled",
}


class GosplanService:
    """
    Fetches real tender data from ГосПлан API v2 and saves to database.
    """

    PROD_URL = "https://v2.gosplan.info"
    TEST_URL = "https://v2test.gosplan.info"
    SOURCE_ID = "eis"

    def __init__(
        self,
        session_factory: async_sessionmaker,
        use_prod: bool = True,
        api_key: str = "",
    ):
        self.session_factory = session_factory
        self.base_url = self.PROD_URL if use_prod else self.TEST_URL
        self.api_key = api_key
        self._reset_stats()
        self._client: Optional[httpx.AsyncClient] = None

    def _reset_stats(self):
        self.stats = {
            "found": 0, "new": 0, "updated": 0,
            "errors": 0, "skipped": 0, "groups_scanned": 0,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                headers=headers,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ============================================================
    # FETCH PURCHASES FROM API
    # ============================================================

    async def _fetch_purchases(
        self,
        limit: int = 50,
        skip: int = 0,
        purchase_name: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> list[dict]:
        """
        GET /fz44/purchases — fetch list of purchases.

        Known valid params (from docs/swagger):
            limit: int (1-100)
            skip: int (offset)
            sort: "max_price_desc", "max_price_asc" (optional)
            purchase_name: str (search by name, keywords)

        Returns list of purchase dicts from API.
        """
        client = await self._get_client()

        # Build params carefully — only include what we're sure works
        params = {"limit": limit, "skip": skip}
        if purchase_name:
            params["purchase_name"] = purchase_name
        if sort:
            params["sort"] = sort

        url = f"{self.base_url}/fz44/purchases"

        print(f"[GOSPLAN] >>> GET {url} params={params}")
        logger.info(f">>> GET {url} params={params}")

        try:
            resp = await client.get(url, params=params)

            print(f"[GOSPLAN] <<< Status: {resp.status_code}")
            logger.info(f"<<< HTTP {resp.status_code}")

            # Handle errors with detailed logging
            if resp.status_code == 422:
                print(f"[GOSPLAN] ❌ 422 Unprocessable Entity. Response body:")
                print(f"[GOSPLAN] {resp.text[:1000]}")
                logger.error(f"422 response: {resp.text[:500]}")
                return []

            if resp.status_code == 429:
                print(f"[GOSPLAN] ⚠️ Rate limited (429). Waiting 60s...")
                logger.warning("Rate limited by API")
                await asyncio.sleep(60)
                return []

            resp.raise_for_status()

            data = resp.json()

            # Debug: print first record structure
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                print(f"[GOSPLAN] ✅ Got {len(data)} purchases")
                print(f"[GOSPLAN] Fields in first record: {list(first.keys())}")
                print(f"[GOSPLAN] First record sample:")
                # Print key fields for debugging (real v2 field names)
                for key in ["purchase_number", "object_info", "max_price",
                            "currency_code", "purchase_type", "stage",
                            "published_at", "customers", "okpd2",
                            "region", "collecting_finished_at",
                            "delivery_places", "docs"]:
                    val = first.get(key)
                    if isinstance(val, dict):
                        print(f"[GOSPLAN]   {key}: {json.dumps(val, ensure_ascii=False, default=str)[:200]}")
                    elif isinstance(val, list):
                        print(f"[GOSPLAN]   {key}: [{len(val)} items] {json.dumps(val[:2], ensure_ascii=False, default=str)[:200]}")
                    else:
                        print(f"[GOSPLAN]   {key}: {val}")
                logger.info(f"Got {len(data)} purchases. First keys: {list(first.keys())}")
                return data
            elif isinstance(data, dict):
                # Maybe wrapped in object
                print(f"[GOSPLAN] Response is dict with keys: {list(data.keys())}")
                logger.info(f"Response dict keys: {list(data.keys())}")
                if "items" in data:
                    return data["items"]
                if "data" in data:
                    return data["data"]
                # Maybe it's an error object
                print(f"[GOSPLAN] Full response: {json.dumps(data, ensure_ascii=False, default=str)[:1000]}")
                return []
            else:
                print(f"[GOSPLAN] ⚠️ Unexpected response type: {type(data)}")
                return []

        except httpx.HTTPStatusError as e:
            print(f"[GOSPLAN] ❌ HTTP error: {e}")
            print(f"[GOSPLAN] Response body: {e.response.text[:500]}")
            logger.error(f"HTTP error: {e}")
            return []
        except Exception as e:
            print(f"[GOSPLAN] ❌ Error: {e}")
            logger.error(f"Error fetching purchases: {e}")
            return []

    # ============================================================
    # MAP API RESPONSE → TENDER MODEL
    # ============================================================

    def _map_purchase_to_tender(self, purchase: dict, okved_codes: list[str]) -> Optional[dict]:
        """
        Map a ГосПлан API v2 purchase object to our Tender model fields.
        All enum fields are stored as plain strings (String(50) in DB).

        Real API v2 fields (from logs):
            purchase_number: str — "0335300021526000006"
            object_info: str — наименование закупки (NOT purchase_name!)
            max_price: float — НМЦК
            currency_code: str — "RUB"
            purchase_type: str — "epNotificationEF2020"
            stage: int — 1 (число, НЕ строка!)
            published_at: str — ISO datetime
            collecting_finished_at: str — дедлайн подачи
            customers: list[dict] — [{name, inn, ...}] (NOT customer!)
            okpd2: list[str] — ["20.59.52.120"] (строки, не объекты!)
            region: str — код региона по КЛАДР
            delivery_places: list — места доставки
            docs: list[dict] — [{doc_type, published_at}]
            owners: list — организации
        """
        try:
            purchase_number = purchase.get("purchase_number", "")
            if not purchase_number:
                return None

            # === TITLE (наименование) ===
            # API v2 uses "object_info" for purchase name
            title = purchase.get("object_info") or ""
            if not title or not title.strip():
                title = "Без наименования"

            # === НМЦК ===
            max_price = None
            raw_price = purchase.get("max_price")
            if raw_price is not None:
                try:
                    max_price = Decimal(str(raw_price))
                except (InvalidOperation, ValueError, TypeError):
                    pass

            # === ЗАКАЗЧИК ===
            # API v2: "customers" is a LIST of INN strings (e.g. ["2223023559"]),
            # NOT a list of dicts. Older API versions may return dicts — handle both.
            customer_name = None
            customer_inn = None
            customers = purchase.get("customers") or []
            if isinstance(customers, list) and len(customers) > 0:
                first_customer = customers[0]
                if isinstance(first_customer, str) and first_customer:
                    customer_inn = first_customer
                elif isinstance(first_customer, dict):
                    customer_name = first_customer.get("name") or ""
                    customer_inn = first_customer.get("inn") or ""

            # === РЕГИОН ===
            # API v2: "region" is at root level (КЛАДР code as string)
            region_name = None
            region_code = None
            raw_region = purchase.get("region")
            if raw_region:
                try:
                    region_code = int(raw_region)
                except (ValueError, TypeError):
                    pass
                # Also try delivery_places for region name
                delivery = purchase.get("delivery_places") or []
                if isinstance(delivery, list) and len(delivery) > 0:
                    place = delivery[0]
                    if isinstance(place, dict):
                        region_name = place.get("region_name") or place.get("address") or str(raw_region)
                    elif isinstance(place, str):
                        region_name = place
                if not region_name:
                    region_name = str(raw_region)

            # === ТИП ЗАКУПКИ → plain string ===
            raw_type = purchase.get("purchase_type", "")
            purchase_type = PURCHASE_TYPE_MAP.get(raw_type, "other")

            # === ЭТАП → STATUS ===
            # API v2: stage is an INTEGER, not a string
            #   1 = Подача заявок (active)
            #   2 = Работа комиссии (active)
            #   3 = Закупка завершена (completed)
            #   4 = Закупка отменена (cancelled)
            STAGE_INT_MAP = {
                1: "active",
                2: "active",
                3: "completed",
                4: "cancelled",
            }
            raw_stage = purchase.get("stage")
            if isinstance(raw_stage, int):
                status = STAGE_INT_MAP.get(raw_stage, "active")
            elif isinstance(raw_stage, str):
                status = STAGE_MAP.get(raw_stage, "active")
            else:
                status = "active"

            # === ДАТЫ ===
            # published_at — дата публикации (NOT publish_date)
            # Also check docs[0].published_at as fallback
            publish_date = self._parse_date(purchase.get("published_at"))
            if not publish_date:
                docs = purchase.get("docs") or []
                if isinstance(docs, list) and len(docs) > 0:
                    first_doc = docs[0]
                    if isinstance(first_doc, dict):
                        publish_date = self._parse_date(first_doc.get("published_at"))

            # collecting_finished_at — дедлайн подачи заявок
            deadline = self._parse_date(purchase.get("collecting_finished_at"))

            # === ОКПД2 ===
            # API v2: okpd2 is a list of STRINGS, not objects
            okpd_codes_from_api = []
            raw_okpd = purchase.get("okpd2") or []
            if isinstance(raw_okpd, list):
                for item in raw_okpd:
                    if isinstance(item, str) and item:
                        okpd_codes_from_api.append(item)
                    elif isinstance(item, dict):
                        code = item.get("code", "")
                        if code:
                            okpd_codes_from_api.append(code)

            # === URL на zakupki.gov.ru ===
            source_url = f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={purchase_number}"

            # === CURRENCY ===
            currency = purchase.get("currency_code") or "RUB"

            return {
                "id": uuid.uuid4(),
                "source_id": self.SOURCE_ID,
                "source_number": str(purchase_number),
                "source_url": source_url,
                "title": str(title)[:2000],
                "description": None,
                "law_type": "44-fz",           # plain string, NOT enum
                "purchase_type": purchase_type,  # plain string
                "okved_codes": okved_codes if okved_codes else [],
                "okpd_codes": okpd_codes_from_api if okpd_codes_from_api else [],
                "tags": [],
                "nmck": max_price,
                "currency": str(currency)[:3] if currency else "RUB",
                "contract_price": None,
                "customer_name": str(customer_name)[:500] if customer_name else None,
                "customer_inn": str(customer_inn)[:12] if customer_inn else None,
                "winner_name": None,
                "winner_inn": None,
                "region": str(region_name)[:200] if region_name else None,
                "region_code": region_code,
                "publish_date": publish_date,
                "deadline": deadline,
                "status": status,               # plain string
                "raw_data": purchase,            # full API response as JSONB
            }
        except Exception as e:
            print(f"[GOSPLAN] ❌ Error mapping purchase {purchase.get('purchase_number', '?')}: {e}")
            logger.error(f"Error mapping purchase: {e}")
            self.stats["errors"] += 1
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            # Try dateutil as fallback
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(date_str)
        except Exception:
            pass
        return None

    # ============================================================
    # SAVE TO DATABASE
    # ============================================================

    async def _upsert_tenders(self, tenders_data: list[dict]) -> int:
        """
        Upsert tenders into database.
        INSERT ... ON CONFLICT (source_id, source_number) DO NOTHING.
        """
        if not tenders_data:
            return 0

        new_count = 0
        async with self.session_factory() as session:
            for tender_dict in tenders_data:
                try:
                    stmt = pg_insert(Tender).values(**tender_dict)
                    stmt = stmt.on_conflict_do_nothing(
                        constraint="uq_tender_source"
                    )
                    result = await session.execute(stmt)
                    if result.rowcount > 0:
                        new_count += 1
                except Exception as e:
                    print(f"[GOSPLAN] ❌ DB error for {tender_dict.get('source_number')}: {e}")
                    logger.error(f"DB error: {e}")
                    self.stats["errors"] += 1
                    await session.rollback()
                    continue

            await session.commit()

        print(f"[GOSPLAN] 💾 Saved {new_count} new tenders to DB")
        return new_count

    async def _update_source_stats(self):
        """Update tender_count and last_parsed_at for EIS source."""
        try:
            async with self.session_factory() as session:
                source = await session.get(Source, self.SOURCE_ID)
                if source:
                    count = (await session.execute(
                        select(func.count()).select_from(Tender)
                        .where(Tender.source_id == self.SOURCE_ID)
                    )).scalar()
                    source.tender_count = count or 0
                    source.last_parsed_at = datetime.utcnow()
                    await session.commit()
                    print(f"[GOSPLAN] 📊 Source stats: {count} total EIS tenders")
        except Exception as e:
            logger.error(f"Error updating source stats: {e}")

    async def _create_parse_log(
        self, status: str = "running", error: Optional[str] = None,
    ) -> Optional[int]:
        """Create a parse_log entry."""
        try:
            async with self.session_factory() as session:
                log = ParseLog(
                    source_id=self.SOURCE_ID,
                    status=status,
                    records_found=self.stats["found"],
                    records_new=self.stats["new"],
                    records_updated=self.stats["updated"],
                    error_message=error,
                )
                if status in ("completed", "error"):
                    log.finished_at = datetime.utcnow()
                session.add(log)
                await session.commit()
                await session.refresh(log)
                return log.id
        except Exception as e:
            logger.error(f"Error creating parse log: {e}")
            return None

    # ============================================================
    # MAIN SCAN METHODS
    # ============================================================

    async def scan(
        self,
        groups: Optional[list[str]] = None,
        max_pages_per_group: int = 3,
        per_page: int = 50,
    ) -> dict:
        """
        Main scan method. Fetches tenders from ГосПлан API v2.

        Args:
            groups: list of group keys ["construction", "it", "industry"]
            max_pages_per_group: pages to fetch per group
            per_page: results per page (max 100)
        """
        self._reset_stats()
        target_groups = groups or list(LIMITED_OKPD2_GROUPS.keys())

        print(f"[GOSPLAN] 🔍 Scan starting: {len(target_groups)} groups, server={self.base_url}")
        logger.info(f"Scan starting: {len(target_groups)} groups")

        await self._create_parse_log(status="running")

        for group_key in target_groups:
            group = LIMITED_OKPD2_GROUPS.get(group_key)
            if not group:
                print(f"[GOSPLAN] ⚠️ Unknown group: {group_key}")
                continue

            print(f"[GOSPLAN] 📂 Group: {group['name']} ({group_key})")
            self.stats["groups_scanned"] += 1

            # Fetch pages of purchases
            for page in range(max_pages_per_group):
                skip = page * per_page

                purchases = await self._fetch_purchases(
                    limit=per_page,
                    skip=skip,
                )

                if not purchases:
                    print(f"[GOSPLAN]    Page {page + 1}: no data, stopping")
                    break

                self.stats["found"] += len(purchases)
                print(f"[GOSPLAN]    Page {page + 1}: got {len(purchases)} purchases")

                # Map to tender objects
                tenders_data = []
                for p in purchases:
                    tender_dict = self._map_purchase_to_tender(
                        p, okved_codes=group["okved_codes"]
                    )
                    if tender_dict:
                        tenders_data.append(tender_dict)
                    else:
                        self.stats["skipped"] += 1

                # Save to DB
                new_count = await self._upsert_tenders(tenders_data)
                self.stats["new"] += new_count

                if len(purchases) < per_page:
                    break  # Last page

                # Be polite to the API
                await asyncio.sleep(2)

        # Update stats
        await self._update_source_stats()

        error_msg = None
        if self.stats["errors"] > 0:
            error_msg = f"{self.stats['errors']} errors during scan"

        await self._create_parse_log(
            status="completed" if not error_msg else "error",
            error=error_msg,
        )

        print(f"[GOSPLAN] ✅ Scan complete: {self.stats}")
        logger.info(f"Scan complete: {self.stats}")
        return self.stats

    async def scan_single_page(self, limit: int = 10) -> dict:
        """
        Quick test — fetch one page of latest purchases.
        Good for testing API connectivity and seeing field structure.
        """
        self._reset_stats()

        print(f"[GOSPLAN] 🔍 Quick test: {limit} purchases from {self.base_url}")

        purchases = await self._fetch_purchases(limit=limit, skip=0)
        if not purchases:
            print("[GOSPLAN] ⚠️ No purchases returned!")
            return self.stats

        self.stats["found"] = len(purchases)

        tenders_data = []
        for p in purchases:
            tender_dict = self._map_purchase_to_tender(p, okved_codes=[])
            if tender_dict:
                tenders_data.append(tender_dict)

        new_count = await self._upsert_tenders(tenders_data)
        self.stats["new"] = new_count

        await self._update_source_stats()

        print(f"[GOSPLAN] ✅ Quick test done: {self.stats}")
        return self.stats

    # ============================================================
    # CONTRACTS — /fz44/contracts
    # Fetches concluded contracts and updates matching tenders with
    # winner_inn, contract_price, and status="completed".
    #
    # Contract record fields (API v2):
    #   purchase_number: str — links to Tender.source_number
    #   customer: str        — customer INN (plain string)
    #   suppliers: list[str] — winner INN(s) (plain strings)
    #   price: float         — contract price
    #   subject: str         — contract subject
    #   reg_num: str         — contract registration number
    #   stage: str           — contract stage ("E" = execution, etc.)
    # ============================================================

    async def _fetch_contracts(
        self,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict]:
        """GET /fz44/contracts — fetch list of concluded contracts."""
        client = await self._get_client()
        url = f"{self.base_url}/fz44/contracts"
        params = {"limit": limit, "skip": skip}

        print(f"[GOSPLAN] >>> GET {url} params={params}")
        logger.info(f">>> GET {url} params={params}")

        try:
            resp = await client.get(url, params=params)
            print(f"[GOSPLAN] <<< Status: {resp.status_code}")

            if resp.status_code == 422:
                print(f"[GOSPLAN] ❌ 422: {resp.text[:500]}")
                return []
            if resp.status_code == 429:
                print("[GOSPLAN] ⚠️ Rate limited (429). Waiting 60s...")
                await asyncio.sleep(60)
                return []

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                print(f"[GOSPLAN] ✅ Got {len(data)} contracts")
                if data:
                    print(f"[GOSPLAN] Contract fields: {list(data[0].keys())}")
                return data
            elif isinstance(data, dict):
                if "items" in data:
                    return data["items"]
                if "data" in data:
                    return data["data"]
                return []
            return []

        except httpx.HTTPStatusError as e:
            print(f"[GOSPLAN] ❌ HTTP error: {e} — {e.response.text[:300]}")
            logger.error(f"HTTP error fetching contracts: {e}")
            return []
        except Exception as e:
            print(f"[GOSPLAN] ❌ Error fetching contracts: {e}")
            logger.error(f"Error fetching contracts: {e}")
            return []

    async def _update_tenders_from_contracts(self, contracts: list[dict]) -> int:
        """
        Match contracts to existing tenders by purchase_number and update:
          winner_inn, contract_price, status → "completed".
        Returns count of updated tenders.
        """
        if not contracts:
            return 0

        updated = 0
        async with self.session_factory() as session:
            for contract in contracts:
                purchase_number = contract.get("purchase_number")
                if not purchase_number:
                    continue

                suppliers = contract.get("suppliers") or []
                winner_inn = None
                if suppliers:
                    first = suppliers[0]
                    if isinstance(first, str) and first:
                        winner_inn = first[:12]
                    elif isinstance(first, dict):
                        winner_inn = (first.get("inn") or "")[:12] or None

                raw_price = contract.get("price")
                contract_price = None
                if raw_price is not None:
                    try:
                        contract_price = Decimal(str(raw_price))
                    except (InvalidOperation, ValueError, TypeError):
                        pass

                values: dict = {"status": "completed"}
                if winner_inn:
                    values["winner_inn"] = winner_inn
                if contract_price is not None:
                    values["contract_price"] = contract_price

                try:
                    result = await session.execute(
                        sa_update(Tender)
                        .where(Tender.source_id == self.SOURCE_ID)
                        .where(Tender.source_number == str(purchase_number))
                        .values(**values)
                    )
                    if result.rowcount > 0:
                        updated += result.rowcount
                        print(
                            f"[GOSPLAN] 🔗 Contract matched: {purchase_number}"
                            f" → winner={winner_inn}, price={contract_price}"
                        )
                except Exception as e:
                    print(f"[GOSPLAN] ❌ DB error updating tender {purchase_number}: {e}")
                    logger.error(f"DB error updating tender from contract: {e}")
                    await session.rollback()
                    continue

            await session.commit()

        print(f"[GOSPLAN] 💾 Updated {updated} tenders from contracts")
        return updated

    async def scan_contracts(
        self,
        max_pages: int = 5,
        per_page: int = 50,
    ) -> dict:
        """
        Fetch recent contracts from /fz44/contracts and update matching
        tenders with winner_inn, contract_price, status="completed".
        """
        stats = {"found": 0, "updated": 0, "errors": 0}

        print(f"[GOSPLAN] 📋 Contract scan: up to {max_pages} pages")
        logger.info("Contract scan starting")

        for page in range(max_pages):
            skip = page * per_page
            contracts = await self._fetch_contracts(limit=per_page, skip=skip)

            if not contracts:
                print(f"[GOSPLAN]    Page {page + 1}: no data, stopping")
                break

            stats["found"] += len(contracts)
            print(f"[GOSPLAN]    Page {page + 1}: got {len(contracts)} contracts")

            updated = await self._update_tenders_from_contracts(contracts)
            stats["updated"] += updated

            if len(contracts) < per_page:
                break

            await asyncio.sleep(2)

        print(f"[GOSPLAN] ✅ Contract scan complete: {stats}")
        logger.info(f"Contract scan complete: {stats}")
        return stats