from fastapi import APIRouter, HTTPException
from app.services.category_service import category_service
from app.models.schemas import Category, CategoryCreate

router = APIRouter()

@router.get("/", response_model=list[Category])
async def get_categories():
    """Get all categories"""
    return category_service.get_all_categories()

@router.post("/", response_model=Category)
async def create_category(category: CategoryCreate):
    """Create a new category"""
    try:
        return category_service.create_category(category.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating category: {str(e)}")