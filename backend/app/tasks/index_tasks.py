"""
Celery Tasks — Meilisearch Indexing
Syncs PostgreSQL data to Meilisearch for instant search
"""

import logging
from datetime import datetime

import meilisearch
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.database import Tender, Company, SubcontractRequest, Source

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _get_meili() -> meilisearch.Client:
    return meilisearch.Client(settings.MEILI_URL, settings.MEILI_KEY)


def _get_session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
    return async_sessionmaker(engine, expire_on_commit=False)


def _ensure_indexes(client: meilisearch.Client):
    """Create Meilisearch indexes with proper settings if they don't exist."""

    # Tenders index
    try:
        client.get_index("tenders")
    except Exception:
        client.create_index("tenders", {"primaryKey": "id"})

    client.index("tenders").update_settings({
        "searchableAttributes": [
            "title",
            "description",
            "customer_name",
            "region",
            "source_name",
        ],
        "filterableAttributes": [
            "source_id",
            "law_type",
            "purchase_type",
            "status",
            "region",
            "region_code",
            "okved_codes",
            "nmck",
            "publish_date_ts",
            "deadline_ts",
        ],
        "sortableAttributes": [
            "publish_date_ts",
            "nmck",
            "deadline_ts",
            "created_at_ts",
        ],
        "faceting": {
            "maxValuesPerFacet": 50,
        },
        "pagination": {
            "maxTotalHits": 10000,
        },
    })

    # Companies index
    try:
        client.get_index("companies")
    except Exception:
        client.create_index("companies", {"primaryKey": "id"})

    client.index("companies").update_settings({
        "searchableAttributes": [
            "full_name",
            "short_name",
            "inn",
            "primary_okved",
            "region",
            "director_name",
        ],
        "filterableAttributes": [
            "primary_okved",
            "region",
            "region_code",
            "company_type",
            "status",
            "has_sro",
            "tender_wins_count",
        ],
        "sortableAttributes": [
            "tender_wins_count",
            "created_at_ts",
        ],
    })

    # Requests index
    try:
        client.get_index("requests")
    except Exception:
        client.create_index("requests", {"primaryKey": "id"})

    client.index("requests").update_settings({
        "searchableAttributes": ["title", "description", "region", "category", "company_name"],
        "filterableAttributes": ["status", "region", "category"],
        "sortableAttributes": ["created_at_ts"],
    })

    logger.info("Meilisearch indexes configured")


def _dt_to_ts(dt) -> int:
    """Convert datetime to Unix timestamp for Meilisearch sorting."""
    if dt is None:
        return 0
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    return 0


# ============================================================
# SYNC TENDERS
# ============================================================

@celery_app.task(name="app.tasks.index_tasks.sync_meilisearch")
def sync_meilisearch():
    """Sync all data from PostgreSQL to Meilisearch."""
    import asyncio

    async def _run():
        client = _get_meili()
        _ensure_indexes(client)
        factory = _get_session_factory()

        # --- Tenders ---
        async with factory() as session:
            # Get source names map
            src_rows = (await session.execute(select(Source))).scalars().all()
            src_map = {s.id: s.short_name for s in src_rows}

            # Batch sync tenders
            total = (await session.execute(select(func.count()).select_from(Tender))).scalar() or 0
            logger.info(f"Syncing {total} tenders to Meilisearch...")

            offset = 0
            while offset < total:
                rows = (await session.execute(
                    select(Tender).order_by(Tender.created_at).offset(offset).limit(BATCH_SIZE)
                )).scalars().all()

                if not rows:
                    break

                docs = []
                for t in rows:
                    docs.append({
                        "id": str(t.id),
                        "source_id": t.source_id,
                        "source_name": src_map.get(t.source_id, ""),
                        "source_number": t.source_number,
                        "source_url": t.source_url,
                        "title": t.title or "",
                        "description": (t.description or "")[:1000],
                        "law_type": t.law_type.value if t.law_type else "",
                        "purchase_type": t.purchase_type.value if t.purchase_type else "",
                        "okved_codes": t.okved_codes or [],
                        "nmck": float(t.nmck) if t.nmck else 0,
                        "customer_name": t.customer_name or "",
                        "customer_inn": t.customer_inn or "",
                        "region": t.region or "",
                        "region_code": t.region_code or 0,
                        "status": t.status.value if t.status else "active",
                        "publish_date_ts": _dt_to_ts(t.publish_date),
                        "deadline_ts": _dt_to_ts(t.deadline),
                        "created_at_ts": _dt_to_ts(t.created_at),
                    })

                client.index("tenders").add_documents(docs)
                offset += BATCH_SIZE

            logger.info(f"Tenders synced: {total}")

        # --- Companies ---
        async with factory() as session:
            total = (await session.execute(select(func.count()).select_from(Company))).scalar() or 0
            logger.info(f"Syncing {total} companies to Meilisearch...")

            offset = 0
            while offset < total:
                rows = (await session.execute(
                    select(Company).order_by(Company.created_at).offset(offset).limit(BATCH_SIZE)
                )).scalars().all()

                if not rows:
                    break

                docs = []
                for c in rows:
                    docs.append({
                        "id": str(c.id),
                        "inn": c.inn,
                        "ogrn": c.ogrn or "",
                        "full_name": c.full_name or "",
                        "short_name": c.short_name or "",
                        "region": c.region or "",
                        "region_code": c.region_code or 0,
                        "director_name": c.director_name or "",
                        "primary_okved": c.primary_okved or "",
                        "company_type": c.company_type.value if c.company_type else "",
                        "status": c.status.value if c.status else "active",
                        "has_sro": c.has_sro,
                        "tender_wins_count": c.tender_wins_count or 0,
                        "created_at_ts": _dt_to_ts(c.created_at),
                    })

                client.index("companies").add_documents(docs)
                offset += BATCH_SIZE

            logger.info(f"Companies synced: {total}")

        # --- Requests ---
        async with factory() as session:
            total = (await session.execute(select(func.count()).select_from(SubcontractRequest))).scalar() or 0

            offset = 0
            while offset < total:
                rows = (await session.execute(
                    select(SubcontractRequest).order_by(SubcontractRequest.created_at).offset(offset).limit(BATCH_SIZE)
                )).scalars().all()

                if not rows:
                    break

                docs = []
                for r in rows:
                    docs.append({
                        "id": str(r.id),
                        "title": r.title or "",
                        "description": (r.description or "")[:1000],
                        "category": r.category or "",
                        "region": r.region or "",
                        "company_name": r.company_name or "",
                        "status": r.status.value if r.status else "active",
                        "budget_text": r.budget_text or "",
                        "created_at_ts": _dt_to_ts(r.created_at),
                    })

                client.index("requests").add_documents(docs)
                offset += BATCH_SIZE

            logger.info(f"Requests synced: {total}")

    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run())
    return {"status": "ok"}


# ============================================================
# UPDATE SOURCE STATS
# ============================================================

@celery_app.task(name="app.tasks.index_tasks.update_source_stats")
def update_source_stats():
    """Update tender_count on sources table."""
    import asyncio

    async def _run():
        factory = _get_session_factory()
        async with factory() as session:
            # Count tenders per source
            q = select(Tender.source_id, func.count().label("cnt")).group_by(Tender.source_id)
            rows = (await session.execute(q)).all()

            for row in rows:
                await session.execute(
                    update(Source)
                    .where(Source.id == row.source_id)
                    .values(tender_count=row.cnt)
                )

            await session.commit()
            logger.info(f"Source stats updated for {len(rows)} sources")

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run())
