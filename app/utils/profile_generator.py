import re
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
from app.utils.file_utils import clean_dict_keys
from app.core.logger import logger

def _extract_name_from_text(text: str) -> str:
    lines = text.split('\n')
    for line in lines[:10]:
        line = line.strip()
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line):
            return line
        if line.lower().startswith('name:'):
            return line.split(':', 1)[1].strip()
    return "Not provided"

def _extract_email_from_text(text: str) -> str:
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else "Not provided"

def _extract_years_experience_from_text(text: str) -> int:
    # Look for patterns like "5 years of experience", "5+ years", "5 yrs"
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s+of\s+experience',
        r'(\d+)\+?\s*(?:years?|yrs?)\s+experience',
        r'experience\s*:?\s*(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0

def generate_candidate_profile(cv_text: str, cv_filename: str) -> Dict[str, Any]:
    logger.info(f"Generating profile for {cv_filename}")

    clean_text = re.sub(r'\s+', ' ', cv_text).strip()
    if len(clean_text) > 7000:
        clean_text = clean_text[:7000]

    client = OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY
    )

    prompt = f"""
You are an expert ATS parser.
Extract candidate details from the following CV text and return in valid JSON format.
Include only these fields: name, email, phone, location, years_experience, skills, education, key_projects, validation_status.

IMPORTANT: 
- Do not include any field names that start with underscore (_). 
- years_experience should be an integer (number of years of professional experience).
- skills should be a list of strings (e.g., ["Python", "Machine Learning"]).
- If a field is not found, use null or empty list for skills/education/projects.

CV Text:
{clean_text}

Return ONLY valid JSON. Example:
{{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "location": "New York, USA",
    "years_experience": 5,
    "skills": ["Python", "Machine Learning"],
    "education": ["Bachelor Computer Science"],
    "key_projects": ["AI chatbot development"],
    "validation_status": "complete"
}}
"""

    # Fallback with regex extractions
    fallback_name = _extract_name_from_text(cv_text)
    fallback_email = _extract_email_from_text(cv_text)
    fallback_exp = _extract_years_experience_from_text(cv_text)
    
    fallback = {
        "name": fallback_name,
        "email": fallback_email,
        "phone": "Not provided",
        "location": "Not provided",
        "years_experience": fallback_exp,
        "skills": [],
        "education": [],
        "key_projects": [],
        "validation_status": "incomplete",
        "cv_filename": cv_filename
    }

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert ATS parser. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content)
        result = {k: v for k, v in result.items() if not k.startswith('_')}
        result = clean_dict_keys(result)

        expected_fields = {"name", "email", "phone", "location", "years_experience",
                           "skills", "education", "key_projects", "validation_status"}
        filtered = {}
        for field in expected_fields:
            value = result.get(field, fallback.get(field))
            if field in ["skills", "education", "key_projects"] and not isinstance(value, list):
                value = []
            filtered[field] = value

        # Override with regex if LLM gave nothing
        if filtered.get("name") in [None, "", "Not provided"]:
            filtered["name"] = fallback_name
        if filtered.get("email") in [None, "", "Not provided"]:
            filtered["email"] = fallback_email
        if filtered.get("years_experience") in [None, 0]:
            filtered["years_experience"] = fallback_exp

        filtered["cv_filename"] = cv_filename
        if filtered.get("name") not in [None, "", "Not provided"] and filtered.get("email") not in [None, "", "Not provided"]:
            filtered["validation_status"] = "complete"
        else:
            filtered["validation_status"] = "incomplete"

        logger.info(f"Profile generated for {cv_filename}: name={filtered['name']}, email={filtered['email']}, exp={filtered['years_experience']}, skills={len(filtered['skills'])}")
        return filtered

    except Exception as e:
        logger.error(f"Profile generation failed for {cv_filename}: {e}, using fallback")
        return fallback

def generate_general_summary(profile: Dict[str, Any]) -> str:
    name = profile.get("name", "Unknown")
    exp = profile.get("years_experience", 0)
    skills = profile.get("skills", [])
    if not skills:
        skills = ["various skills"]
    skills_str = ", ".join(skills[:5])
    fallback = f"{name} has {exp} years of experience in {skills_str}."
    
    safe_profile = clean_dict_keys(profile)
    safe_json = json.dumps(safe_profile, ensure_ascii=False, indent=2)
    client = OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=settings.OPENROUTER_API_KEY)
    prompt = f"Write a neutral professional summary (120-180 words) based only on this profile:\n{safe_json}"
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=30
        )
        summary = resp.choices[0].message.content.strip()
        return summary if summary else fallback
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return fallback

def extract_professional_summary(cv_text: str) -> Optional[str]:
    pattern = r"(?:Professional Summary|Summary|Profile)\s*(.*?)(?=\n(?:Skills|Experience|Education|Projects|\w+\s*:\s*)|\Z)"
    match = re.search(pattern, cv_text, flags=re.I | re.S)
    return match.group(1).strip() if match else None