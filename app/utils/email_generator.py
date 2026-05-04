from typing import Dict, Any
from app.core.config import settings
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


def generate_recruitment_email(
    candidate: Dict[str, Any],
    job_description: str,
    company_name: str = "Your Company",
    sender_role: str = "HR Manager",
) -> str:
    """
    Generate a personalised recruitment email.

    The *candidate* dict is the raw cache JSON, which has this shape::

        {
            "page_content": "...",        # AI-generated summary
            "metadata": {
                "name": "...",
                "email": "...",
                "skills": [...],
                "experience_years": 5,
                ...
            },
            "profile": {                  # raw LLM-parsed profile (may be absent)
                "name": "...",
                "skills": [...],
                ...
            },
            "raw_text": "..."
        }

    We prefer ``metadata`` (always present) and fall back to ``profile``
    then to top-level keys for backwards compatibility.
    """

    metadata = candidate.get("metadata") or {}
    profile   = candidate.get("profile")  or {}

    # ── Candidate fields ────────────────────────────────────────────────
    name = (
        metadata.get("name")
        or profile.get("name")
        or candidate.get("name")
        or "Candidate"
    )

    skills_raw = (
        metadata.get("skills")
        or profile.get("skills")
        or []
    )
    skills = ", ".join(skills_raw) if skills_raw else "various skills"

    experience = (
        metadata.get("experience_years")
        or metadata.get("years_experience")
        or profile.get("years_experience")
        or candidate.get("experience_years")
        or 0
    )

    # Use the combined AI summary stored in page_content; fall back to profile summary
    summary = (
        candidate.get("page_content")
        or candidate.get("summary")
        or f"{name} – {experience} years of experience in {skills}."
    )
    # Trim to keep the prompt lean
    summary = summary[:600]

    # ── LLM call ────────────────────────────────────────────────────────
    client = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.6,
    )

    prompt = PromptTemplate(
        input_variables=[
            "name", "skills", "experience", "summary",
            "job_description", "sender_role", "company_name",
        ],
        template="""
Write a short, professional, and friendly recruitment email in **HTML format** to the candidate below.

Candidate Information:
- Name: {name}
- Key Skills: {skills}
- Experience: {experience} years
- Profile Summary: {summary}

Job Description:
{job_description}

Instructions:
- Use <p> tags for paragraphs and <br> for line breaks where needed.
- Greet the candidate by name in the first paragraph.
- Mention at least one specific match between their skills/experience and the job.
- Invite them to the next step (interview or call).
- Keep it warm, polite, and professional — 2-3 short paragraphs.
- Do NOT include any personal email addresses in the body.
- End with a professional signature:
  <p>Best regards,<br><b>{sender_role}</b><br>{company_name}</p>
""",
    )

    chain = prompt | client
    try:
        result = chain.invoke(
            {
                "name": name,
                "skills": skills,
                "experience": experience,
                "summary": summary,
                "job_description": job_description,
                "company_name": company_name,
                "sender_role": sender_role,
            }
        )
        return result.content.strip()
    except Exception as e:
        print(f"⚠️  Email generation failed: {e}")
        return (
            f"<p>Dear {name},</p>"
            f"<p>Thank you for your interest. We will be in touch shortly.</p>"
            f"<p>Best regards,<br><b>{sender_role}</b><br>{company_name}</p>"
        )