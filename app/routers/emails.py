from fastapi import APIRouter, HTTPException
from app.services.email_service import email_service
from app.models.schemas import EmailRequest, EmailResponse

router = APIRouter()

@router.post("/generate", response_model=EmailResponse)
async def generate_email(request: EmailRequest):
    """Generate a recruitment email for a candidate"""
    try:
        email_content = email_service.generate_email(
            candidate_id=request.candidate_id,
            job_description=request.job_description,
            company_name=request.company_name,
            sender_role=request.sender_role
        )
        return EmailResponse(
            success=True,
            message="Email generated successfully",
            email_content=email_content
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation error: {str(e)}")

@router.post("/send")
async def send_email(request: EmailRequest):
    """Send a recruitment email to a candidate"""
    try:
        success = email_service.send_email(
            candidate_id=request.candidate_id,
            job_description=request.job_description,
            company_name=request.company_name,
            sender_role=request.sender_role
        )
        if success:
            return {"message": "Email sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending error: {str(e)}")