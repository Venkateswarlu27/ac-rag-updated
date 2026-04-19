"""
pipeline/state.py
LangGraph shared state schema for the AC-RAG pipeline.

ALL nodes read from and write to this TypedDict.
Using TypedDict (not dataclass) because LangGraph requires it for state management
and supports partial updates — each node only writes the fields it owns.

Field ownership (which node writes what):
  query_analyzer   → rewritten_query, intent, complexity_score, decomposed_queries
  retrieval_planner→ retrieval_plan
  retriever        → retrieved_docs
  validator        → scored_docs, validation_passed
  context_refiner  → refined_context
  generator        → answer, answer_with_attribution
  critic           → critic_scores, critic_passed, critic_feedback

Shared lifecycle fields:
  retry_count      → incremented by the graph router on each retry loop
  stage_logs       → append-only list; every node appends its trace entry
  error            → set if a node fails; triggers graceful exit
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class RetrievalPlan(TypedDict):
    """
    Output of the Retrieval Planner node.
    Drives how the Retriever node executes its search.
    """
    k: int                      # number of final passages to retrieve (4–12)
    fetch_k: int                # MMR candidate pool size
    lambda_mult: float          # MMR diversity parameter (0=diverse, 1=relevant)
    modality_filter: str        # "text" | "table" | "figure" | "all"
    use_multi_query: bool       # decompose query into sub-queries before retrieval
    retrieval_depth: str        # "shallow" | "standard" | "deep"


class CriticScores(TypedDict):
    """
    Output of the Critic (self-reflection) node.
    All dimensions scored 1–5. Accept only if ALL ≥ CRITIC_MIN_SCORE.
    """
    faithfulness: int
    completeness: int
    table_accuracy: int
    figure_accuracy: int
    conciseness: int
    overall: float              # mean of all dimensions
    feedback: str               # critic's textual feedback for retry


class StageLogEntry(TypedDict):
    stage: str
    status: str                 # "started" | "completed" | "failed" | "skipped"
    details: Dict[str, Any]


class ACRagState(TypedDict):
    """
    Full shared state for the AC-RAG LangGraph pipeline.
    """
    # ── Input ─────────────────────────────────────────────────────────────────
    query: str

    # ── Entry Router output ───────────────────────────────────────────────────
    route: Optional[str]                 # "rag" | "unknown"

    # ── Query Analyzer outputs ────────────────────────────────────────────────
    rewritten_query: Optional[str]      # clarified query optimised for vector retrieval
    intent: Optional[str]               # "factual" | "analytical" | "comparative" | "summarization"
    complexity_score: Optional[float]   # 0.0 (simple) → 1.0 (complex)
    decomposed_queries: Optional[List[str]]  # sub-queries if complex

    # ── Retrieval Planner outputs ─────────────────────────────────────────────
    retrieval_plan: Optional[RetrievalPlan]

    # ── Retriever outputs ─────────────────────────────────────────────────────
    retrieved_docs: Optional[List[Dict[str, Any]]]  # list of {content, metadata}

    # ── Validator outputs ─────────────────────────────────────────────────────
    scored_docs: Optional[List[Dict[str, Any]]]     # docs with "score" field added
    validation_passed: Optional[bool]

    # ── Context Refiner outputs ───────────────────────────────────────────────
    refined_context: Optional[str]      # deduplicated, re-ranked, compressed context

    # ── Generator outputs ─────────────────────────────────────────────────────
    answer: Optional[str]
    answer_with_attribution: Optional[List[Dict[str, Any]]]  # [{sentence, source_chunk_id}]

    # ── Critic outputs ────────────────────────────────────────────────────────
    critic_scores: Optional[CriticScores]
    critic_passed: Optional[bool]
    critic_feedback: Optional[str]

    # ── Pipeline control ──────────────────────────────────────────────────────
    retry_count: int
    retry_reason: Optional[str]         # "content" | "format" — drives retry routing
    stage_logs: List[StageLogEntry]     # append-only trace for research analysis
    error: Optional[str]                # non-None triggers graceful pipeline exit


def initial_state(query: str) -> ACRagState:
    """
    Create a clean initial state for a new query.
    All optional fields start as None; pipeline fills them in order.
    """
    return ACRagState(
        query=query,
        route=None,
        rewritten_query=None,
        intent=None,
        complexity_score=None,
        decomposed_queries=None,
        retrieval_plan=None,
        retrieved_docs=None,
        scored_docs=None,
        validation_passed=None,
        refined_context=None,
        answer=None,
        answer_with_attribution=None,
        critic_scores=None,
        critic_passed=None,
        critic_feedback=None,
        retry_count=0,
        retry_reason=None,
        stage_logs=[],
        error=None,
    )
