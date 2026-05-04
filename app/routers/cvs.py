from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from app.services.cv_service import cv_service
from app.models.schemas import CV

router = APIRouter()

@router.post("/upload", response_model=CV)
async def upload_cv(file: UploadFile = File(...), category: str = Form(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    try:
        return await cv_service.upload_cv(file, category)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading CV: {str(e)}")

@router.get("/", response_model=list[CV])
async def get_cvs(category: str):
    try:
        return cv_service.get_cvs_by_category(category)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving CVs: {str(e)}")

@router.get("/{cv_id}/preview", response_class=FileResponse)
async def preview_cv(cv_id: str, category: str = Query(...)):
    try:
        cv_file = cv_service.get_cv_file(cv_id, category)
        return FileResponse(cv_file, media_type="application/pdf", filename=cv_file.name)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving CV: {str(e)}")

@router.delete("/{cv_id}")
async def delete_cv(cv_id: str, category: str):
    try:
        success = cv_service.delete_cv(cv_id, category)
        if success:
            return {"message": f"CV {cv_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"CV {cv_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting CV: {str(e)}")