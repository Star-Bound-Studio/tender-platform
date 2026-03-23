"""
Tender Platform — Database Models
SQLAlchemy ORM models for PostgreSQL

Tables:
  - sources          — тендерные площадки (ЕИС, РТС, Роснефть и т.д.)
  - tenders          — тендеры/закупки со всех площадок
  - companies        — компании из ЕГРЮЛ
  - company_okveds   — ОКВЭД компаний (many-to-many)
  - okved_codes      — справочник ОКВЭД-2
  - sro_permits      — допуски СРО
  - arbitrations     — арбитражные дела
  - financials       — бухотчётность (bo.nalog.ru)
  - contacts         — контакты компаний
  - requests         — заявки на субподряд
  - users            — пользователи платформы
  - subscriptions    — подписки на уведомления
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Integer, BigInteger, Numeric, Boolean, Date,
    DateTime, ForeignKey, Index, Enum as SAEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


# ============================================================
# ENUMS
# ============================================================

class SourceType(str, enum.Enum):
    EIS = "eis"                # zakupki.gov.ru (44-ФЗ, 223-ФЗ)
    RTS = "rts"                # РТС-тендер
    SBERBANK_AST = "sber"      # Сбербанк-АСТ
    CORPORATE = "corp"         # Роснефть, Газпром, ЛУКОЙЛ
    SUBCONTRACT = "sub"        # Всем Подряд и аналоги


class LawType(str, enum.Enum):
    FZ44 = "44-fz"
    FZ223 = "223-fz"
    COMMERCIAL = "commercial"
    CORPORATE = "corporate"
    SUBCONTRACT = "subcontract"


class PurchaseType(str, enum.Enum):
    AUCTION = "auction"                 # Электронный аукцион
    QUOTATION = "quotation"             # Запрос котировок
    CONTEST = "contest"                 # Конкурс
    SINGLE_SOURCE = "single_source"     # Единственный поставщик
    DIRECT_REQUEST = "direct_request"   # Прямая заявка (субподряд)
    OTHER = "other"


class TenderStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DRAFT = "draft"


class CompanyType(str, enum.Enum):
    CONTRACTOR = "contractor"     # Подрядчик
    CUSTOMER = "customer"         # Заказчик
    SUPPLIER = "supplier"         # Поставщик
    MIXED = "mixed"               # Смешанный


class CompanyStatus(str, enum.Enum):
    ACTIVE = "active"
    LIQUIDATED = "liquidated"
    REORGANIZING = "reorganizing"


class RequestStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


# ============================================================
# SOURCES — Тендерные площадки
# ============================================================

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # 'eis', 'rts', etc.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")  # HEX for UI badge
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parse_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'ftp_xml', 'scrapy_html', etc.
    parse_frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'every_2h', 'daily', etc.
    last_parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tender_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenders: Mapped[List["Tender"]] = relationship(back_populates="source")


# ============================================================
# TENDERS — Тендеры / Закупки
# ============================================================

class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source reference
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_number: Mapped[str] = mapped_column(String(100), nullable=False)  # Номер на площадке
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Прямая ссылка на оригинал

    # Core fields
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Classification
    law_type: Mapped[LawType] = mapped_column(SAEnum(LawType), nullable=False)
    purchase_type: Mapped[Optional[PurchaseType]] = mapped_column(SAEnum(PurchaseType))
    okved_codes: Mapped[Optional[list]] = mapped_column(ARRAY(String(20)))
    okpd_codes: Mapped[Optional[list]] = mapped_column(ARRAY(String(20)))
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(100)))

    # Price
    nmck: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))  # НМЦ контракта
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    contract_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))  # Цена контракта

    # Customer
    customer_name: Mapped[Optional[str]] = mapped_column(String(500))
    customer_inn: Mapped[Optional[str]] = mapped_column(String(12))

    # Winner
    winner_name: Mapped[Optional[str]] = mapped_column(String(500))
    winner_inn: Mapped[Optional[str]] = mapped_column(String(12))

    # Location
    region: Mapped[Optional[str]] = mapped_column(String(200))
    region_code: Mapped[Optional[int]] = mapped_column(Integer)

    # Dates
    publish_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Status
    status: Mapped[TenderStatus] = mapped_column(SAEnum(TenderStatus), default=TenderStatus.ACTIVE)

    # Raw data (for debugging/reprocessing)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Full-text search vector
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    source: Mapped["Source"] = relationship(back_populates="tenders")

    # Constraints
    __table_args__ = (
        UniqueConstraint("source_id", "source_number", name="uq_tender_source"),
        Index("ix_tender_search", "search_vector", postgresql_using="gin"),
        Index("ix_tender_source_id", "source_id"),
        Index("ix_tender_status", "status"),
        Index("ix_tender_law_type", "law_type"),
        Index("ix_tender_region_code", "region_code"),
        Index("ix_tender_customer_inn", "customer_inn"),
        Index("ix_tender_winner_inn", "winner_inn"),
        Index("ix_tender_publish_date", "publish_date"),
        Index("ix_tender_deadline", "deadline"),
        Index("ix_tender_nmck", "nmck"),
        Index("ix_tender_okved", "okved_codes", postgresql_using="gin"),
    )


# ============================================================
# OKVED CODES — Справочник ОКВЭД-2
# ============================================================

class OkvedCode(Base):
    __tablename__ = "okved_codes"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # '09.10', '42.21'
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(5))    # 'B', 'F'
    section_name: Mapped[Optional[str]] = mapped_column(String(300))
    parent_code: Mapped[Optional[str]] = mapped_column(String(20))  # For tree structure
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0=section, 1=class, 2=group, 3=subgroup

    __table_args__ = (
        Index("ix_okved_section", "section"),
        Index("ix_okved_parent", "parent_code"),
    )


# ============================================================
# COMPANIES — Компании из ЕГРЮЛ
# ============================================================

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inn: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    ogrn: Mapped[Optional[str]] = mapped_column(String(15), unique=True)
    
    # Names
    full_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Address
    legal_address: Mapped[Optional[str]] = mapped_column(Text)
    region: Mapped[Optional[str]] = mapped_column(String(200))
    region_code: Mapped[Optional[int]] = mapped_column(Integer)

    # Director
    director_name: Mapped[Optional[str]] = mapped_column(String(300))
    director_title: Mapped[Optional[str]] = mapped_column(String(200))

    # Registration
    registration_date: Mapped[Optional[date]] = mapped_column(Date)
    authorized_capital: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    # Classification
    primary_okved: Mapped[Optional[str]] = mapped_column(String(20))
    company_type: Mapped[Optional[CompanyType]] = mapped_column(SAEnum(CompanyType))
    status: Mapped[CompanyStatus] = mapped_column(SAEnum(CompanyStatus), default=CompanyStatus.ACTIVE)

    # Computed / cached stats
    tender_wins_count: Mapped[int] = mapped_column(Integer, default=0)
    tender_wins_sum: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    arbitration_count: Mapped[int] = mapped_column(Integer, default=0)
    has_sro: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    egrul_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Full-text search
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    okveds: Mapped[List["CompanyOkved"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    contacts: Mapped[List["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    sro_permits: Mapped[List["SroPermit"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    arbitrations: Mapped[List["Arbitration"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    financials: Mapped[List["Financial"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_company_search", "search_vector", postgresql_using="gin"),
        Index("ix_company_inn", "inn"),
        Index("ix_company_region_code", "region_code"),
        Index("ix_company_primary_okved", "primary_okved"),
        Index("ix_company_status", "status"),
        Index("ix_company_tender_wins", "tender_wins_count"),
    )


# ============================================================
# COMPANY_OKVEDS — ОКВЭД компании (many-to-many)
# ============================================================

class CompanyOkved(Base):
    __tablename__ = "company_okveds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    okved_code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped["Company"] = relationship(back_populates="okveds")

    __table_args__ = (
        UniqueConstraint("company_id", "okved_code", name="uq_company_okved"),
        Index("ix_company_okved_code", "okved_code"),
    )


# ============================================================
# CONTACTS — Контакты компаний
# ============================================================

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    contact_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'email', 'phone', 'website'
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))  # 'egrul', '2gis', 'website'
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped["Company"] = relationship(back_populates="contacts")


# ============================================================
# SRO_PERMITS — Допуски СРО
# ============================================================

class SroPermit(Base):
    __tablename__ = "sro_permits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    sro_name: Mapped[str] = mapped_column(String(500), nullable=False)
    permit_number: Mapped[Optional[str]] = mapped_column(String(100))
    max_contract_sum: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(50), default="active")  # 'active', 'suspended', 'revoked'
    issue_date: Mapped[Optional[date]] = mapped_column(Date)

    company: Mapped["Company"] = relationship(back_populates="sro_permits")


# ============================================================
# ARBITRATIONS — Арбитражные дела
# ============================================================

class Arbitration(Base):
    __tablename__ = "arbitrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    case_number: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'plaintiff', 'defendant'
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(50))  # 'active', 'closed', 'appeal'
    court: Mapped[Optional[str]] = mapped_column(String(300))
    filing_date: Mapped[Optional[date]] = mapped_column(Date)

    company: Mapped["Company"] = relationship(back_populates="arbitrations")

    __table_args__ = (
        UniqueConstraint("company_id", "case_number", name="uq_company_case"),
    )


# ============================================================
# FINANCIALS — Бухотчётность (bo.nalog.ru)
# ============================================================

class Financial(Base):
    __tablename__ = "financials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))  # Выручка
    profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))   # Прибыль
    assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))   # Активы
    employees: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="bo.nalog.ru")

    company: Mapped["Company"] = relationship(back_populates="financials")

    __table_args__ = (
        UniqueConstraint("company_id", "year", name="uq_company_year"),
    )


# ============================================================
# REQUESTS — Заявки на субподряд
# ============================================================

class SubcontractRequest(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source (parsed or user-created)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    is_user_created: Mapped[bool] = mapped_column(Boolean, default=False)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(200))

    # Budget
    budget_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    budget_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    budget_text: Mapped[Optional[str]] = mapped_column(String(200))  # 'Договорная', 'от 7000 р/м3'

    # Location
    region: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text)

    # Contact
    company_name: Mapped[Optional[str]] = mapped_column(String(500))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_email: Mapped[Optional[str]] = mapped_column(String(200))

    # Status & dates
    status: Mapped[RequestStatus] = mapped_column(SAEnum(RequestStatus), default=RequestStatus.ACTIVE)
    publish_date: Mapped[Optional[date]] = mapped_column(Date)
    expire_date: Mapped[Optional[date]] = mapped_column(Date)

    # Search
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_request_search", "search_vector", postgresql_using="gin"),
        Index("ix_request_status", "status"),
        Index("ix_request_region", "region"),
    )


# ============================================================
# USERS — Пользователи
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(300))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    company_inn: Mapped[Optional[str]] = mapped_column(String(12))  # Linked company
    role: Mapped[str] = mapped_column(String(20), default="user")  # 'user', 'admin'

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ============================================================
# SUBSCRIPTIONS — Подписки на уведомления
# ============================================================

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Filter criteria (JSONB for flexibility)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example: {"okved_codes": ["42.21", "43.99"], "regions": ["ХМАО-Югра"], "nmck_min": 10000000}
    
    name: Mapped[Optional[str]] = mapped_column(String(200))  # User-given name
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="subscriptions")


# ============================================================
# PARSE_LOG — Лог парсинга (для мониторинга)
# ============================================================

class ParseLog(Base):
    __tablename__ = "parse_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # 'running', 'success', 'error'
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
