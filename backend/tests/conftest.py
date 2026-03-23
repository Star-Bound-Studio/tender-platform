"""
Test Configuration — Fixtures for all tests.
Uses in-memory SQLite for speed, or real PostgreSQL via TEST_DATABASE_URL env var.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from uuid import uuid4
from datetime import datetime, date, timedelta
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.models.database import Base, Source, Tender, Company, CompanyOkved, OkvedCode
from app.models.database import Financial, SroPermit, Contact, SubcontractRequest, User
from app.models.session import get_db
from app.config import settings


# ============================================================
# DATABASE FIXTURES
# ============================================================

TEST_DB_URL = "postgresql+asyncpg://tp_user:tp_secret_2026@postgres:5432/tender_platform_test"


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create fresh engine + tables per test, then drop."""
    eng = create_async_engine(TEST_DB_URL, echo=False, pool_size=5, max_overflow=0)
    factory = async_sessionmaker(eng, expire_on_commit=False)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        yield session

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB override."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================
# SEED FIXTURES — Reusable test data
# ============================================================

@pytest_asyncio.fixture
async def seed_sources(db_session: AsyncSession) -> list[Source]:
    """Insert all 7 sources."""
    sources = [
        Source(id="eis", name="ЕИС", short_name="ЕИС", source_type="eis", base_url="https://zakupki.gov.ru", color="#3b82f6", parse_method="ftp_xml", parse_frequency="every_2h"),
        Source(id="rts", name="РТС-тендер", short_name="РТС", source_type="rts", base_url="https://rts-tender.ru", color="#22c55e", parse_method="scrapy_json", parse_frequency="twice_daily"),
        Source(id="sber", name="Сбербанк-АСТ", short_name="Сбер-АСТ", source_type="sber", base_url="https://sberbank-ast.ru", color="#f59e0b", parse_method="scrapy_html", parse_frequency="twice_daily"),
        Source(id="rosneft", name="Роснефть", short_name="Роснефть", source_type="corp", base_url="https://tenders.rosneft.ru", color="#a855f7", parse_method="scrapy_html", parse_frequency="daily"),
        Source(id="gazprom", name="Газпром", short_name="Газпром", source_type="corp", base_url="https://zakupki.gazprom.ru", color="#8b5cf6", parse_method="scrapy_html", parse_frequency="daily"),
        Source(id="lukoil", name="ЛУКОЙЛ", short_name="ЛУКОЙЛ", source_type="corp", base_url="https://lukoil.ru", color="#7c3aed", parse_method="scrapy_html", parse_frequency="daily"),
        Source(id="vsem_podryad", name="Всем Подряд", short_name="Субподряды", source_type="sub", base_url="https://vsem-podryad.ru", color="#ec4899", parse_method="scrapy_html", parse_frequency="daily"),
    ]
    for s in sources:
        db_session.add(s)
    await db_session.commit()
    return sources


@pytest_asyncio.fixture
async def seed_tenders(db_session: AsyncSession, seed_sources) -> list[Tender]:
    """Insert test tenders from various sources."""
    tenders = [
        Tender(source_id="eis", source_number="EIS-TEST-001", title="Ремонт дороги М-5 Урал", law_type="44-fz", purchase_type="auction", nmck=Decimal("245000000"), customer_name="ФКУ Упрдор", customer_inn="7453098760", region="Челябинская обл.", region_code=74, status="active", publish_date=datetime.utcnow() - timedelta(days=5), deadline=datetime.utcnow() + timedelta(days=14), source_url="https://zakupki.gov.ru/test/001"),
        Tender(source_id="eis", source_number="EIS-TEST-002", title="Строительство школы на 1100 мест", law_type="44-fz", purchase_type="contest", nmck=Decimal("890000000"), customer_name="Администрация г. Тюмень", region="Тюменская обл.", region_code=72, status="active", publish_date=datetime.utcnow() - timedelta(days=3), source_url="https://zakupki.gov.ru/test/002"),
        Tender(source_id="rts", source_number="RTS-TEST-001", title="Поставка серверного оборудования для ЦОД", law_type="commercial", purchase_type="auction", nmck=Decimal("89500000"), customer_name="ПАО МТС", region="Москва", region_code=77, status="active", source_url="https://rts-tender.ru/test/001"),
        Tender(source_id="rosneft", source_number="RSN-TEST-001", title="Бурение скважин на Приобском участке", law_type="corporate", nmck=Decimal("128500000"), customer_name="ПАО Роснефть", customer_inn="7706107510", region="ХМАО-Югра", region_code=86, status="active", source_url="https://tenders.rosneft.ru/test/001"),
        Tender(source_id="vsem_podryad", source_number="VP-TEST-001", title="Монтаж вентфасада 4500 м2", law_type="subcontract", purchase_type="direct_request", nmck=Decimal("12800000"), region="Москва", region_code=77, status="active", source_url="https://vsem-podryad.ru/test/001"),
        Tender(source_id="eis", source_number="EIS-TEST-003", title="Закупка медоборудования", law_type="44-fz", nmck=Decimal("5000000"), status="completed", region="Свердловская обл.", region_code=66, source_url="https://zakupki.gov.ru/test/003"),
    ]
    for t in tenders:
        db_session.add(t)
    await db_session.commit()
    return tenders


@pytest_asyncio.fixture
async def seed_companies(db_session: AsyncSession) -> list[Company]:
    """Insert test companies with relations."""
    companies = [
        Company(inn="8601012345", ogrn="1028600508200", full_name="ООО БурСервис", short_name="БурСервис", region="ХМАО-Югра", region_code=86, director_name="Петров И.С.", primary_okved="09.10", has_sro=True, tender_wins_count=42, status="active", is_verified=True),
        Company(inn="7701234567", full_name="ООО ТрансЛогистик", short_name="ТрансЛогистик", region="Москва", region_code=77, primary_okved="49.41", has_sro=False, tender_wins_count=31, status="active"),
        Company(inn="6612345678", full_name="ООО УралЭлектроМонтаж", short_name="УралЭМ", region="Свердловская обл.", region_code=66, primary_okved="43.21", has_sro=True, tender_wins_count=24, status="active"),
    ]
    for c in companies:
        db_session.add(c)
    await db_session.flush()

    # Add relations for first company
    db_session.add(CompanyOkved(company_id=companies[0].id, okved_code="09.10", is_primary=True))
    db_session.add(CompanyOkved(company_id=companies[0].id, okved_code="42.21"))
    db_session.add(Contact(company_id=companies[0].id, contact_type="email", value="info@burservice.ru", is_primary=True))
    db_session.add(Contact(company_id=companies[0].id, contact_type="phone", value="+7 (3462) 55-00-11"))
    db_session.add(Financial(company_id=companies[0].id, year=2024, revenue=Decimal("2800000000"), profit=Decimal("196000000"), employees=450))
    db_session.add(Financial(company_id=companies[0].id, year=2023, revenue=Decimal("2500000000"), profit=Decimal("175000000"), employees=420))
    db_session.add(SroPermit(company_id=companies[0].id, sro_name="НОСТРОЙ №342", permit_number="СРО-45678", max_contract_sum=Decimal("500000000"), status="active"))

    await db_session.commit()
    return companies


@pytest_asyncio.fixture
async def seed_requests(db_session: AsyncSession, seed_sources) -> list[SubcontractRequest]:
    """Insert test subcontract requests."""
    reqs = [
        SubcontractRequest(source_id="vsem_podryad", title="Монтаж вентфасада клинкер", description="Москва. 4500 м2. Аванс 30%.", category="Фасады", budget_text="12 800 000", region="Москва", status="active", publish_date=date.today()),
        SubcontractRequest(title="Электромонтаж на складе", description="Бригада 5-8 чел.", category="Электромонтаж", budget_text="3 200 000", region="Краснодарский край", status="active", is_user_created=True, publish_date=date.today()),
        SubcontractRequest(title="Бурение скважин вахта", category="Бурение", budget_text="Договорная", region="ХМАО-Югра", status="closed"),
    ]
    for r in reqs:
        db_session.add(r)
    await db_session.commit()
    return reqs


@pytest_asyncio.fixture
async def seed_okveds(db_session: AsyncSession) -> list[OkvedCode]:
    """Insert OKVED codes."""
    codes = [
        OkvedCode(code="F", name="Строительство", level=0, section="F"),
        OkvedCode(code="42", name="Строительство инженерных сооружений", level=1, section="F", parent_code="F"),
        OkvedCode(code="42.21", name="Строительство инженерных коммуникаций", level=2, section="F", parent_code="42"),
        OkvedCode(code="09.10", name="Услуги в области добычи нефти и газа", level=2, section="B", parent_code="09"),
        OkvedCode(code="49.41", name="Грузовой автомобильный транспорт", level=2, section="H", parent_code="49"),
    ]
    for o in codes:
        db_session.add(o)
    await db_session.commit()
    return codes


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    import bcrypt

    user = User(
        email="test@example.com",
        password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8"),
        full_name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user
