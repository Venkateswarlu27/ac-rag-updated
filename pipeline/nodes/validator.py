"""
pipeline/nodes/validator.py
Validator Node — Evidence Validation (full implementation).

Algorithm:
  1. Embed query and all retrieved passages
  2. Compute cosine similarity (query ↔ each passage)
  3. Attach score to each passage
  4. Discard passages with score < EVIDENCE_SCORE_THRESHOLD (0.65)
  5. If surviving passages < MIN_VALID_PASSAGES → set validation_passed=False
     (graph router will retry retrieval)
  6. Log score distribution for research analysis

Ablation:
  USE_VALIDATOR=False → all docs pass with score=1.0 (set in settings.py)
"""

import logging
from typing import Any, Dict, List

from config.settings import (
    EVIDENCE_SCORE_THRESHOLD,
    MIN_VALID_PASSAGES,
    USE_VALIDATOR,
)
from pipeline.state import ACRagState
from utils.scoring import score_passages_against_query

logger = logging.getLogger(__name__)


def _score_and_filter(
    query: str,
    docs: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Score all docs and filter below threshold.
    Returns (filtered_docs, stats_dict).
    """
    texts = [doc["content"] for doc in docs]
    scores = score_passages_against_query(query, texts)

    # Attach scores
    scored = [{**doc, "score": score} for doc, score in zip(docs, scores)]

    # Log individual scores for research traceability
    for doc in scored:
        logger.debug(
            "[Validator] chunk=%s score=%.4f section=%s",
            doc.get("chunk_id", "?"), doc["score"], doc.get("section_heading", "?")
        )

    # Filter
    passed = [doc for doc in scored if doc["score"] >= EVIDENCE_SCORE_THRESHOLD]
    failed = [doc for doc in scored if doc["score"] < EVIDENCE_SCORE_THRESHOLD]

    stats = {
        "total": len(scored),
        "passed": len(passed),
        "failed": len(failed),
        "threshold": EVIDENCE_SCORE_THRESHOLD,
        "score_min": round(min(scores), 4) if scores else 0.0,
        "score_max": round(max(scores), 4) if scores else 0.0,
        "score_mean": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }

    return passed, stats


def validator_node(state: ACRagState) -> ACRagState:
    """
    LangGraph node: Validator (full implementation).
    Reads:  state["query"], state["retrieved_docs"]
    Writes: state["scored_docs"], state["validation_passed"]
    """
    query = state["query"]
    docs = state.get("retrieved_docs") or []

    log_entry: Dict[str, Any] = {
        "stage": "validator",
        "status": "started",
        "details": {"docs_in": len(docs)},
    }

    if not docs:
        logger.warning("[Validator] No documents to validate.")
        log_entry["status"] = "completed"
        log_entry["details"]["validation_passed"] = False
        log_entry["details"]["reason"] = "empty_docs"
        return {
            **state,
            "scored_docs": [],
            "validation_passed": False,
            "stage_logs": state["stage_logs"] + [log_entry],
        }

    # ── Ablation bypass ───────────────────────────────────────────────────────
    if not USE_VALIDATOR:
        logger.info("[Validator] Ablation: validator disabled — passing all %d docs", len(docs))
        scored = [{**doc, "score": 1.0} for doc in docs]
        log_entry["status"] = "completed"
        log_entry["details"].update({"validation_passed": True, "ablation_skip": True})
        return {
            **state,
            "scored_docs": scored,
            "validation_passed": True,
            "stage_logs": state["stage_logs"] + [log_entry],
        }

    # ── Score and filter ──────────────────────────────────────────────────────
    try:
        passed_docs, stats = _score_and_filter(query, docs)

        validation_passed = len(passed_docs) >= MIN_VALID_PASSAGES

        logger.info(
            "[Validator] %d/%d passages passed (threshold=%.2f). "
            "scores: min=%.3f max=%.3f mean=%.3f. valid=%s",
            stats["passed"], stats["total"],
            EVIDENCE_SCORE_THRESHOLD,
            stats["score_min"], stats["score_max"], stats["score_mean"],
            validation_passed,
        )

        if not validation_passed:
            logger.warning(
                "[Validator] Only %d passage(s) passed minimum threshold %d — will retry retrieval.",
                len(passed_docs), MIN_VALID_PASSAGES,
            )

        log_entry["status"] = "completed"
        log_entry["details"].update({**stats, "validation_passed": validation_passed})

        return {
            **state,
            "scored_docs": passed_docs,
            "validation_passed": validation_passed,
            "stage_logs": state["stage_logs"] + [log_entry],
        }

    except Exception as e:
        logger.error("[Validator] Scoring failed: %s", e)
        log_entry["status"] = "failed"
        log_entry["details"]["error"] = str(e)
        # On scoring failure, pass docs through unscored rather than crashing pipeline
        scored_fallback = [{**doc, "score": 0.0} for doc in docs]
        return {
            **state,
            "scored_docs": scored_fallback,
            "validation_passed": False,
            "error": f"Validator scoring failed: {e}",
            "stage_logs": state["stage_logs"] + [log_entry],
        }
