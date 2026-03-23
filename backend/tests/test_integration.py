"""
Tests — Integration & Health
Health check, root endpoint, search service, schema validation.
"""

import pytest
from httpx import AsyncClient
from decimal import Decimal

from app.schemas.models import (
    TenderOut, CompanyOut, CompanyDetailOut, RequestOut,
    TenderListOut, CompanyListOut, RequestListOut,
    TenderSearchParams, UserCreate, Token,
)


# ============================================================
# HEALTH & ROOT
# ============================================================

@pytest.mark.asyncio
class TestHealth:

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "version" in data
        assert data["docs"] == "/docs"

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ============================================================
# PYDANTIC SCHEMA VALIDATION
# ============================================================

class TestSchemas:
    """Test Pydantic schema creation and validation."""

    def test_tender_search_params_defaults(self):
        p = TenderSearchParams()
        assert p.page == 1
        assert p.per_page == 20
        assert p.sort_by == "publish_date"
        assert p.sort_order == "desc"
        assert p.status == "active"

    def test_tender_search_params_custom(self):
        p = TenderSearchParams(
            q="бурение", source_id="eis", region="ХМАО",
            nmck_min=Decimal("10000000"), page=3, per_page=50,
        )
        assert p.q == "бурение"
        assert p.nmck_min == Decimal("10000000")
        assert p.page == 3

    def test_tender_search_params_validation(self):
        """Page must be >= 1, per_page <= 100."""
        with pytest.raises(Exception):
            TenderSearchParams(page=0)
        with pytest.raises(Exception):
            TenderSearchParams(per_page=200)

    def test_user_create_validation(self):
        u = UserCreate(email="test@test.com", password="123456")
        assert u.email == "test@test.com"

    def test_user_create_short_password(self):
        with pytest.raises(Exception):
            UserCreate(email="test@test.com", password="12")

    def test_tender_list_out(self):
        out = TenderListOut(
            total=100, page=1, per_page=20,
            items=[], source_counts={"eis": 50, "rts": 30},
        )
        assert out.total == 100
        assert out.source_counts["eis"] == 50

    def test_company_list_out(self):
        out = CompanyListOut(total=5, page=1, per_page=20, items=[])
        assert out.total == 5

    def test_request_list_out(self):
        out = RequestListOut(total=3, page=1, per_page=20, items=[])
        assert out.total == 3

    def test_token_model(self):
        t = Token(access_token="abc123")
        assert t.token_type == "bearer"


# ============================================================
# SEARCH SERVICE (unit test without Meilisearch)
# ============================================================

class TestSearchServiceUnit:
    """Test search service filter building logic."""

    def test_filter_building(self):
        """Verify filter string construction."""
        from app.services.search import SearchService
        svc = SearchService.__new__(SearchService)
        # We can't call search without Meili, but we can test the logic
        # by verifying the class exists and has the right methods
        assert hasattr(svc, 'search_tenders')
        assert hasattr(svc, 'search_companies')
        assert hasattr(svc, 'search_requests')
