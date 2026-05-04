"""
search_service.py
=================
Thin orchestration layer: calls vector_store → optional LLM reranker → trims.

Deduplication is handled inside ``vector_store.search()`` so we do NOT repeat
it here.  We still over-fetch to give the reranker more candidates to work with.
"""

import logging
from typing import Any, Dict, List

from app.services.vector_store import vector_store_service
from app.utils.reranker import rerank_candidates

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self.vector_service = vector_store_service   # singleton

    def hybrid_search(
        self,
        category: str,
        job_description: str,
        top_n: int = 5,
        rerank: bool = False,
    ) -> List[Dict[str, Any]]:
        if not category or not job_description.strip():
            logger.warning("Empty category or job description")
            return []

        # Over-fetch only when reranking (gives LLM more context)
        fetch_count = top_n * 3 if rerank else top_n

        try:
            self.vector_service.ensure_category_index(category)
        except ValueError as e:
            logger.error(f"Category error: {e}")
            raise

        results = self.vector_service.search(category, job_description, fetch_count)
        if not results:
            logger.info(f"No results for category '{category}'")
            return []

        logger.info(f"Retrieved {len(results)} candidates from vector store")

        if rerank and len(results) > 1:
            try:
                logger.info("Applying LLM reranking…")
                results = rerank_candidates(results, job_description)
            except Exception as e:
                logger.error(f"Reranking failed — using original order: {e}")

        final = results[:top_n]
        # Re-number ranks after reranking / trim
        for i, r in enumerate(final, 1):
            r["rank"] = i

        return final


search_service = SearchService()