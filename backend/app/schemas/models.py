"""
Tender Platform — Pydantic Schemas
Request/Response models for API
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# SOURCES
# ============================================================

class SourceOut(BaseModel):
    id: str
    name: str
    short_name: str
    source_type: str
    base_url: str
    color: str
    is_active: bool
    parse_method: Optional[str] = None
    parse_frequency: Optional[str] = None
    last_parsed_at: Optional[datetime] = None
    tender_count: int = 0

    class Config:
        from_attributes = True


# ============================================================
# TENDERS
# ============================================================

class TenderOut(BaseModel):
    id: UUID
    source_id: str
    source_number: str
    source_url: Optional[str] = None

    title: str
    description: Optional[str] = None

    law_type: str
    purchase_type: Optional[str] = None
    okved_codes: List[str] = []
    tags: List[str] = []

    nmck: Optional[Decimal] = None
    currency: str = "RUB"
    contract_price: Optional[Decimal] = None

    customer_name: Optional[str] = None
    customer_inn: Optional[str] = None
    winner_name: Optional[str] = None
    winner_inn: Optional[str] = None

    region: Optional[str] = None
    region_code: Optional[int] = None

    publish_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    status: str = "active"

    created_at: datetime
    updated_at: datetime

    # Enriched fields (added by API, not in DB)
    source_name: Optional[str] = None
    source_color: Optional[str] = None

    class Config:
        from_attributes = True


class TenderListOut(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[TenderOut]
    source_counts: dict = {}  # {"eis": 120, "rts": 45, ...}


class TenderSearchParams(BaseModel):
    q: Optional[str] = None              # Full-text search
    source_id: Optional[str] = None      # Filter by source
    law_type: Optional[str] = None       # 44-fz, 223-fz, commercial, etc.
    purchase_type: Optional[str] = None
    region: Optional[str] = None
    region_code: Optional[int] = None
    okved: Optional[str] = None          # OKVED code filter
    nmck_min: Optional[Decimal] = None
    nmck_max: Optional[Decimal] = None
    status: Optional[str] = "active"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    customer_inn: Optional[str] = None

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: str = "publish_date"        # publish_date, nmck, deadline
    sort_order: str = "desc"             # asc, desc


# ============================================================
# COMPANIES
# ============================================================

class CompanyOkvedOut(BaseModel):
    okved_code: str
    is_primary: bool = False

    class Config:
        from_attributes = True


class ContactOut(BaseModel):
    contact_type: str
    value: str
    is_primary: bool = False

    class Config:
        from_attributes = True


class SroPermitOut(BaseModel):
    sro_name: str
    permit_number: Optional[str] = None
    max_contract_sum: Optional[Decimal] = None
    status: str = "active"

    class Config:
        from_attributes = True


class FinancialOut(BaseModel):
    year: int
    revenue: Optional[Decimal] = None
    profit: Optional[Decimal] = None
    assets: Optional[Decimal] = None
    employees: Optional[int] = None

    class Config:
        from_attributes = True


class CompanyOut(BaseModel):
    id: UUID
    inn: str
    ogrn: Optional[str] = None

    full_name: str
    short_name: Optional[str] = None

    legal_address: Optional[str] = None
    region: Optional[str] = None

    director_name: Optional[str] = None
    registration_date: Optional[date] = None
    authorized_capital: Optional[Decimal] = None

    primary_okved: Optional[str] = None
    company_type: Optional[str] = None
    status: str = "active"

    tender_wins_count: int = 0
    tender_wins_sum: Optional[Decimal] = None
    arbitration_count: int = 0
    has_sro: bool = False
    is_verified: bool = False

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompanyDetailOut(CompanyOut):
    """Full company card with all relations."""
    okveds: List[CompanyOkvedOut] = []
    contacts: List[ContactOut] = []
    sro_permits: List[SroPermitOut] = []
    financials: List[FinancialOut] = []


class CompanyListOut(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[CompanyOut]


class CompanySearchParams(BaseModel):
    q: Optional[str] = None
    okved: Optional[str] = None
    region: Optional[str] = None
    region_code: Optional[int] = None
    company_type: Optional[str] = None
    has_sro: Optional[bool] = None
    status: str = "active"

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: str = "tender_wins_count"
    sort_order: str = "desc"


# ============================================================
# REQUESTS (Subcontract)
# ============================================================

class RequestOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None

    budget_text: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None

    region: Optional[str] = None
    company_name: Optional[str] = None

    status: str = "active"
    publish_date: Optional[date] = None

    source_id: Optional[str] = None
    source_url: Optional[str] = None
    is_user_created: bool = False

    created_at: datetime

    class Config:
        from_attributes = True


class RequestListOut(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[RequestOut]


class RequestCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    budget_text: Optional[str] = None
    region: Optional[str] = None
    company_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


# ============================================================
# OKVED
# ============================================================

class OkvedOut(BaseModel):
    code: str
    name: str
    section: Optional[str] = None
    section_name: Optional[str] = None
    parent_code: Optional[str] = None
    level: int = 0

    class Config:
        from_attributes = True


# ============================================================
# AUTH
# ============================================================

class UserCreate(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    phone: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


# ============================================================
# STATS
# ============================================================

class PlatformStats(BaseModel):
    total_tenders: int = 0
    active_tenders: int = 0
    total_companies: int = 0
    total_requests: int = 0
    total_sources: int = 0
    source_stats: List[SourceOut] = []
