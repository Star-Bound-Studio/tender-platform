"""
Meilisearch Search Service
Provides instant search (<20ms) with facets, filters, typo-tolerance
Used by API endpoints for /search queries
"""

import logging
from typing import Optional
from decimal import Decimal

import meilisearch
from app.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """Wrapper around Meilisearch for platform search."""

    def __init__(self):
        self.client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_KEY)

    def search_tenders(
        self,
        q: str = "",
        source_id: Optional[str] = None,
        law_type: Optional[str] = None,
        region: Optional[str] = None,
        okved: Optional[str] = None,
        nmck_min: Optional[float] = None,
        nmck_max: Optional[float] = None,
        status: str = "active",
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "publish_date_ts:desc",
    ) -> dict:
        """
        Search tenders via Meilisearch.
        Returns results with facet distribution (source counts).
        """
        filters = []
        if status:
            filters.append(f'status = "{status}"')
        if source_id:
            filters.append(f'source_id = "{source_id}"')
        if law_type:
            filters.append(f'law_type = "{law_type}"')
        if region:
            filters.append(f'region = "{region}"')
        if okved:
            filters.append(f'okved_codes = "{okved}"')
        if nmck_min is not None:
            filters.append(f"nmck >= {nmck_min}")
        if nmck_max is not None:
            filters.append(f"nmck <= {nmck_max}")

        filter_str = " AND ".join(filters) if filters else None

        try:
            result = self.client.index("tenders").search(
                q or "",
                {
                    "filter": filter_str,
                    "sort": [sort_by],
                    "limit": per_page,
                    "offset": (page - 1) * per_page,
                    "facets": ["source_id", "law_type", "region"],
                    "attributesToHighlight": ["title"],
                    "highlightPreTag": "<mark>",
                    "highlightPostTag": "</mark>",
                },
            )

            return {
                "total": result.get("estimatedTotalHits", 0),
                "processing_time_ms": result.get("processingTimeMs", 0),
                "hits": result.get("hits", []),
                "facets": result.get("facetDistribution", {}),
                "page": page,
                "per_page": per_page,
            }

        except Exception as e:
            logger.error(f"Meilisearch search error: {e}")
            return {"total": 0, "hits": [], "facets": {}, "error": str(e)}

    def search_companies(
        self,
        q: str = "",
        okved: Optional[str] = None,
        region: Optional[str] = None,
        has_sro: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Search companies via Meilisearch."""
        filters = ['status = "active"']
        if okved:
            filters.append(f'primary_okved = "{okved}"')
        if region:
            filters.append(f'region = "{region}"')
        if has_sro is not None:
            filters.append(f"has_sro = {'true' if has_sro else 'false'}")

        filter_str = " AND ".join(filters)

        try:
            result = self.client.index("companies").search(
                q or "",
                {
                    "filter": filter_str,
                    "sort": ["tender_wins_count:desc"],
                    "limit": per_page,
                    "offset": (page - 1) * per_page,
                    "facets": ["primary_okved", "region", "has_sro"],
                },
            )
            return {
                "total": result.get("estimatedTotalHits", 0),
                "processing_time_ms": result.get("processingTimeMs", 0),
                "hits": result.get("hits", []),
                "facets": result.get("facetDistribution", {}),
            }
        except Exception as e:
            logger.error(f"Company search error: {e}")
            return {"total": 0, "hits": [], "facets": {}}

    def search_requests(
        self,
        q: str = "",
        region: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Search subcontract requests."""
        filters = ['status = "active"']
        if region:
            filters.append(f'region = "{region}"')
        if category:
            filters.append(f'category = "{category}"')

        try:
            result = self.client.index("requests").search(
                q or "",
                {
                    "filter": " AND ".join(filters),
                    "sort": ["created_at_ts:desc"],
                    "limit": per_page,
                    "offset": (page - 1) * per_page,
                },
            )
            return {
                "total": result.get("estimatedTotalHits", 0),
                "hits": result.get("hits", []),
            }
        except Exception as e:
            logger.error(f"Request search error: {e}")
            return {"total": 0, "hits": []}


# Singleton
search_service = SearchService()
