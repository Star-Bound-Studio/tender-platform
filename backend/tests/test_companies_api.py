"""
Tests — Companies API
Covers: list, search, filters, detail with relations, company tenders
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCompaniesList:
    """GET /api/v1/companies"""

    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/v1/companies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_all(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_filter_by_region(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies", params={"region": "Москва"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["inn"] == "7701234567"

    async def test_filter_has_sro(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies", params={"has_sro": True})
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["has_sro"] is True

    async def test_filter_no_sro(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies", params={"has_sro": False})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["has_sro"] is False

    async def test_sort_by_wins(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies", params={"sort_by": "tender_wins_count", "sort_order": "desc"})
        data = resp.json()
        wins = [i["tender_wins_count"] for i in data["items"]]
        assert wins == sorted(wins, reverse=True)

    async def test_pagination(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies", params={"per_page": 1, "page": 1})
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3


@pytest.mark.asyncio
class TestCompanyDetail:
    """GET /api/v1/companies/{inn}"""

    async def test_get_by_inn(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345")
        assert resp.status_code == 200
        data = resp.json()
        assert data["inn"] == "8601012345"
        assert data["full_name"] == "ООО БурСервис"
        assert data["region"] == "ХМАО-Югра"
        assert data["has_sro"] is True

    async def test_detail_includes_okveds(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345")
        data = resp.json()
        assert "okveds" in data
        assert len(data["okveds"]) == 2
        codes = [o["okved_code"] for o in data["okveds"]]
        assert "09.10" in codes
        assert "42.21" in codes

    async def test_detail_includes_contacts(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345")
        data = resp.json()
        assert "contacts" in data
        assert len(data["contacts"]) == 2
        types = [c["contact_type"] for c in data["contacts"]]
        assert "email" in types
        assert "phone" in types

    async def test_detail_includes_financials(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345")
        data = resp.json()
        assert "financials" in data
        assert len(data["financials"]) == 2
        years = [f["year"] for f in data["financials"]]
        assert 2024 in years
        assert 2023 in years

    async def test_detail_includes_sro(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345")
        data = resp.json()
        assert "sro_permits" in data
        assert len(data["sro_permits"]) == 1
        assert data["sro_permits"][0]["status"] == "active"

    async def test_nonexistent_inn(self, client: AsyncClient, seed_companies):
        resp = await client.get("/api/v1/companies/0000000000")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestCompanyTenders:
    """GET /api/v1/companies/{inn}/tenders"""

    async def test_company_tenders(self, client: AsyncClient, seed_tenders, seed_companies):
        # Rosneft INN is used as customer in seed_tenders
        resp = await client.get("/api/v1/companies/7706107510/tenders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["inn"] == "7706107510"
        assert data["count"] >= 1

    async def test_company_tenders_empty(self, client: AsyncClient, seed_tenders, seed_companies):
        resp = await client.get("/api/v1/companies/8601012345/tenders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0  # BurService isn't customer/winner in test data
