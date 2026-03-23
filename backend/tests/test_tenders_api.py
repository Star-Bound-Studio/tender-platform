"""
Tests — Tenders API
Covers: list, filters, search, detail, stats, pagination, sorting
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTendersList:
    """GET /api/v1/tenders"""

    async def test_list_empty(self, client: AsyncClient, seed_sources):
        """Returns empty list when no tenders."""
        resp = await client.get("/api/v1/tenders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1

    async def test_list_all(self, client: AsyncClient, seed_tenders):
        """Returns all active tenders."""
        resp = await client.get("/api/v1/tenders")
        assert resp.status_code == 200
        data = resp.json()
        # 5 active + 1 completed, but default status=active
        assert data["total"] == 5
        assert len(data["items"]) == 5

    async def test_list_includes_source_counts(self, client: AsyncClient, seed_tenders):
        """Response includes source_counts for UI badges."""
        resp = await client.get("/api/v1/tenders")
        data = resp.json()
        assert "source_counts" in data
        assert data["source_counts"].get("eis", 0) >= 1
        assert data["source_counts"].get("rts", 0) >= 1

    async def test_list_all_statuses(self, client: AsyncClient, seed_tenders):
        """Can fetch all statuses."""
        resp = await client.get("/api/v1/tenders", params={"status": ""})
        data = resp.json()
        assert data["total"] == 6  # 5 active + 1 completed


@pytest.mark.asyncio
class TestTendersFilter:
    """Filtering tenders by various criteria."""

    async def test_filter_by_source(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"source_id": "eis"})
        data = resp.json()
        assert data["total"] == 2  # EIS-TEST-001, EIS-TEST-002 (active only)
        for item in data["items"]:
            assert item["source_id"] == "eis"

    async def test_filter_by_law_type(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"law_type": "corporate"})
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["law_type"] == "corporate"

    async def test_filter_by_region(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"region": "Москва"})
        data = resp.json()
        assert data["total"] >= 2  # RTS + VP both in Moscow

    async def test_filter_by_region_code(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"region_code": 86})
        data = resp.json()
        assert data["total"] >= 1  # ХМАО

    async def test_filter_by_nmck_range(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"nmck_min": 100000000, "nmck_max": 300000000})
        data = resp.json()
        for item in data["items"]:
            nmck = float(item["nmck"])
            assert 100000000 <= nmck <= 300000000

    async def test_filter_by_customer_inn(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"customer_inn": "7706107510"})
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["customer_inn"] == "7706107510"

    async def test_combined_filters(self, client: AsyncClient, seed_tenders):
        """Multiple filters combined with AND."""
        resp = await client.get("/api/v1/tenders", params={
            "source_id": "eis", "region_code": 74,
        })
        data = resp.json()
        assert data["total"] == 1
        assert "Урал" in data["items"][0]["title"]


@pytest.mark.asyncio
class TestTendersPagination:
    """Pagination and sorting."""

    async def test_pagination(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"per_page": 2, "page": 1})
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["per_page"] == 2
        assert data["page"] == 1

    async def test_pagination_page2(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"per_page": 2, "page": 2})
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    async def test_sort_by_nmck_desc(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"sort_by": "nmck", "sort_order": "desc"})
        data = resp.json()
        items = data["items"]
        prices = [float(i["nmck"]) for i in items if i["nmck"]]
        assert prices == sorted(prices, reverse=True)

    async def test_sort_by_nmck_asc(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders", params={"sort_by": "nmck", "sort_order": "asc"})
        data = resp.json()
        items = data["items"]
        prices = [float(i["nmck"]) for i in items if i["nmck"]]
        assert prices == sorted(prices)


@pytest.mark.asyncio
class TestTenderDetail:
    """GET /api/v1/tenders/{id}"""

    async def test_get_by_id(self, client: AsyncClient, seed_tenders):
        # First get the list to get an ID
        resp = await client.get("/api/v1/tenders")
        tender_id = resp.json()["items"][0]["id"]

        resp2 = await client.get(f"/api/v1/tenders/{tender_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["id"] == tender_id
        assert data["title"]
        assert data["source_id"]

    async def test_get_nonexistent(self, client: AsyncClient, seed_sources):
        resp = await client.get("/api/v1/tenders/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    async def test_detail_has_source_name(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders")
        tender_id = resp.json()["items"][0]["id"]
        resp2 = await client.get(f"/api/v1/tenders/{tender_id}")
        data = resp2.json()
        assert data.get("source_name") or data.get("source_color")


@pytest.mark.asyncio
class TestTenderStats:
    """GET /api/v1/tenders/stats"""

    async def test_stats(self, client: AsyncClient, seed_tenders):
        resp = await client.get("/api/v1/tenders/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tenders"] >= 5
        assert data["active_tenders"] >= 5
        assert "source_stats" in data
        assert len(data["source_stats"]) >= 1
