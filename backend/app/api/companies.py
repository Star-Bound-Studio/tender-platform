"""Companies API — catalog with EGRUL data, search, filtering."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import get_db
from app.models.database import Company, CompanyOkved, Tender, Source
from app.schemas.models import CompanyOut, CompanyDetailOut, CompanyListOut, TenderOut

router = APIRouter()


def _enrich_tender(tender, src_map):
    data = {c.name: getattr(tender, c.name) for c in tender.__table__.columns}
    for key in ("okved_codes", "okpd_codes", "tags"):
        if data.get(key) is None:
            data[key] = []
    s = src_map.get(tender.source_id, {})
    data["source_name"] = s.get("short_name", "")
    data["source_color"] = s.get("color", "#666")
    return data


@router.get("", response_model=CompanyListOut)
async def list_companies(
    q: Optional[str] = Query(None),
    okved: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    company_type: Optional[str] = Query(None),
    has_sro: Optional[bool] = Query(None),
    status: str = Query("active"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("tender_wins_count"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    conds = [Company.status == status]
    if q:
        conds.append(Company.search_vector.match(q, postgresql_regconfig="russian"))
    if okved:
        conds.append(Company.id.in_(
            select(CompanyOkved.company_id).where(CompanyOkved.okved_code.startswith(okved))
        ))
    if region:
        conds.append(Company.region.ilike(f"%{region}%"))
    if company_type:
        conds.append(Company.company_type == company_type)
    if has_sro is not None:
        conds.append(Company.has_sro == has_sro)

    where = and_(*conds)
    total = (await db.execute(select(func.count()).select_from(Company).where(where))).scalar() or 0

    col_map = {"tender_wins_count": Company.tender_wins_count, "full_name": Company.full_name, "created_at": Company.created_at}
    col = col_map.get(sort_by, Company.tender_wins_count)
    order = desc(col) if sort_order == "desc" else asc(col)

    rows = (await db.execute(
        select(Company).where(where).order_by(order.nulls_last()).offset((page-1)*per_page).limit(per_page)
    )).scalars().all()

    return CompanyListOut(total=total, page=page, per_page=per_page, items=[CompanyOut.model_validate(c) for c in rows])


@router.get("/{inn}", response_model=CompanyDetailOut)
async def get_company(inn: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Company)
        .where(Company.inn == inn)
        .options(
            selectinload(Company.okveds),
            selectinload(Company.contacts),
            selectinload(Company.sro_permits),
            selectinload(Company.financials),
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    return CompanyDetailOut.model_validate(company)


@router.get("/{inn}/tenders")
async def company_tenders(inn: str, role: str = Query("all"), db: AsyncSession = Depends(get_db)):
    """Tenders where company is customer or winner."""
    conds = []
    if role == "customer":
        conds.append(Tender.customer_inn == inn)
    elif role == "winner":
        conds.append(Tender.winner_inn == inn)
    else:
        from sqlalchemy import or_
        conds.append(or_(Tender.customer_inn == inn, Tender.winner_inn == inn))

    rows = (await db.execute(
        select(Tender).where(and_(*conds)).order_by(desc(Tender.publish_date)).limit(50)
    )).scalars().all()

    src_map = {s.id: {"short_name": s.short_name, "color": s.color} for s in (await db.execute(select(Source))).scalars().all()}
    return {"inn": inn, "count": len(rows), "tenders": [TenderOut(**_enrich_tender(t, src_map)) for t in rows]}
