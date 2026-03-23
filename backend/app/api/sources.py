"""Sources API — list connected platforms with stats."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import get_db
from app.models.database import Source, Tender, ParseLog
from app.schemas.models import SourceOut

router = APIRouter()


@router.get("", response_model=list[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db)):
    # Update tender counts
    count_q = select(Tender.source_id, func.count().label("cnt")).group_by(Tender.source_id)
    counts = {r.source_id: r.cnt for r in (await db.execute(count_q)).all()}

    rows = (await db.execute(select(Source).order_by(Source.id))).scalars().all()
    result = []
    for s in rows:
        data = SourceOut.model_validate(s)
        data.tender_count = counts.get(s.id, 0)
        result.append(data)
    return result


@router.get("/{source_id}/logs")
async def source_logs(source_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(ParseLog).where(ParseLog.source_id == source_id).order_by(ParseLog.started_at.desc()).limit(20)
    )).scalars().all()
    return [{"started_at": r.started_at, "status": r.status, "records_new": r.records_new, "records_found": r.records_found} for r in rows]
