"""
Tender Platform — FastAPI Application
Main entry point
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import settings
from app.api import tenders, companies, requests as req_router, sources, auth, okved


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    from app.models.session import engine
    from app.models.database import Base

    # Auto-create tables
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

    # Start background scheduler (if enabled)
    try:
        from app.services.scheduler import setup_scheduler
        setup_scheduler()
    except Exception as e:
        print(f"   ⚠️ Scheduler skipped: {e}")

    yield

    # Shutdown
    try:
        from app.services.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    print("👋 Shutting down...")


app = FastAPI(
    title="Tender Platform API",
    description="Агрегатор тендерных площадок — API",
    version="0.2.0",
    lifespan=lifespan,
)

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ============================================================
# BULLETPROOF CORS — works with ngrok, Cloudflare Tunnel, etc.
# ============================================================

class TunnelCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Max-Age": "86400",
                },
            )
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "*"
        return response


app.add_middleware(TunnelCORSMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ============================================================
# API ROUTES
# ============================================================

app.include_router(tenders.router, prefix="/api/v1/tenders", tags=["Tenders"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(req_router.router, prefix="/api/v1/requests", tags=["Requests"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(okved.router, prefix="/api/v1/okved", tags=["OKVED"])

# ============================================================
# LANDING PAGE
# ============================================================

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Tender Platform API</h1><p><a href='/docs'>Docs</a></p>")


@app.get("/api", tags=["Health"])
async def api_root():
    return {"name": "Tender Platform API", "version": "0.2.0", "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ============================================================
# SCANNER MANAGEMENT (manual trigger)
# ============================================================

@app.post("/api/v1/scanner/eis/run", tags=["Scanner"])
async def run_eis_scan(background_tasks: BackgroundTasks, region: str = "77"):
    """
    Manually trigger EIS scan for a specific region.
    Runs in background — returns immediately.

    Region codes: 77=Москва, 86=ХМАО, 74=Челябинск, etc.
    """
    async def _do_scan():
        from app.models.session import AsyncSessionLocal
        from app.services.eis_scanner import EisScannerService

        scanner = EisScannerService(
            session_factory=AsyncSessionLocal,
            token=settings.EIS_TOKEN,
        )
        try:
            await scanner.scan(regions=[region])
        finally:
            await scanner.close()

    background_tasks.add_task(_do_scan)
    return {
        "status": "started",
        "region": region,
        "message": f"EIS scan for region {region} started in background. Check /api/v1/tenders for results.",
    }


@app.post("/api/v1/scanner/gosplan/run", tags=["Scanner"])
async def run_gosplan_scan(
    background_tasks: BackgroundTasks,
    group: str = "",
    limit: int = 50,
    test_mode: bool = False,
):
    """
    Manually trigger Gosplan API scan.

    - group: "construction", "it", "industry" or empty for all
    - limit: results per page (max 100)
    - test_mode: if True, fetch only 10 records (quick test)
    """
    async def _do_scan():
        from app.models.session import AsyncSessionLocal
        from app.services.gosplan import GosplanService

        service = GosplanService(
            session_factory=AsyncSessionLocal,
            use_prod=settings.GOSPLAN_USE_PROD,
            api_key=settings.GOSPLAN_API_KEY,
        )
        try:
            if test_mode:
                await service.scan_single_page(limit=10)
            else:
                groups = [group] if group else None
                await service.scan(
                    groups=groups,
                    per_page=min(limit, 100),
                )
        finally:
            await service.close()

    background_tasks.add_task(_do_scan)

    return {
        "status": "started",
        "group": group or "all",
        "test_mode": test_mode,
        "api_server": "v2.gosplan.info" if settings.GOSPLAN_USE_PROD else "v2test.gosplan.info",
        "message": "Gosplan scan started in background. Check /api/v1/tenders for results.",
    }


@app.post("/api/v1/scanner/gosplan/contracts", tags=["Scanner"])
async def run_gosplan_contracts(
    background_tasks: BackgroundTasks,
    max_pages: int = 5,
):
    """
    Manually trigger Gosplan contracts scan (/fz44/contracts).
    Updates matching tenders with winner_inn, contract_price, status=completed.
    """
    async def _do_scan():
        from app.models.session import AsyncSessionLocal
        from app.services.gosplan import GosplanService

        service = GosplanService(
            session_factory=AsyncSessionLocal,
            use_prod=settings.GOSPLAN_USE_PROD,
            api_key=settings.GOSPLAN_API_KEY,
        )
        try:
            await service.scan_contracts(max_pages=max_pages)
        finally:
            await service.close()

    background_tasks.add_task(_do_scan)
    return {
        "status": "started",
        "max_pages": max_pages,
        "message": "Contracts scan started in background.",
    }


@app.get("/api/v1/scanner/status", tags=["Scanner"])
async def scanner_status():
    """Check scanner configuration and scheduler status."""
    from app.services.scheduler import scheduler

    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })

    return {
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "scheduler_running": scheduler.running,
        "eis_token_set": bool(settings.EIS_TOKEN),
        "eis_limited_mode": settings.EIS_LIMITED_MODE,
        "eis_scan_interval_hours": settings.EIS_SCAN_INTERVAL_HOURS,
        "gosplan_enabled": settings.GOSPLAN_ENABLED,
        "gosplan_server": "prod" if settings.GOSPLAN_USE_PROD else "test",
        "gosplan_scan_interval_hours": settings.GOSPLAN_SCAN_INTERVAL_HOURS,
        "dadata_enabled": settings.DADATA_ENABLED,
        "dadata_api_key_set": bool(settings.DADATA_API_KEY),
        "dadata_batch_size": settings.DADATA_BATCH_SIZE,
        "dadata_interval_hours": settings.DADATA_INTERVAL_HOURS,
        "jobs": jobs,
    }


@app.post("/api/v1/scanner/dadata/run", tags=["Scanner"])
async def run_dadata_enrich(
    background_tasks: BackgroundTasks,
    batch_size: int = 50,
    create_stubs: bool = True,
):
    """
    Manually trigger DaData company enrichment.

    - batch_size: how many companies to enrich (default 50)
    - create_stubs: if True, first create company stubs from tender INNs
    """
    if not settings.DADATA_API_KEY:
        return {
            "status": "error",
            "message": "DADATA_API_KEY not set in .env. Get it from https://dadata.ru",
        }

    async def _do_enrich():
        from app.models.session import AsyncSessionLocal
        from app.services.dadata import DaDataService

        service = DaDataService(
            session_factory=AsyncSessionLocal,
            api_key=settings.DADATA_API_KEY,
            secret=settings.DADATA_SECRET,
        )
        try:
            if create_stubs:
                new = await service.create_stubs_from_tenders()
                print(f"[DADATA] 📦 Created {new} new company stubs")

            stats = await service.enrich_batch(limit=batch_size)
            print(f"[DADATA] ✅ Enrichment done: {stats}")
        finally:
            await service.close()

    background_tasks.add_task(_do_enrich)

    return {
        "status": "started",
        "batch_size": batch_size,
        "create_stubs": create_stubs,
        "message": "DaData enrichment started in background. Check /api/v1/companies for results.",
    }
