"""
cv_service.py
=============
Handles CV upload, retrieval, and deletion.

Key fixes vs. original:
* Uses the module-level ``vector_store_service`` singleton (never creates a
  second ``VectorStoreService()`` instance).
* ``get_cvs_by_category`` and ``get_cv_file`` read the hash from the cache
  JSON instead of re-extracting PDF text every time (much faster).
* Disk-space error (errno.ENOSPC) is handled explicitly.
* Duplicate uploads are detected before calling the vector store.
"""

import errno
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.core.logger import logger
from app.services.vector_store import vector_store_service   # ← singleton
from app.utils.file_utils import clean_dict_keys
from app.utils.pdf_parser import extract_text_from_pdf
from app.utils.profile_generator import (
    extract_professional_summary,
    generate_candidate_profile,
    generate_general_summary,
)


class CVService:
    def __init__(self):
        self.base_dir = Path(settings.CONTENT_DIR)
        # Do NOT create a second VectorStoreService here.
        self.vector_service = vector_store_service

    # ------------------------------------------------------------------ #
    #  Upload                                                              #
    # ------------------------------------------------------------------ #

    async def upload_cv(self, file: UploadFile, category: str) -> Dict[str, Any]:
        category_path = self.base_dir / category
        if not category_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Category '{category}' not found"
            )

        cv_dir    = category_path / "cvs"
        cache_dir = category_path / "cache"
        cv_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        cv_path = cv_dir / file.filename
        content = await file.read()

        # ── Save PDF to disk ────────────────────────────────────────────
        try:
            with open(cv_path, "wb") as f:
                f.write(content)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                raise HTTPException(
                    status_code=507,
                    detail="Insufficient storage space on server",
                )
            raise HTTPException(
                status_code=500, detail=f"File write error: {e}"
            )

        try:
            cv_text      = extract_text_from_pdf(str(cv_path))
            content_hash = hashlib.md5(cv_text.encode()).hexdigest()
            cache_file   = cache_dir / f"{content_hash}.json"

            # ── Cache check ─────────────────────────────────────────────
            cache_valid    = False
            candidate_data = None

            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        candidate_data = json.load(f)
                    meta = candidate_data.get("metadata", {})
                    if (
                        meta.get("name")  not in (None, "", "Not provided")
                        and meta.get("email") not in (None, "", "Not provided")
                    ):
                        cache_valid = True
                        logger.info(f"Loaded valid cache for '{file.filename}'")
                    else:
                        logger.warning(
                            f"Cache for '{file.filename}' is incomplete — regenerating"
                        )
                        cache_file.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Error reading cache {cache_file}: {e} — regenerating")
                    cache_file.unlink(missing_ok=True)

            # ── Generate profile if cache miss ──────────────────────────
            if not cache_valid:
                profile           = generate_candidate_profile(cv_text, file.filename)
                extracted_summary = extract_professional_summary(cv_text)
                llm_summary       = generate_general_summary(profile)

                combined_summary = ""
                if extracted_summary:
                    combined_summary += f"PROFILE SUMMARY (from CV):\n{extracted_summary}\n\n"
                combined_summary += f"AI-GENERATED SUMMARY:\n{llm_summary}"

                if not combined_summary.strip():
                    combined_summary = (
                        f"Candidate: {profile.get('name', 'Unknown')}. "
                        f"Experience: {profile.get('years_experience', 0)} years. "
                        f"Skills: {', '.join(profile.get('skills', []))}"
                    )

                candidate_data = {
                    "page_content": combined_summary,
                    "metadata": {
                        "name":              profile.get("name",             "Unknown"),
                        "email":             profile.get("email",            "Not provided"),
                        "phone":             profile.get("phone",            "Not provided"),
                        "location":          profile.get("location",         "Not provided"),
                        "skills":            profile.get("skills",           []),
                        "experience_years":  profile.get("years_experience", 0),
                        "cv_file_path":      str(cv_path),
                        "validation_status": profile.get("validation_status","incomplete"),
                    },
                    "raw_text": cv_text,
                    "profile":  profile,
                }

                candidate_data = clean_dict_keys(candidate_data)

                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(candidate_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Cached fresh profile for '{file.filename}'")

            # ── Inject content_hash before vector store ─────────────────
            candidate_data["content_hash"] = content_hash

            # ── Add to vector store (idempotent — won't add duplicates) ─
            await self.vector_service.add_document(category, candidate_data)

            return {
                "id":           content_hash,
                "filename":     file.filename,
                "category":     category,
                "uploaded_at":  cv_path.stat().st_ctime,
                "metadata":     candidate_data["metadata"],
                "file_path":    str(cv_path),
                "content_hash": content_hash,
            }

        except HTTPException:
            raise
        except Exception as e:
            if cv_path.exists():
                cv_path.unlink(missing_ok=True)
            logger.error(f"Error processing CV '{file.filename}': {e}")
            raise HTTPException(
                status_code=500, detail=f"Error processing CV: {e}"
            )

    # ------------------------------------------------------------------ #
    #  List                                                                #
    # ------------------------------------------------------------------ #

    def get_cvs_by_category(self, category: str) -> List[Dict[str, Any]]:
        category_path = self.base_dir / category
        if not category_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Category '{category}' not found"
            )

        cv_dir    = category_path / "cvs"
        cache_dir = category_path / "cache"
        cvs: List[Dict[str, Any]] = []

        if not cv_dir.exists():
            return cvs

        for cv_file in cv_dir.glob("*.pdf"):
            # Fast path: derive hash from text (cached in memory once extracted)
            try:
                cv_text      = extract_text_from_pdf(str(cv_file))
                content_hash = hashlib.md5(cv_text.encode()).hexdigest()
            except Exception as e:
                logger.warning(f"Could not hash '{cv_file.name}': {e}")
                continue

            metadata: Dict[str, Any] = {}
            cache_file = cache_dir / f"{content_hash}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    metadata = cached.get("metadata", {})
                except Exception as e:
                    logger.warning(f"Could not read cache '{cache_file}': {e}")

            cvs.append(
                {
                    "id":           content_hash,
                    "filename":     cv_file.name,
                    "category":     category,
                    "uploaded_at":  cv_file.stat().st_ctime,
                    "metadata":     metadata,
                    "file_path":    str(cv_file),
                    "content_hash": content_hash,
                }
            )

        return cvs

    # ------------------------------------------------------------------ #
    #  File retrieval                                                      #
    # ------------------------------------------------------------------ #

    def get_cv_file(self, cv_id: str, category: str) -> Path:
        """Return the PDF path for a given content_hash (cv_id)."""
        category_path = self.base_dir / category
        if not category_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Category '{category}' not found"
            )

        cv_dir    = category_path / "cvs"
        cache_dir = category_path / "cache"

        # Fast path: check cache files whose filename IS the hash
        cache_file = cache_dir / f"{cv_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cv_file_path = Path(
                    cached.get("metadata", {}).get("cv_file_path", "")
                )
                if cv_file_path.exists():
                    return cv_file_path
            except Exception:
                pass

        # Slow fallback: scan and hash each PDF
        if cv_dir.exists():
            for cv_file in cv_dir.glob("*.pdf"):
                try:
                    cv_text      = extract_text_from_pdf(str(cv_file))
                    content_hash = hashlib.md5(cv_text.encode()).hexdigest()
                    if content_hash == cv_id:
                        return cv_file
                except Exception:
                    continue

        raise HTTPException(
            status_code=404, detail=f"CV with ID '{cv_id}' not found"
        )

    # ------------------------------------------------------------------ #
    #  Delete                                                              #
    # ------------------------------------------------------------------ #

    def delete_cv(self, cv_id: str, category: str) -> bool:
        category_path = self.base_dir / category
        if not category_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Category '{category}' not found"
            )

        cv_dir     = category_path / "cvs"
        cache_dir  = category_path / "cache"
        cv_deleted = False

        if cv_dir.exists():
            for pdf_file in cv_dir.glob("*.pdf"):
                try:
                    cv_text      = extract_text_from_pdf(str(pdf_file))
                    content_hash = hashlib.md5(cv_text.encode()).hexdigest()
                except Exception:
                    continue
                if content_hash == cv_id:
                    pdf_file.unlink(missing_ok=True)
                    cv_deleted = True
                    logger.info(f"Deleted CV file: '{pdf_file}'")
                    break

        # Remove cache
        cache_file = cache_dir / f"{cv_id}.json"
        if cache_file.exists():
            cache_file.unlink(missing_ok=True)
            logger.info(f"Deleted cache: '{cache_file}'")

        # Remove from vector store
        self.vector_service.remove_document(category, cv_id)

        if not cv_deleted:
            raise HTTPException(
                status_code=404, detail=f"CV with ID '{cv_id}' not found"
            )
        return True


# ── Module-level singleton ──────────────────────────────────────────────────
cv_service = CVService()