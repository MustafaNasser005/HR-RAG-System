import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from app.core.config import settings
from app.services.vector_store import vector_store_service

logger = logging.getLogger(__name__)

class CategoryService:
    def __init__(self):
        self.base_dir = Path(settings.CONTENT_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _is_valid_category_dir(self, path: Path) -> bool:
        """Check if directory is a valid category (not a system folder)"""
        name = path.name
        # Skip system / hidden folders
        if name.startswith('.') or name in ['logs', '__pycache__', 'cache', 'indices']:
            return False
        # Accept if it has a 'cvs' subdirectory (created by the app)
        return (path / "cvs").exists()
    
    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Get all valid categories (exclude system folders)"""
        categories = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and self._is_valid_category_dir(item):
                cv_count = len(list((item / "cvs").glob("*.pdf"))) if (item / "cvs").exists() else 0
                created_at = datetime.fromtimestamp(item.stat().st_ctime).isoformat()
                categories.append({
                    "id": item.name,
                    "name": item.name,
                    "description": f"Category for {item.name} CVs",
                    "cv_count": cv_count,
                    "created_at": created_at
                })
        return sorted(categories, key=lambda x: x["name"])
    
    def create_category(self, category_name: str) -> Dict[str, Any]:
        """Create a new category directory and initialize vector store"""
        category_path = self.base_dir / category_name
        if category_path.exists():
            raise ValueError(f"Category '{category_name}' already exists")
        
        # Create category structure
        (category_path / "cvs").mkdir(parents=True)
        (category_path / "cache").mkdir(parents=True)
        (category_path / "indices").mkdir(parents=True)
        
        # Initialize empty vector store indices for this category
        vector_store_service.ensure_category_index(category_name)
        
        logger.info(f"Created category: {category_name}")
        return {
            "id": category_name,
            "name": category_name,
            "description": f"Category for {category_name} CVs",
            "cv_count": 0,
            "created_at": datetime.now().isoformat()
        }

category_service = CategoryService()