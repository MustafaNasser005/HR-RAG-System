from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CategoryBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: str
    created_at: datetime
    cv_count: int = 0
    class Config:
        from_attributes = True

class CVBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    filename: str
    category: str

class CVCreate(CVBase):
    pass

class CV(CVBase):
    id: str
    uploaded_at: datetime
    metadata: Dict[str, Any]
    file_path: str
    content_hash: str
    class Config:
        from_attributes = True

class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    years_experience: Optional[int] = None
    skills: List[str] = []
    education: List[str] = []
    key_projects: List[str] = []
    validation_status: str

class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_description: str
    category: str
    top_n: int = 5
    rerank: bool = False

class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rank: int
    name: str
    email: str
    phone: Optional[str] = None
    similarity_score: float
    semantic_score: float
    keyword_score: float
    summary: str
    validation_status: str
    candidate_id: str   # <-- ADDED: needed for email generation

class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidate_id: str
    job_description: str
    company_name: str = "Your Company"
    sender_role: str = "HR Manager"

class EmailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    message: str
    email_content: Optional[str] = None