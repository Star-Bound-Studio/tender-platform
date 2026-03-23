"""
Tests — Data Models
ORM constraints, enums, computed fields, model validation.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.database import (
    Tender, Company, Source, CompanyOkved, Financial,
    TenderStatus, LawType, CompanyStatus, SourceType,
)


@pytest.mark.asyncio
class TestSourceModel:

    async def test_create_source(self, db_session: AsyncSession):
        s = Source(id="test", name="Test Source", short_name="TST", source_type="eis",
                   base_url="https://test.com", color="#ff0000", parse_method="scrapy_html", parse_frequency="daily")
        db_session.add(s)
        await db_session.commit()

        result = await db_session.execute(select(Source).where(Source.id == "test"))
        loaded = result.scalar_one()
        assert loaded.name == "Test Source"
        assert loaded.is_active is True
        assert loaded.tender_count == 0

    async def test_source_duplicate_id(self, db_session: AsyncSession):
        s1 = Source(id="dup", name="First", short_name="F", source_type="eis", base_url="https://1.com", parse_method="ftp", parse_frequency="daily")
        db_session.add(s1)
        await db_session.commit()

        s2 = Source(id="dup", name="Second", short_name="S", source_type="rts", base_url="https://2.com", parse_method="ftp", parse_frequency="daily")
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            await db_session.commit()


@pytest.mark.asyncio
class TestTenderModel:

    async def test_create_tender(self, db_session: AsyncSession, seed_sources):
        t = Tender(
            source_id="eis", source_number="TEST-001",
            title="Тестовый тендер", law_type="44-fz",
            nmck=Decimal("1000000"), status="active",
        )
        db_session.add(t)
        await db_session.commit()

        result = await db_session.execute(select(Tender).where(Tender.source_number == "TEST-001"))
        loaded = result.scalar_one()
        assert loaded.title == "Тестовый тендер"
        assert loaded.nmck == Decimal("1000000")
        assert loaded.id is not None  # UUID auto-generated
        assert loaded.created_at is not None

    async def test_unique_source_number(self, db_session: AsyncSession, seed_sources):
        """Same source + number = conflict."""
        t1 = Tender(source_id="eis", source_number="DUP-001", title="First", law_type="44-fz")
        db_session.add(t1)
        await db_session.commit()

        t2 = Tender(source_id="eis", source_number="DUP-001", title="Second", law_type="44-fz")
        db_session.add(t2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_different_source_same_number_ok(self, db_session: AsyncSession, seed_sources):
        """Different source + same number = OK (different platforms)."""
        t1 = Tender(source_id="eis", source_number="SAME-001", title="EIS tender", law_type="44-fz")
        t2 = Tender(source_id="rts", source_number="SAME-001", title="RTS tender", law_type="commercial")
        db_session.add_all([t1, t2])
        await db_session.commit()

        count = (await db_session.execute(
            select(Tender).where(Tender.source_number == "SAME-001")
        )).scalars().all()
        assert len(count) == 2

    async def test_tender_okved_array(self, db_session: AsyncSession, seed_sources):
        """OKVED codes stored as array."""
        t = Tender(
            source_id="eis", source_number="OKV-001", title="With OKVEDs",
            law_type="44-fz", okved_codes=["42.21", "43.99"],
        )
        db_session.add(t)
        await db_session.commit()

        loaded = (await db_session.execute(
            select(Tender).where(Tender.source_number == "OKV-001")
        )).scalar_one()
        assert loaded.okved_codes == ["42.21", "43.99"]


@pytest.mark.asyncio
class TestCompanyModel:

    async def test_create_company(self, db_session: AsyncSession):
        c = Company(inn="1234567890", full_name="ООО Тест", region="Москва", status="active")
        db_session.add(c)
        await db_session.commit()

        loaded = (await db_session.execute(select(Company).where(Company.inn == "1234567890"))).scalar_one()
        assert loaded.full_name == "ООО Тест"
        assert loaded.tender_wins_count == 0
        assert loaded.has_sro is False

    async def test_unique_inn(self, db_session: AsyncSession):
        c1 = Company(inn="1111111111", full_name="First")
        db_session.add(c1)
        await db_session.commit()

        c2 = Company(inn="1111111111", full_name="Duplicate")
        db_session.add(c2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_company_with_okveds(self, db_session: AsyncSession):
        c = Company(inn="2222222222", full_name="With OKVED")
        db_session.add(c)
        await db_session.flush()

        db_session.add(CompanyOkved(company_id=c.id, okved_code="42.21", is_primary=True))
        db_session.add(CompanyOkved(company_id=c.id, okved_code="43.99"))
        await db_session.commit()

        loaded = (await db_session.execute(
            select(Company).where(Company.inn == "2222222222")
        )).scalar_one()
        assert loaded.id == c.id

    async def test_company_financials_unique_year(self, db_session: AsyncSession):
        """One financial record per company per year."""
        c = Company(inn="3333333333", full_name="Fin Test")
        db_session.add(c)
        await db_session.flush()

        f1 = Financial(company_id=c.id, year=2024, revenue=Decimal("1000000"))
        db_session.add(f1)
        await db_session.commit()

        f2 = Financial(company_id=c.id, year=2024, revenue=Decimal("2000000"))
        db_session.add(f2)
        with pytest.raises(IntegrityError):
            await db_session.commit()


@pytest.mark.asyncio
class TestEnums:
    """Test that enum values work correctly."""

    async def test_tender_status_values(self, db_session: AsyncSession, seed_sources):
        for status in ["active", "completed", "cancelled"]:
            t = Tender(source_id="eis", source_number=f"ENUM-{status}", title=f"Status {status}",
                       law_type="44-fz", status=status)
            db_session.add(t)
        await db_session.commit()

        active = (await db_session.execute(
            select(Tender).where(Tender.status == "active")
        )).scalars().all()
        assert len(active) == 1

    async def test_law_type_values(self, db_session: AsyncSession, seed_sources):
        for law in ["44-fz", "223-fz", "commercial", "corporate", "subcontract"]:
            t = Tender(source_id="eis", source_number=f"LAW-{law}", title=f"Law {law}", law_type=law)
            db_session.add(t)
        await db_session.commit()
        all_t = (await db_session.execute(select(Tender))).scalars().all()
        assert len(all_t) == 5
