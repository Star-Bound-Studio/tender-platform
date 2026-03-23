"""
Tender Platform — Tenders API
Search, filter, paginate tenders from all sources
"""

from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import get_db
from app.models.database import Tender, Source, TenderStatus
from app.schemas.models import TenderOut, TenderListOut

router = APIRouter()


def _enrich(tender, src_map):
    data = {c.name: getattr(tender, c.name) for c in tender.__table__.columns}
    # Convert None arrays to empty lists for Pydantic
    for key in ("okved_codes", "okpd_codes", "tags"):
        if data.get(key) is None:
            data[key] = []
    s = src_map.get(tender.source_id, {})
    data["source_name"] = s.get("short_name", "")
    data["source_color"] = s.get("color", "#666")
    return data


@router.get("", response_model=TenderListOut)
async def list_tenders(
    q: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    law_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    region_code: Optional[int] = Query(None),
    okved: Optional[str] = Query(None),
    nmck_min: Optional[Decimal] = Query(None),
    nmck_max: Optional[Decimal] = Query(None),
    status: Optional[str] = Query("active"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    customer_inn: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("publish_date"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    conds = []
    if status:
        conds.append(Tender.status == status)
    if source_id:
        conds.append(Tender.source_id == source_id)
    if law_type:
        conds.append(Tender.law_type == law_type)
    if region:
        conds.append(Tender.region.ilike(f"%{region}%"))
    if region_code:
        conds.append(Tender.region_code == region_code)
    if okved:
        conds.append(Tender.okved_codes.any(okved))
    if nmck_min is not None:
        conds.append(Tender.nmck >= nmck_min)
    if nmck_max is not None:
        conds.append(Tender.nmck <= nmck_max)
    if date_from:
        conds.append(Tender.publish_date >= date_from)
    if date_to:
        conds.append(Tender.publish_date <= date_to)
    if customer_inn:
        conds.append(Tender.customer_inn == customer_inn)
    if q:
        conds.append(Tender.search_vector.match(q, postgresql_regconfig="russian"))

    where = and_(*conds) if conds else True

    total = (await db.execute(select(func.count()).select_from(Tender).where(where))).scalar() or 0

    sc_q = select(Tender.source_id, func.count().label("cnt")).where(where).group_by(Tender.source_id)
    source_counts = {r.source_id: r.cnt for r in (await db.execute(sc_q)).all()}

    col_map = {"publish_date": Tender.publish_date, "nmck": Tender.nmck, "deadline": Tender.deadline, "created_at": Tender.created_at}
    col = col_map.get(sort_by, Tender.publish_date)
    order = desc(col) if sort_order == "desc" else asc(col)

    rows = (await db.execute(
        select(Tender).where(where).order_by(order.nulls_last()).offset((page-1)*per_page).limit(per_page)
    )).scalars().all()

    src_map = {s.id: {"short_name": s.short_name, "color": s.color} for s in (await db.execute(select(Source))).scalars().all()}

    return TenderListOut(
        total=total, page=page, per_page=per_page,
        items=[TenderOut(**_enrich(t, src_map)) for t in rows],
        source_counts=source_counts,
    )


@router.get("/stats")
async def tender_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(Tender))).scalar() or 0
    active = (await db.execute(select(func.count()).select_from(Tender).where(Tender.status == TenderStatus.ACTIVE))).scalar() or 0

    src_q = select(Source.id, Source.short_name, Source.color, func.count(Tender.id).label("cnt")).outerjoin(Tender).group_by(Source.id)
    src = [{"id": r.id, "name": r.short_name, "color": r.color, "count": r.cnt} for r in (await db.execute(src_q)).all()]

    return {"total_tenders": total, "active_tenders": active, "source_stats": src}


@router.get("/{tender_id}", response_model=TenderOut)
async def get_tender(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(Tender).where(Tender.id == tender_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tender not found")
    src_map = {s.id: {"short_name": s.short_name, "color": s.color} for s in (await db.execute(select(Source))).scalars().all()}
    return TenderOut(**_enrich(t, src_map))


@router.get("/search/instant")
async def instant_search(
    q: str = Query("", description="Search query"),
    source_id: Optional[str] = Query(None),
    law_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    okved: Optional[str] = Query(None),
    nmck_min: Optional[float] = Query(None),
    nmck_max: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Instant search via Meilisearch (<20ms).
    Returns highlighted results with facet distribution (source counts).
    """
    from app.services.search import search_service
    return search_service.search_tenders(
        q=q, source_id=source_id, law_type=law_type,
        region=region, okved=okved,
        nmck_min=nmck_min, nmck_max=nmck_max,
        page=page, per_page=per_page,
    )
