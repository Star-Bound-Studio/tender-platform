# Tender Platform

Агрегатор тендерных площадок — все закупки, компании и заявки на субподряд в одном окне.

## Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Celery
- **Database:** PostgreSQL 16 + Meilisearch + Redis
- **Frontend:** Flutter (Web + Android)
- **Parsing:** Scrapy + lxml + FTP (EIS)

## Quick Start

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env with your values

# 2. Start all services
docker compose up -d

# 3. Check health
curl http://localhost:8000/health
# → {"status": "ok"}

# 4. Open API docs
open http://localhost:8000/docs

# 5. Check Meilisearch
open http://localhost:7700
```

## Services

| Service      | Port  | Description                    |
|-------------|-------|--------------------------------|
| API         | 8000  | FastAPI backend + Swagger docs |
| PostgreSQL  | 5432  | Main database                  |
| Redis       | 6379  | Cache + Celery broker          |
| Meilisearch | 7700  | Instant search engine          |

## API Endpoints

### Tenders
- `GET /api/v1/tenders` — list with filters (source, OKVED, region, price, date)
- `GET /api/v1/tenders/search/instant` — Meilisearch instant search
- `GET /api/v1/tenders/stats` — platform statistics
- `GET /api/v1/tenders/{id}` — tender detail

### Companies
- `GET /api/v1/companies` — catalog with filters
- `GET /api/v1/companies/{inn}` — full company card (EGRUL + financials + SRO + arbitration)
- `GET /api/v1/companies/{inn}/tenders` — company's tenders

### Requests (Subcontract)
- `GET /api/v1/requests` — list subcontract requests
- `POST /api/v1/requests` — create new request (free)

### Sources
- `GET /api/v1/sources` — connected platforms with stats
- `GET /api/v1/sources/{id}/logs` — parse logs

### OKVED
- `GET /api/v1/okved/tree` — hierarchical OKVED tree
- `GET /api/v1/okved/search?q=` — search by code or name

### Auth
- `POST /api/v1/auth/register` — create account
- `POST /api/v1/auth/login` — get JWT token

## Parsers

| Parser      | Source                | Method    | Schedule      |
|------------|----------------------|-----------|---------------|
| EIS        | zakupki.gov.ru       | FTP XML   | Every 2 hours |
| RTS        | rts-tender.ru        | Scrapy    | Twice daily    |
| Corporate  | Rosneft, Gazprom     | Scrapy    | Daily          |
| Subcontract| vsem-podryad.ru      | Scrapy    | Daily          |
| EGRUL      | egrul.nalog.ru       | HTTP API  | Weekly         |

## Run manually

```bash
# Parse EIS now
docker compose exec celery_worker celery -A app.celery_app call app.tasks.parse_tasks.parse_eis

# Sync to Meilisearch
docker compose exec celery_worker celery -A app.celery_app call app.tasks.index_tasks.sync_meilisearch

# Enrich companies from EGRUL
docker compose exec celery_worker celery -A app.celery_app call app.tasks.enrich_tasks.enrich_companies_egrul
```

## Project Structure

```
tender-platform/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── init.sql                 # DB schema + seed data
│   └── app/
│       ├── main.py              # FastAPI app
│       ├── config.py            # Settings
│       ├── celery_app.py        # Celery + Beat schedule
│       ├── models/
│       │   ├── database.py      # SQLAlchemy ORM (12 tables)
│       │   └── session.py       # Async DB session
│       ├── api/
│       │   ├── tenders.py       # Tender endpoints
│       │   ├── companies.py     # Company endpoints
│       │   ├── requests.py      # Subcontract endpoints
│       │   ├── sources.py       # Platform sources
│       │   ├── okved.py         # OKVED tree/search
│       │   └── auth.py          # JWT auth
│       ├── schemas/
│       │   └── models.py        # Pydantic models
│       ├── services/
│       │   └── search.py        # Meilisearch service
│       ├── parsers/
│       │   └── eis_parser.py    # EIS FTP XML parser
│       └── tasks/
│           ├── parse_tasks.py   # Celery parse tasks
│           ├── index_tasks.py   # Meilisearch sync
│           └── enrich_tasks.py  # EGRUL enrichment
```
