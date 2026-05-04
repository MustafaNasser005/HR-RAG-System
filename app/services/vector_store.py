import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from langchain.docstore.document import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self):
        self.base_dir = Path(settings.CONTENT_DIR)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.indices: Dict[str, dict] = {}
        self._embedding_dim: Optional[int] = None
        self._load_existing_indices()

    # ------------------------------------------------------------------
    #  Embedding helpers
    # ------------------------------------------------------------------
    def _get_embedding_dimension(self) -> int:
        if self._embedding_dim is None:
            self._embedding_dim = len(self.embeddings.embed_query("test"))
        return self._embedding_dim

    def _embed(self, text: str) -> np.ndarray:
        return np.array(self.embeddings.embed_query(text), dtype="float32")

    # ------------------------------------------------------------------
    #  Ground‑truth loader: cache JSONs (always authoritative)
    # ------------------------------------------------------------------
    def _load_docs_from_cache(self, category: str) -> List[Document]:
        cache_dir = self.base_dir / category / "cache"
        docs: List[Document] = []
        if not cache_dir.exists():
            return docs

        for cache_file in sorted(cache_dir.glob("*.json")):
            content_hash = cache_file.stem  # filename = hash
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                summary = data.get("page_content", "").strip()
                if not summary:
                    logger.warning(f"Skipping {cache_file.name}: empty summary")
                    continue

                metadata = dict(data.get("metadata", {}))
                metadata["content_hash"] = content_hash  # force it

                docs.append(Document(page_content=summary, metadata=metadata))
            except Exception as e:
                logger.warning(f"Skipping corrupt cache {cache_file.name}: {e}")

        logger.info(f"Loaded {len(docs)} docs from cache for category '{category}'")
        return docs

    # ------------------------------------------------------------------
    #  Rebuild index from documents (only non‑empty summaries)
    # ------------------------------------------------------------------
    def _rebuild_index_from_documents(self, category: str, docs: List[Document]):
        dim = self._get_embedding_dimension()
        faiss_index = faiss.IndexFlatIP(dim)
        bm25_corpus: List[List[str]] = []
        valid_docs: List[Document] = []

        for doc in docs:
            text = doc.page_content.strip()
            if not text:
                continue
            # add to FAISS
            vec = self._embed(text).reshape(1, -1)
            faiss_index.add(vec)
            # add to BM25 corpus
            bm25_corpus.append(text.lower().split())
            valid_docs.append(doc)

        self.indices[category] = {
            "faiss": faiss_index,
            "bm25": BM25Okapi(bm25_corpus) if bm25_corpus else None,
            "bm25_corpus": bm25_corpus,
            "bm25_docs": valid_docs,
            "documents": valid_docs,
        }
        self._save_category_index(category)
        logger.info(
            f"Rebuilt '{category}': FAISS={faiss_index.ntotal} vectors, docs={len(valid_docs)}"
        )

    def _rebuild_from_cache(self, category: str):
        """Force a full rebuild from the JSON cache files."""
        logger.info(f"Forcing full rebuild of '{category}' from cache…")
        docs = self._load_docs_from_cache(category)
        self._rebuild_index_from_documents(category, docs)

    # ------------------------------------------------------------------
    #  Load / save indices from disk
    # ------------------------------------------------------------------
    def _load_existing_indices(self):
        if not self.base_dir.exists():
            return
        for p in self.base_dir.iterdir():
            if p.is_dir() and not p.name.startswith(".") and (p / "indices").exists():
                self._load_category_index(p.name)

    def _load_category_index(self, category: str):
        indices_path = self.base_dir / category / "indices"
        dim = self._get_embedding_dimension()

        # Read on‑disk FAISS and BM25 data
        faiss_index = faiss.IndexFlatIP(dim)
        bm25_docs: List[Document] = []
        bm25_corpus: List[List[str]] = []

        faiss_file = indices_path / "faiss.index"
        bm25_file = indices_path / "bm25.json"

        if faiss_file.exists():
            try:
                faiss_index = faiss.read_index(str(faiss_file))
                logger.info(f"Loaded FAISS for '{category}' with {faiss_index.ntotal} vectors")
            except Exception as e:
                logger.warning(f"Failed to load FAISS for '{category}': {e}")

        if bm25_file.exists():
            try:
                with open(bm25_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                bm25_corpus = data.get("corpus", [])
                bm25_docs = [Document(**d) for d in data.get("docs", [])]
                logger.info(f"Loaded BM25 for '{category}' with {len(bm25_docs)} docs")
            except Exception as e:
                logger.warning(f"Failed to load BM25 for '{category}': {e}")

        # --- Consistency checks -------------------------------------------------
        need_rebuild = False
        if faiss_index.ntotal != len(bm25_docs):
            logger.warning(
                f"[{category}] FAISS count ({faiss_index.ntotal}) != BM25 docs ({len(bm25_docs)})"
            )
            need_rebuild = True
        elif any(not d.metadata.get("content_hash") for d in bm25_docs):
            logger.warning(f"[{category}] Some documents lack content_hash → rebuild")
            need_rebuild = True

        if need_rebuild:
            self._rebuild_from_cache(category)
            return

        # All good – store in memory
        self.indices[category] = {
            "faiss": faiss_index,
            "bm25": BM25Okapi(bm25_corpus) if bm25_corpus else None,
            "bm25_corpus": bm25_corpus,
            "bm25_docs": bm25_docs,
            "documents": bm25_docs,
        }

    def _save_category_index(self, category: str):
        if category not in self.indices:
            return
        indices_path = self.base_dir / category / "indices"
        indices_path.mkdir(exist_ok=True)
        try:
            faiss.write_index(self.indices[category]["faiss"], str(indices_path / "faiss.index"))
            with open(indices_path / "bm25.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "corpus": self.indices[category]["bm25_corpus"],
                        "docs": [
                            {"page_content": d.page_content, "metadata": d.metadata}
                            for d in self.indices[category]["bm25_docs"]
                        ],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"Saved indices for '{category}'")
        except Exception as e:
            logger.error(f"Failed to save indices for '{category}': {e}")

    # ------------------------------------------------------------------
    #  Public: ensure index exists / repair on the fly
    # ------------------------------------------------------------------
    def ensure_category_index(self, category: str):
        if category in self.indices:
            # Extra safety: check consistency and rebuild if needed
            idx = self.indices[category]
            if idx["faiss"].ntotal != len(idx["documents"]):
                logger.warning(f"Inconsistent index in memory for '{category}' – rebuilding")
                self._rebuild_from_cache(category)
            return

        category_path = self.base_dir / category
        if not category_path.exists():
            raise ValueError(f"Category '{category}' does not exist on disk")

        (category_path / "indices").mkdir(parents=True, exist_ok=True)
        self._load_category_index(category)

        if category not in self.indices:
            # Brand new empty category
            dim = self._get_embedding_dimension()
            self.indices[category] = {
                "faiss": faiss.IndexFlatIP(dim),
                "bm25": None,
                "bm25_corpus": [],
                "bm25_docs": [],
                "documents": [],
            }
        logger.info(f"Index ready for '{category}'")

    # ------------------------------------------------------------------
    #  CRUD
    # ------------------------------------------------------------------
    async def add_document(self, category: str, candidate_data: Dict[str, Any]) -> Optional[str]:
        self.ensure_category_index(category)
        idx = self.indices[category]

        summary = candidate_data.get("page_content", "").strip()
        if not summary:
            logger.warning("Empty page_content – skipping")
            return None

        metadata = dict(candidate_data.get("metadata", {}))

        content_hash = candidate_data.get("content_hash")
        if not content_hash:
            content_hash = hashlib.md5(summary.encode()).hexdigest()
            logger.warning(f"No content_hash – using fallback {content_hash[:8]}")
        metadata["content_hash"] = content_hash

        # Idempotency: skip if already present
        for existing in idx["documents"]:
            if existing.metadata.get("content_hash") == content_hash:
                logger.info(f"Document {content_hash[:8]} already in '{category}' – skip")
                return content_hash

        # Create new document
        doc = Document(page_content=summary, metadata=metadata)

        # Add to FAISS
        vec = self._embed(summary).reshape(1, -1)
        idx["faiss"].add(vec)

        # Add to BM25 structures
        tokenized = summary.lower().split()
        idx["bm25_corpus"].append(tokenized)
        idx["bm25_docs"].append(doc)
        idx["documents"].append(doc)
        idx["bm25"] = BM25Okapi(idx["bm25_corpus"])

        # Final consistency check – if mismatch, rebuild completely
        if idx["faiss"].ntotal != len(idx["documents"]):
            logger.error(
                f"Inconsistency after add: FAISS={idx['faiss'].ntotal}, docs={len(idx['documents'])}. "
                "Rebuilding from cache."
            )
            self._rebuild_from_cache(category)
        else:
            self._save_category_index(category)

        logger.info(f"Added {content_hash[:8]} to '{category}' (total docs: {len(idx['documents'])})")
        return content_hash

    def remove_document(self, category: str, doc_id: str):
        if category not in self.indices:
            return
        docs = self.indices[category]["documents"]
        new_docs = [d for d in docs if d.metadata.get("content_hash") != doc_id]
        if len(new_docs) == len(docs):
            logger.warning(f"Document {doc_id[:8]} not found in '{category}'")
            return
        self._rebuild_index_from_documents(category, new_docs)

    # ------------------------------------------------------------------
    #  Search
    # ------------------------------------------------------------------
    def search(self, category: str, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        self.ensure_category_index(category)

        idx = self.indices[category]
        documents = idx["documents"]
        if not documents or not query.strip():
            return []

        n_docs = len(documents)
        q_vec = self._embed(query).reshape(1, -1)

        # Semantic (FAISS)
        semantic_scores: Dict[int, float] = {}
        if idx["faiss"].ntotal > 0:
            k = min(idx["faiss"].ntotal, max(top_n * 3, 20))
            scores, indices = idx["faiss"].search(q_vec, k)
            for col in range(indices.shape[1]):
                i = int(indices[0][col])
                if 0 <= i < n_docs:
                    # convert cosine similarity (inner product) to [0,1]
                    semantic_scores[i] = float((scores[0][col] + 1.0) / 2.0)

        # BM25
        bm25_raw = np.zeros(n_docs, dtype="float32")
        if idx["bm25"] is not None:
            tokens = query.lower().split()
            if tokens:
                try:
                    raw = np.array(idx["bm25"].get_scores(tokens), dtype="float32")
                    usable = min(len(raw), n_docs)
                    bm25_raw[:usable] = raw[:usable]
                except Exception as e:
                    logger.warning(f"BM25 scoring failed: {e}")

        max_bm25 = float(bm25_raw.max()) if bm25_raw.max() > 0 else 1.0

        # Combine
        candidates = []
        for i, doc in enumerate(documents):
            sem = semantic_scores.get(i, 0.0)
            kw = float(bm25_raw[i]) / max_bm25 if max_bm25 > 0 else 0.0
            final = 0.6 * sem + 0.4 * kw
            candidates.append(
                {
                    "doc": doc,
                    "final_score": final,
                    "semantic_score": sem,
                    "keyword_score": float(bm25_raw[i]),
                }
            )

        candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # Deduplicate by (name, email)
        seen = set()
        unique = []
        for c in candidates:
            meta = c["doc"].metadata
            key = (meta.get("name", ""), meta.get("email", ""))
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Build output
        output = []
        for rank, item in enumerate(unique[:top_n], 1):
            doc = item["doc"]
            meta = doc.metadata
            cid = meta.get("content_hash", "")
            if not cid:
                logger.warning(f"Missing content_hash for {meta.get('name')}")
            output.append(
                {
                    "rank": rank,
                    "name": meta.get("name", "Unknown"),
                    "email": meta.get("email", "Not provided"),
                    "phone": meta.get("phone", "Not provided"),
                    "similarity_score": round(item["final_score"], 4),
                    "semantic_score": round(item["semantic_score"], 4),
                    "keyword_score": round(item["keyword_score"], 4),
                    "summary": doc.page_content[:500],
                    "validation_status": meta.get("validation_status", "incomplete"),
                    "candidate_id": cid,
                }
            )
        return output


# Singleton
vector_store_service = VectorStoreService()