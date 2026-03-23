"""
Celery Tasks — Company Enrichment
Loads and updates company data from EGRUL (FNS) and other free sources
"""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.database import Company, Tender

logger = logging.getLogger(__name__)

TARGET_OKVEDS = [
    "41.20", "42.11", "42.21", "43.21", "43.99",  # Construction
    "62.01", "62.02", "63.11",                      # IT
    "09.10", "49.41", "71.12", "33.12", "46.90",   # Industry & Service
]


def _get_session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="app.tasks.enrich_tasks.enrich_companies_egrul")
def enrich_companies_egrul():
    """
    Discover new companies from tenders and enrich from EGRUL.
    
    Strategy:
    1. Find all unique INNs from tenders (customer + winner) that are NOT in companies table
    2. For each new INN, query EGRUL API (egrul.nalog.ru)
    3. Filter by our target OKVEDs
    4. Insert matching companies
    """
    import asyncio

    async def _run():
        factory = _get_session_factory()
        stats = {"discovered": 0, "added": 0, "skipped": 0, "errors": 0}

        async with factory() as session:
            # 1. Find INNs from tenders not yet in companies
            existing_inns = select(Company.inn)

            # Customer INNs
            customer_q = (
                select(Tender.customer_inn)
                .where(
                    Tender.customer_inn.isnot(None),
                    Tender.customer_inn.notin_(existing_inns),
                )
                .distinct()
                .limit(200)  # Process in batches
            )
            customer_inns = [r[0] for r in (await session.execute(customer_q)).all()]

            # Winner INNs
            winner_q = (
                select(Tender.winner_inn)
                .where(
                    Tender.winner_inn.isnot(None),
                    Tender.winner_inn.notin_(existing_inns),
                )
                .distinct()
                .limit(200)
            )
            winner_inns = [r[0] for r in (await session.execute(winner_q)).all()]

            all_inns = list(set(customer_inns + winner_inns))
            stats["discovered"] = len(all_inns)
            logger.info(f"Discovered {len(all_inns)} new INNs from tenders")

        # 2. Query EGRUL for each INN
        import httpx

        async with httpx.AsyncClient(timeout=30) as http:
            for inn in all_inns:
                try:
                    company_data = await _fetch_egrul(http, inn)
                    if company_data:
                        # 3. Check if OKVED matches our targets
                        primary_okved = company_data.get("primary_okved", "")
                        matches_target = any(
                            primary_okved.startswith(ok)
                            for ok in TARGET_OKVEDS
                        )

                        # Save all companies from tenders, but mark target ones
                        async with factory() as session:
                            company = Company(
                                inn=inn,
                                ogrn=company_data.get("ogrn"),
                                full_name=company_data.get("full_name", f"ИНН {inn}"),
                                short_name=company_data.get("short_name"),
                                legal_address=company_data.get("address"),
                                region=company_data.get("region"),
                                director_name=company_data.get("director"),
                                registration_date=company_data.get("reg_date"),
                                authorized_capital=company_data.get("capital"),
                                primary_okved=primary_okved,
                                company_type="customer" if inn in customer_inns else "contractor",
                                is_verified=True,
                                egrul_updated_at=datetime.utcnow(),
                            )
                            session.add(company)
                            await session.commit()
                            stats["added"] += 1

                    else:
                        stats["skipped"] += 1

                except Exception as e:
                    logger.error(f"EGRUL fetch error for INN {inn}: {e}")
                    stats["errors"] += 1

        # 4. Update tender win counts
        await _update_tender_stats(factory)

        logger.info(f"EGRUL enrichment complete: {stats}")
        return stats

    loop = asyncio.new_event_loop()
    return loop.run_until_complete(_run())


async def _fetch_egrul(http, inn: str) -> dict | None:
    """
    Fetch company data from EGRUL (nalog.ru).
    Uses the free public search endpoint.
    """
    try:
        # Step 1: Request search token
        resp = await http.post(
            "https://egrul.nalog.ru/",
            data={"query": inn, "region": "", "page": ""},
        )
        if resp.status_code != 200:
            return None

        token = resp.json().get("t")
        if not token:
            return None

        # Step 2: Get results
        import asyncio
        await asyncio.sleep(1)  # Rate limiting

        resp2 = await http.get(
            f"https://egrul.nalog.ru/search-result/{token}",
        )
        if resp2.status_code != 200:
            return None

        data = resp2.json()
        rows = data.get("rows", [])
        if not rows:
            return None

        row = rows[0]  # First match
        return {
            "inn": row.get("i"),  # INN
            "ogrn": row.get("o"),  # OGRN
            "full_name": row.get("c"),  # Company name
            "short_name": row.get("c", "")[:500],
            "address": row.get("a"),  # Address
            "region": _extract_region(row.get("a", "")),
            "director": row.get("g"),  # Director
            "reg_date": None,  # Not in search results, need full extract
            "capital": None,
            "primary_okved": "",  # Need additional request for OKVED
        }

    except Exception as e:
        logger.error(f"EGRUL API error: {e}")
        return None


def _extract_region(address: str) -> str:
    """Extract region name from full address string."""
    if not address:
        return ""

    # Common region patterns
    region_keywords = [
        "Москва", "Санкт-Петербург", "Московская обл",
        "ХМАО", "ЯНАО", "Тюменская обл", "Свердловская обл",
        "Краснодарский край", "Челябинская обл", "Пермский край",
        "Красноярский край", "Новосибирская обл", "Оренбургская обл",
    ]
    for kw in region_keywords:
        if kw.lower() in address.lower():
            return kw
    
    # Try to extract from comma-separated address
    parts = address.split(",")
    if len(parts) >= 2:
        return parts[1].strip()[:200]

    return ""


async def _update_tender_stats(factory):
    """Update tender_wins_count and tender_wins_sum for all companies."""
    from sqlalchemy import func as sqf
    from decimal import Decimal

    async with factory() as session:
        # Count wins per winner INN
        q = (
            select(
                Tender.winner_inn,
                sqf.count().label("cnt"),
                sqf.sum(Tender.contract_price).label("total"),
            )
            .where(Tender.winner_inn.isnot(None))
            .group_by(Tender.winner_inn)
        )
        rows = (await session.execute(q)).all()

        for row in rows:
            await session.execute(
                update(Company)
                .where(Company.inn == row.winner_inn)
                .values(
                    tender_wins_count=row.cnt,
                    tender_wins_sum=row.total or Decimal(0),
                )
            )

        await session.commit()
        logger.info(f"Updated tender stats for {len(rows)} companies")
