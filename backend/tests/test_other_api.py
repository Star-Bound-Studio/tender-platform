"""
Tests — Requests, Sources, OKVED, Auth APIs
"""

import pytest
from httpx import AsyncClient


# ============================================================
# REQUESTS (Subcontract)
# ============================================================

@pytest.mark.asyncio
class TestRequestsAPI:
    """GET/POST /api/v1/requests"""

    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/v1/requests")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_active(self, client: AsyncClient, seed_requests):
        resp = await client.get("/api/v1/requests")
        data = resp.json()
        assert data["total"] == 2  # 2 active, 1 closed
        for item in data["items"]:
            assert item["status"] == "active"

    async def test_filter_by_region(self, client: AsyncClient, seed_requests):
        resp = await client.get("/api/v1/requests", params={"region": "Москва"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["region"] == "Москва"

    async def test_filter_by_category(self, client: AsyncClient, seed_requests):
        resp = await client.get("/api/v1/requests", params={"category": "Фасады"})
        data = resp.json()
        assert data["total"] == 1
        assert "вентфасад" in data["items"][0]["title"].lower()

    async def test_create_request(self, client: AsyncClient, seed_sources):
        resp = await client.post("/api/v1/requests", json={
            "title": "Нужна бригада монтажников",
            "description": "5 человек, срок 1 мес.",
            "category": "Монтаж",
            "budget_text": "от 500 000",
            "region": "Москва",
            "company_name": "ООО Тест",
            "contact_phone": "+7 999 123-45-67",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Нужна бригада монтажников"
        assert data["is_user_created"] is True
        assert data["status"] == "active"
        assert data["id"]  # UUID generated

    async def test_create_request_validation(self, client: AsyncClient, seed_sources):
        """Title too short."""
        resp = await client.post("/api/v1/requests", json={"title": "abc"})
        assert resp.status_code == 422  # Validation error

    async def test_create_request_minimal(self, client: AsyncClient, seed_sources):
        """Only title required."""
        resp = await client.post("/api/v1/requests", json={"title": "Нужен электрик срочно"})
        assert resp.status_code == 201


# ============================================================
# SOURCES
# ============================================================

@pytest.mark.asyncio
class TestSourcesAPI:
    """GET /api/v1/sources"""

    async def test_list_sources(self, client: AsyncClient, seed_sources):
        resp = await client.get("/api/v1/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        ids = [s["id"] for s in data]
        assert "eis" in ids
        assert "rts" in ids
        assert "vsem_podryad" in ids

    async def test_source_has_fields(self, client: AsyncClient, seed_sources):
        resp = await client.get("/api/v1/sources")
        eis = next(s for s in resp.json() if s["id"] == "eis")
        assert eis["name"] == "ЕИС"
        assert eis["short_name"] == "ЕИС"
        assert eis["color"] == "#3b82f6"
        assert eis["is_active"] is True


# ============================================================
# OKVED
# ============================================================

@pytest.mark.asyncio
class TestOkvedAPI:
    """GET /api/v1/okved/*"""

    async def test_tree(self, client: AsyncClient, seed_okveds):
        resp = await client.get("/api/v1/okved/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5
        codes = [o["code"] for o in data]
        assert "42.21" in codes
        assert "09.10" in codes

    async def test_tree_by_section(self, client: AsyncClient, seed_okveds):
        resp = await client.get("/api/v1/okved/tree", params={"section": "F"})
        data = resp.json()
        for item in data:
            assert item["section"] == "F"

    async def test_search_by_code(self, client: AsyncClient, seed_okveds):
        resp = await client.get("/api/v1/okved/search", params={"q": "42"})
        data = resp.json()
        assert len(data) >= 1
        assert any("42" in o["code"] for o in data)

    async def test_search_by_name(self, client: AsyncClient, seed_okveds):
        resp = await client.get("/api/v1/okved/search", params={"q": "нефт"})
        data = resp.json()
        assert len(data) >= 1

    async def test_search_empty(self, client: AsyncClient, seed_okveds):
        resp = await client.get("/api/v1/okved/search", params={"q": "zzzzzzz"})
        data = resp.json()
        assert len(data) == 0


# ============================================================
# AUTH
# ============================================================

@pytest.mark.asyncio
class TestAuthAPI:
    """POST /api/v1/auth/*"""

    async def test_register(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "securepass",
            "full_name": "Новый Пользователь",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["full_name"] == "Новый Пользователь"
        assert data["role"] == "user"
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate(self, client: AsyncClient, seed_user):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "anotherpass",
        })
        assert resp.status_code == 400  # Already exists

    async def test_login_success(self, client: AsyncClient, seed_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    async def test_login_wrong_password(self, client: AsyncClient, seed_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == 401
