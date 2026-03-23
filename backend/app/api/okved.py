"""OKVED API — hierarchical tree for filters."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import get_db
from app.models.database import OkvedCode
from app.schemas.models import OkvedOut

router = APIRouter()


@router.get("/tree")
async def okved_tree(section: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """Get OKVED tree. If section provided, return children."""
    q = select(OkvedCode)
    if section:
        q = q.where(OkvedCode.section == section)
    q = q.order_by(OkvedCode.code)
    rows = (await db.execute(q)).scalars().all()
    return [OkvedOut.model_validate(r) for r in rows]


@router.get("/search")
async def okved_search(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    """Search OKVED by code or name."""
    rows = (await db.execute(
        select(OkvedCode).where(
            OkvedCode.code.startswith(q) | OkvedCode.name.ilike(f"%{q}%")
        ).limit(20)
    )).scalars().all()
    return [OkvedOut.model_validate(r) for r in rows]
