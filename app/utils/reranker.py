import json
import logging
from typing import List, Dict
from app.core.config import settings
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

def rerank_candidates(candidates: List[Dict], job_description: str) -> List[Dict]:
    """
    Re-rank candidates using LLM for nuanced contextual matching.
    Deduplicates candidates to prevent repeated entries.
    """
    if not candidates or len(candidates) <= 1:
        return candidates

    try:
        client = ChatOpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0
        )

        candidate_list_str = "\n".join([
            f"{i+1}. Name: {c.get('name', 'Unknown')} | Summary: {c.get('summary', '')[:300]}..."
            for i, c in enumerate(candidates)
        ])

        prompt_template = PromptTemplate(
            input_variables=["candidates", "job_description"],
            template="""You are an HR expert. Re-rank these candidates from best fit to worst fit for the given job description based on skills, experience, and relevance.

Job Description:
{job_description}

Candidates:
{candidates}

Return ONLY a JSON array of candidate indices (1-based) in best-to-worst order."""
        )

        formatted_prompt = prompt_template.format(
            candidates=candidate_list_str,
            job_description=job_description
        )

        response = client.invoke(formatted_prompt)
        output_text = getattr(response, 'content', str(response)).strip()

        start_idx = output_text.find('[')
        end_idx = output_text.rfind(']') + 1
        if start_idx == -1 or end_idx == 0:
            logger.warning("No JSON array found in LLM response")
            return list({c['name']: c for c in candidates}.values())  # deduplicate

        json_str = output_text[start_idx:end_idx]
        ranked_indices = json.loads(json_str)

        # Deduplicate and reorder
        if isinstance(ranked_indices, list):
            seen = set()
            reordered = []
            for idx in ranked_indices:
                if 1 <= idx <= len(candidates) and idx not in seen:
                    reordered.append(candidates[idx - 1])
                    seen.add(idx)
            # Add remaining candidates that LLM did not include
            for i, c in enumerate(candidates):
                if (i + 1) not in seen:
                    reordered.append(c)
            return reordered
        else:
            return list({c['name']: c for c in candidates}.values())  # fallback deduplicate

    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return list({c['name']: c for c in candidates}.values())  # fallback deduplicate
