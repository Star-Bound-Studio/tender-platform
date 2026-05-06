"""
Background Scheduler — APScheduler integration for FastAPI.
Runs EIS scanner, Gosplan scanner and other jobs on schedule.

Usage:
  - Starts automatically with FastAPI via lifespan
  - Jobs run in background thread (AsyncIOScheduler)
  - Manual trigger available via API endpoint
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger("scheduler")

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def job_eis_scan():
    """Scheduled job: scan EIS for new tenders (SOAP)."""
    from app.models.session import AsyncSessionLocal
    from app.services.eis_scanner import EisScannerService, LIMITED_REGIONS

    logger.info("⏰ Scheduled EIS scan starting...")

    regions = LIMITED_REGIONS if settings.EIS_LIMITED_MODE else None

    scanner = EisScannerService(
        session_factory=AsyncSessionLocal,
        token=settings.EIS_TOKEN,
    )

    try:
        stats = await scanner.scan(regions=regions, subsystem="PRIZ")
        logger.info(f"⏰ Scheduled EIS scan done: {stats}")
    except Exception as e:
        logger.error(f"⏰ Scheduled EIS scan failed: {e}")
    finally:
        await scanner.close()


async def job_gosplan_scan():
    """Scheduled job: scan tenders via Gosplan REST API v2."""
    from app.models.session import AsyncSessionLocal
    from app.services.gosplan import GosplanService

    logger.info("⏰ Scheduled Gosplan scan starting...")

    service = GosplanService(
        session_factory=AsyncSessionLocal,
        use_prod=settings.GOSPLAN_USE_PROD,
        api_key=settings.GOSPLAN_API_KEY,
    )

    try:
        stats = await service.scan(
            max_pages_per_group=settings.GOSPLAN_MAX_PAGES,
            per_page=settings.GOSPLAN_PER_PAGE,
        )
        logger.info(f"⏰ Scheduled Gosplan scan done: {stats}")
    except Exception as e:
        logger.error(f"⏰ Scheduled Gosplan scan failed: {e}")
    finally:
        await service.close()


async def job_gosplan_contracts():
    """Scheduled job: fetch concluded contracts and update matching tenders."""
    from app.models.session import AsyncSessionLocal
    from app.services.gosplan import GosplanService

    logger.info("⏰ Scheduled Gosplan contracts scan starting...")

    service = GosplanService(
        session_factory=AsyncSessionLocal,
        use_prod=settings.GOSPLAN_USE_PROD,
        api_key=settings.GOSPLAN_API_KEY,
    )
    try:
        stats = await service.scan_contracts(
            max_pages=settings.GOSPLAN_MAX_PAGES,
            per_page=settings.GOSPLAN_PER_PAGE,
        )
        logger.info(f"⏰ Scheduled contracts scan done: {stats}")
    except Exception as e:
        logger.error(f"⏰ Scheduled contracts scan failed: {e}")
    finally:
        await service.close()


async def job_update_source_stats():
    """Update tender counts for all sources."""
    from app.models.session import AsyncSessionLocal
    from app.models.database import Source, Tender
    from sqlalchemy import select, func

    try:
        async with AsyncSessionLocal() as session:
            sources = (await session.execute(select(Source))).scalars().all()
            for source in sources:
                count = (await session.execute(
                    select(func.count()).select_from(Tender).where(Tender.source_id == source.id)
                )).scalar()
                source.tender_count = count or 0
            await session.commit()
            logger.info(f"⏰ Source stats updated for {len(sources)} sources")
    except Exception as e:
        logger.error(f"⏰ Stats update failed: {e}")


async def job_dadata_enrich():
    """Scheduled job: enrich company records via DaData API.

    Loops `enrich_batch` until either everything is processed or the daily
    safety cap is hit. We don't want to ddos DaData (free tier ≈ 10k/day),
    so we cap the run at ~3000 lookups, which is well under the limit and
    enough to drain a typical pending backlog in one night.
    """
    from app.models.session import AsyncSessionLocal
    from app.services.dadata import DaDataService

    DAILY_CAP = 3000
    PASS_SIZE = max(settings.DADATA_BATCH_SIZE, 200)

    logger.info("⏰ Scheduled DaData enrichment starting...")

    service = DaDataService(
        session_factory=AsyncSessionLocal,
        api_key=settings.DADATA_API_KEY,
        secret=settings.DADATA_SECRET,
    )

    try:
        # Step 1: Create stubs from tender INNs that aren't in companies table yet
        new_stubs = await service.create_stubs_from_tenders()
        if new_stubs:
            logger.info(f"⏰ Created {new_stubs} new company stubs from tenders")

        # Step 2: Enrich in passes until drained or cap reached
        total_processed = 0
        while total_processed < DAILY_CAP:
            stats = await service.enrich_batch(limit=PASS_SIZE)
            processed = stats.get("processed", 0)
            if processed == 0:
                break
            total_processed += processed
            logger.info(
                f"⏰ DaData pass: +{processed} processed "
                f"(running total: {total_processed})"
            )
        logger.info(f"⏰ DaData enrichment done: total {total_processed} processed")
    except Exception as e:
        logger.error(f"⏰ DaData enrichment failed: {e}")
    finally:
        await service.close()


def setup_scheduler():
    """Configure and start the scheduler."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("📋 Scheduler disabled (SCHEDULER_ENABLED=false)")
        return

    # EIS SOAP scan — every 2 hours (needs token)
    if settings.EIS_TOKEN:
        scheduler.add_job(
            job_eis_scan,
            trigger=IntervalTrigger(hours=settings.EIS_SCAN_INTERVAL_HOURS),
            id="eis_scan",
            name="EIS SOAP Scanner",
            replace_existing=True,
            max_instances=1,
        )

    # Gosplan REST scan — every 1 hour (free, no token needed)
    if settings.GOSPLAN_ENABLED:
        scheduler.add_job(
            job_gosplan_scan,
            trigger=IntervalTrigger(hours=settings.GOSPLAN_SCAN_INTERVAL_HOURS),
            id="gosplan_scan",
            name="Gosplan REST Scanner",
            replace_existing=True,
            max_instances=1,
        )
        # Contracts scan — every 2 hours (after purchases, so tenders exist first)
        scheduler.add_job(
            job_gosplan_contracts,
            trigger=IntervalTrigger(hours=2),
            id="gosplan_contracts",
            name="Gosplan Contracts Scanner",
            replace_existing=True,
            max_instances=1,
        )

    # Update source stats — every 30 minutes
    scheduler.add_job(
        job_update_source_stats,
        trigger=IntervalTrigger(minutes=30),
        id="update_stats",
        name="Update source statistics",
        replace_existing=True,
    )

    # DaData company enrichment — once a day at 03:00 MSK (low-traffic window).
    # We use Cron rather than Interval so the schedule is stable across restarts
    # and predictable for monitoring.
    if settings.DADATA_ENABLED and settings.DADATA_API_KEY:
        scheduler.add_job(
            job_dadata_enrich,
            trigger=CronTrigger(hour=3, minute=0, timezone="Europe/Moscow"),
            id="dadata_enrich",
            name="DaData Company Enrichment (daily 03:00 MSK)",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
        )

    scheduler.start()
    logger.info(f"📋 Scheduler started with {len(scheduler.get_jobs())} jobs")
    for job in scheduler.get_jobs():
        logger.info(f"   → {job.name}: next run at {job.next_run_time}")


def shutdown_scheduler():
    """Gracefully stop scheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("📋 Scheduler stopped")