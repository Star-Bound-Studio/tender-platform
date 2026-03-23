"""
Tender Platform — FastAPI Application
Main entry point
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api import tenders, companies, requests as req_router, sources, auth, okved


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    from app.models.session import engine
    from app.models.database import Base

    # Авто-создание таблиц при запуске
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"🚀 Tender Platform API started")
    print(f"   Database connected")
    
    # Авто-заполнение демо-данными, если база пуста
    try:
        from app.models.session import AsyncSessionLocal
        from app.models.database import Source
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as session:
            count = (await session.execute(select(func.count()).select_from(Source))).scalar()
            if count == 0:
                print("   📦 Seeding demo data...")
                from app.seed import seed
                await seed()
                print("   ✅ Demo data loaded!")
            else:
                print(f"   📊 {count} sources already in DB")
    except Exception as e:
        print(f"   ⚠️ Seed skipped: {e}")

    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="Tender Platform API",
    description="Агрегатор тендерных площадок — API",
    version="0.1.0",
    lifespan=lifespan,
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# РОУТЫ (API)
# ============================================================

app.include_router(tenders.router, prefix="/api/v1/tenders", tags=["Tenders"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(req_router.router, prefix="/api/v1/requests", tags=["Requests"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(okved.router, prefix="/api/v1/okved", tags=["OKVED"])

# ============================================================
# ЛЕНДИНГ И ПРОВЕРКА СТАТУСА
# ============================================================

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Отдает красивую главную страницу из index.html"""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Tender Platform API</h1><p><a href='/docs'>Docs</a></p>")


@app.get("/api", tags=["Health"])
async def api_root():
    """Информационный роут для проверки работы API"""
    return {
        "name": "Tender Platform API", 
        "version": "0.1.0", 
        "status": "running", 
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    """Простой health-check для Render"""
    return {"status": "ok"}
