"""
Tender Platform — Celery Configuration
Task queue for parsing, indexing, and background jobs
"""

from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "tender_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.parse_tasks",
        "app.tasks.index_tasks",
        "app.tasks.enrich_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# ============================================================
# BEAT SCHEDULE — Periodic tasks
# ============================================================
celery_app.conf.beat_schedule = {
    # ЕИС — every 2 hours (main source)
    "parse-eis-every-2h": {
        "task": "app.tasks.parse_tasks.parse_eis",
        "schedule": crontab(minute=0, hour="*/2"),  # 00:00, 02:00, 04:00, ...
        "args": [],
    },

    # РТС-тендер — twice daily
    "parse-rts-morning": {
        "task": "app.tasks.parse_tasks.parse_rts",
        "schedule": crontab(minute=30, hour=7),
    },
    "parse-rts-evening": {
        "task": "app.tasks.parse_tasks.parse_rts",
        "schedule": crontab(minute=30, hour=19),
    },

    # Корпоративные (Роснефть, Газпром) — daily at night
    "parse-corporate-daily": {
        "task": "app.tasks.parse_tasks.parse_corporate",
        "schedule": crontab(minute=0, hour=3),
    },

    # Всем Подряд (субподряды) — daily
    "parse-subcontracts-daily": {
        "task": "app.tasks.parse_tasks.parse_subcontracts",
        "schedule": crontab(minute=0, hour=5),
    },

    # Meilisearch reindex — every 30 min
    "reindex-meilisearch": {
        "task": "app.tasks.index_tasks.sync_meilisearch",
        "schedule": crontab(minute="*/30"),
    },

    # Update source stats — hourly
    "update-source-stats": {
        "task": "app.tasks.index_tasks.update_source_stats",
        "schedule": crontab(minute=15, hour="*"),
    },

    # EGRUL enrichment — weekly (Sunday night)
    "enrich-egrul-weekly": {
        "task": "app.tasks.enrich_tasks.enrich_companies_egrul",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),
    },
}
