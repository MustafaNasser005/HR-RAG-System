import json
import logging
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

from app.core.config import settings
from app.utils.email_generator import generate_recruitment_email

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_password = settings.HR_SMTP_GMAIL
        self.base_dir = Path(settings.CONTENT_DIR)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _find_candidate_data(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        Locate the cached candidate JSON by ``candidate_id`` (= content_hash).

        Cache files are written as ``{content_hash}.json`` inside each
        category's ``cache/`` folder.
        """
        if not candidate_id:
            logger.error("_find_candidate_data called with empty candidate_id")
            return None

        for category_path in self.base_dir.iterdir():
            if not category_path.is_dir():
                continue
            cache_file = category_path / "cache" / f"{candidate_id}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    logger.info(
                        f"Found candidate data for {candidate_id[:8]}… "
                        f"in category '{category_path.name}'"
                    )
                    return data
                except Exception as e:
                    logger.error(f"Error reading cache file {cache_file}: {e}")

        logger.error(
            f"No cache file found for candidate_id={candidate_id!r}. "
            f"Searched under {self.base_dir}"
        )
        return None

    def _resolve_recipient_email(self, candidate_data: Dict[str, Any]) -> Optional[str]:
        """Pull the candidate e-mail from wherever it may be stored."""
        email = (
            candidate_data.get("metadata", {}).get("email")
            or candidate_data.get("profile", {}).get("email")
            or candidate_data.get("email")
        )
        if not email or email.strip().lower() in ("not provided", "none", ""):
            return None
        return email.strip()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate_email(
        self,
        candidate_id: str,
        job_description: str,
        company_name: str,
        sender_role: str,
    ) -> str:
        """Generate a recruitment email HTML string for a candidate."""
        candidate_data = self._find_candidate_data(candidate_id)
        if not candidate_data:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found in cache")

        return generate_recruitment_email(
            candidate_data, job_description, company_name, sender_role
        )

    def send_email(
        self,
        candidate_id: str,
        job_description: str,
        company_name: str,
        sender_role: str,
    ) -> bool:
        """Generate and send a recruitment email to a candidate."""
        try:
            candidate_data = self._find_candidate_data(candidate_id)
            if not candidate_data:
                logger.error(f"Candidate with ID '{candidate_id}' not found")
                return False

            recipient_email = self._resolve_recipient_email(candidate_data)
            if not recipient_email:
                logger.error(
                    f"No valid e-mail address for candidate '{candidate_id}'"
                )
                return False

            email_content = generate_recruitment_email(
                candidate_data, job_description, company_name, sender_role
            )

            msg = MIMEMultipart("alternative")
            msg["From"]    = settings.EMAIL_FROM
            msg["To"]      = recipient_email
            msg["Subject"] = f"Exciting opportunity at {company_name}"
            msg.attach(MIMEText(email_content, "html"))

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.EMAIL_FROM, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {recipient_email} (candidate {candidate_id[:8]}…)")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to candidate '{candidate_id}': {e}")
            return False


email_service = EmailService()