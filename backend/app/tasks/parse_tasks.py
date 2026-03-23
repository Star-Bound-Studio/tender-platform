"""
Celery Tasks — Parsing
Triggers parsers for each source and logs results
"""

import logging
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.database import Source, ParseLog

logger = logging.getLogger(__name__)


def _get_session_factory():
    """Create async session factory for use in Celery tasks."""
    engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _log_parse(session_factory, source_id: str, stats: dict):
    """Write parse result to parse_logs and update source."""
    async with session_factory() as session:
        log = ParseLog(
            source_id=source_id,
            finished_at=datetime.utcnow(),
            status="success" if stats.get("errors", 0) == 0 else "partial",
            records_found=stats.get("found", 0),
            records_new=stats.get("new", 0),
            records_updated=stats.get("updated", 0),
            error_message=None if stats.get("errors", 0) == 0 else f"{stats['errors']} errors",
        )
        session.add(log)

        await session.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(last_parsed_at=datetime.utcnow())
        )
        await session.commit()


# ============================================================
# EIS (zakupki.gov.ru) — 44-ФЗ, 223-ФЗ
# ============================================================

@celery_app.task(name="app.tasks.parse_tasks.parse_eis", bind=True, max_retries=3)
def parse_eis(self):
    """Parse zakupki.gov.ru FTP XML."""
    import asyncio

    async def _run():
        factory = _get_session_factory()
        from app.parsers.eis_parser import EISParser
        parser = EISParser(factory)
        stats = await parser.run()
        await _log_parse(factory, "eis", stats)
        return stats

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        logger.info(f"EIS parse complete: {result}")
        return result
    except Exception as exc:
        logger.error(f"EIS parse failed: {exc}")
        self.retry(exc=exc, countdown=300)  # Retry in 5 min


# ============================================================
# РТС-тендер
# ============================================================

@celery_app.task(name="app.tasks.parse_tasks.parse_rts", bind=True, max_retries=3)
def parse_rts(self):
    """Parse rts-tender.ru."""
    import asyncio

    async def _run():
        factory = _get_session_factory()
        from app.parsers.rts_parser import RTSParser
        parser = RTSParser(factory)
        stats = await parser.run()
        await _log_parse(factory, "rts", stats)
        return stats

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        logger.info(f"RTS parse complete: {result}")
        return result
    except Exception as exc:
        logger.error(f"RTS parse failed: {exc}")
        self.retry(exc=exc, countdown=300)


# ============================================================
# Corporate (Роснефть, Газпром, ЛУКОЙЛ)
# ============================================================

@celery_app.task(name="app.tasks.parse_tasks.parse_corporate", bind=True, max_retries=2)
def parse_corporate(self):
    """Parse corporate procurement sites."""
    import asyncio

    async def _run():
        factory = _get_session_factory()
        results = {}

        for source_id, parser_class_name in [
            ("rosneft", "RosneftParser"),
            ("gazprom", "GazpromParser"),
        ]:
            try:
                module = __import__(f"app.parsers.corporate_parser", fromlist=[parser_class_name])
                parser_cls = getattr(module, parser_class_name)
                parser = parser_cls(factory)
                stats = await parser.run()
                await _log_parse(factory, source_id, stats)
                results[source_id] = stats
            except Exception as e:
                logger.error(f"Corporate parser {source_id} failed: {e}")
                results[source_id] = {"error": str(e)}

        return results

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_run())
    except Exception as exc:
        logger.error(f"Corporate parse failed: {exc}")
        self.retry(exc=exc, countdown=600)


# ============================================================
# Всем Подряд (субподряды)
# ============================================================

@celery_app.task(name="app.tasks.parse_tasks.parse_subcontracts", bind=True, max_retries=3)
def parse_subcontracts(self):
    """Parse vsem-podryad.ru."""
    import asyncio

    async def _run():
        factory = _get_session_factory()
        from app.parsers.subcontract_parser import VsemPodryadParser
        parser = VsemPodryadParser(factory)
        stats = await parser.run()
        await _log_parse(factory, "vsem_podryad", stats)
        return stats

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        logger.info(f"Subcontract parse complete: {result}")
        return result
    except Exception as exc:
        logger.error(f"Subcontract parse failed: {exc}")
        self.retry(exc=exc, countdown=300)
