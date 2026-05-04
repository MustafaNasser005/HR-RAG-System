from fastapi import APIRouter, HTTPException
from app.services.search_service import search_service
from app.services.category_service import category_service
from app.models.schemas import SearchQuery, SearchResult

router = APIRouter()   # ✅ required for FastAPI to detect routes

@router.post("/", response_model=list[SearchResult])
async def search_candidates(query: SearchQuery):
    try:
        # Validate category exists
        categories = [c["name"] for c in category_service.get_all_categories()]
        if query.category not in categories:
            raise HTTPException(status_code=404, detail=f"Category '{query.category}' not found")

        results = search_service.hybrid_search(
            category=query.category,
            job_description=query.job_description,
            top_n=query.top_n,
            rerank=query.rerank
        )
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")