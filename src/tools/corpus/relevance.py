"""Hybrid relevance ranking utilities for Phase 2 retrieval."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from src.audit import AuditTimer, log_agent_step
from src.config import GEMINI_FLASH
from src.llm import call_llm, is_llm_unavailable_response, parse_json_response
from src.models import Article


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= 2]


def _article_text(article: Article) -> str:
    return " ".join([
        article.title,
        article.category,
        " ".join(article.tags),
        article.content[:5000],
    ]).lower()


def _bm25_scores(query: str, docs: list[str], k1: float = 1.2, b: float = 0.75) -> list[float]:
    """Compute BM25 scores without external dependency."""
    if not docs:
        return []

    tokenized_docs = [_tokenize(doc) for doc in docs]
    q_tokens = _tokenize(query)
    if not q_tokens:
        return [0.0] * len(docs)

    doc_freq: dict[str, int] = defaultdict(int)
    term_freqs: list[Counter] = []
    lengths: list[int] = []

    for doc_tokens in tokenized_docs:
        counter = Counter(doc_tokens)
        term_freqs.append(counter)
        lengths.append(len(doc_tokens) or 1)
        for token in counter.keys():
            doc_freq[token] += 1

    n_docs = len(docs)
    avgdl = sum(lengths) / n_docs
    scores: list[float] = []

    for idx, tf in enumerate(term_freqs):
        dl = lengths[idx]
        score = 0.0
        for token in q_tokens:
            if token not in tf:
                continue
            df = doc_freq.get(token, 0)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            freq = tf[token]
            denom = freq + k1 * (1 - b + b * (dl / avgdl if avgdl else 1.0))
            score += idf * ((freq * (k1 + 1.0)) / denom)
        scores.append(score)

    return scores


class EmbeddingScorer:
    """Lazy embedding scorer using sentence-transformers when available."""

    def __init__(self):
        self._model = None
        self._available = True

    def _get_model(self):
        if self._model is not None:
            return self._model
        if not self._available:
            return None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            return self._model
        except Exception:
            self._available = False
            return None

    def similarity_scores(self, query: str, docs: list[str]) -> list[float]:
        model = self._get_model()
        if model is None or not docs:
            return [0.0] * len(docs)

        try:
            q_vec = np.asarray(model.encode([query], normalize_embeddings=True)[0], dtype=float)
            d_vecs = np.asarray(model.encode(docs, normalize_embeddings=True), dtype=float)
            sims = d_vecs @ q_vec
            return [float(s) for s in sims.tolist()]
        except Exception:
            return [0.0] * len(docs)


_EMBEDDING_SCORER = EmbeddingScorer()


def hybrid_rank_articles(topic: str, articles: list[Article], top_k: int = 80) -> list[dict[str, Any]]:
    """Rank by weighted BM25 + embedding similarity and attach explainability."""
    if not articles:
        return []

    docs = [_article_text(a) for a in articles]
    bm25 = _bm25_scores(topic, docs)
    emb = _EMBEDDING_SCORER.similarity_scores(topic, docs)

    max_bm25 = max(bm25) if bm25 else 0.0
    max_emb = max(emb) if emb else 0.0

    ranked: list[dict[str, Any]] = []
    for idx, article in enumerate(articles):
        bm25_norm = (bm25[idx] / max_bm25) if max_bm25 > 0 else 0.0
        emb_norm = (emb[idx] / max_emb) if max_emb > 0 else 0.0
        combined = 0.6 * bm25_norm + 0.4 * emb_norm

        reason_parts = []
        if bm25_norm >= 0.35:
            reason_parts.append(f"strong_lexical={bm25_norm:.2f}")
        if emb_norm >= 0.35:
            reason_parts.append(f"semantic_match={emb_norm:.2f}")
        if not reason_parts:
            reason_parts.append("weak_match")

        ranked.append(
            {
                "article": article,
                "article_id": article.id,
                "bm25_score": round(bm25_norm, 4),
                "embedding_score": round(emb_norm, 4),
                "combined_score": round(combined, 4),
                "base_reason": "; ".join(reason_parts),
            }
        )

    ranked.sort(key=lambda row: (row["combined_score"], row["article"].published_at), reverse=True)
    return ranked[: max(1, top_k)]


async def llm_rerank_top(
    topic: str,
    ranked_rows: list[dict[str, Any]],
    session_id: str = "default",
    top_k: int = 16,
    final_k: int = 10,
) -> tuple[list[str], dict[str, str], str]:
    """Use LLM as a light reranker over top candidates with deterministic fallback."""
    if not ranked_rows:
        return [], {}, "hybrid_empty"

    candidates = ranked_rows[: max(1, top_k)]
    candidate_lines = []
    for idx, row in enumerate(candidates, start=1):
        article: Article = row["article"]
        candidate_lines.append(
            f"{idx}. id={article.id}\n"
            f"title={article.title}\n"
            f"category={article.category}\n"
            f"scores: lexical={row['bm25_score']}, semantic={row['embedding_score']}, combined={row['combined_score']}\n"
            f"snippet={article.content[:240]}"
        )

    prompt = (
        f"Topic: {topic}\n\n"
        "Candidates:\n"
        + "\n\n".join(candidate_lines)
        + "\n\nReturn JSON with this schema:\n"
        + json.dumps(
            {
                "selected_ids": ["id1", "id2"],
                "reasons": {"id1": "reason"},
            },
            indent=2,
        )
        + "\nRules: select up to "
        + str(max(1, final_k))
        + " IDs, prefer broad topical coverage, and only use given IDs."
    )

    with AuditTimer() as timer:
        try:
            raw = await call_llm(
                prompt=prompt,
                model=GEMINI_FLASH,
                system_instruction=(
                    "You are a strict financial-topic reranker. "
                    "Return strict JSON only, no markdown."
                ),
                response_mime_type="application/json",
                temperature=0.1,
            )

            if is_llm_unavailable_response(raw):
                raise ValueError("LLM unavailable for rerank")

            parsed = parse_json_response(raw)
            selected = [str(x).strip() for x in parsed.get("selected_ids", []) if str(x).strip()]
            reasons_raw = parsed.get("reasons", {})
            reasons = {
                str(k).strip(): str(v).strip()
                for k, v in reasons_raw.items()
                if str(k).strip() and str(v).strip()
            }

            valid = {row["article_id"] for row in candidates}
            selected = [aid for aid in selected if aid in valid][: max(1, final_k)]
            if selected:
                log_agent_step(
                    agent_name="HybridRelevance",
                    action="llm_rerank_top",
                    model_used=GEMINI_FLASH,
                    input_summary=f"topic={topic}, candidates={len(candidates)}",
                    output_summary=f"selected={len(selected)}",
                    latency_ms=timer.elapsed_ms,
                    status="success",
                    session_id=session_id,
                )
                return selected, reasons, "hybrid_bm25_embedding_llm"
        except Exception:
            pass

    # Deterministic fallback: use top combined candidates.
    fallback_ids = [row["article_id"] for row in candidates[: max(1, final_k)]]
    fallback_reasons = {
        row["article_id"]: f"fallback_combined_rank={i + 1}; {row['base_reason']}"
        for i, row in enumerate(candidates[: max(1, final_k)])
    }
    return fallback_ids, fallback_reasons, "hybrid_bm25_embedding_fallback"
