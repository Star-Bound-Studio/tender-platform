"""Subcontract Requests API — list, create, filter."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import get_db
from app.models.database import SubcontractRequest, RequestStatus
from app.schemas.models import RequestOut, RequestListOut, RequestCreate

router = APIRouter()


@router.get("", response_model=RequestListOut)
async def list_requests(
    q: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: str = Query("active"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conds = [SubcontractRequest.status == status]
    if q:
        conds.append(SubcontractRequest.search_vector.match(q, postgresql_regconfig="russian"))
    if region:
        conds.append(SubcontractRequest.region.ilike(f"%{region}%"))
    if category:
        conds.append(SubcontractRequest.category == category)

    where = and_(*conds)
    total = (await db.execute(select(func.count()).select_from(SubcontractRequest).where(where))).scalar() or 0

    rows = (await db.execute(
        select(SubcontractRequest).where(where).order_by(desc(SubcontractRequest.created_at)).offset((page-1)*per_page).limit(per_page)
    )).scalars().all()

    return RequestListOut(total=total, page=page, per_page=per_page, items=[RequestOut.model_validate(r) for r in rows])


@router.post("", response_model=RequestOut, status_code=201)
async def create_request(data: RequestCreate, db: AsyncSession = Depends(get_db)):
    req = SubcontractRequest(
        title=data.title,
        description=data.description,
        category=data.category,
        budget_text=data.budget_text,
        region=data.region,
        company_name=data.company_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        is_user_created=True,
        status=RequestStatus.ACTIVE,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return RequestOut.model_validate(req)
