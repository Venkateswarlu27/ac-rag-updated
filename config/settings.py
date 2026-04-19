"""
config/settings.py
Central configuration for AC-RAG pipeline.
All thresholds, flags, and hyperparameters live here.
Ablation flags allow disabling pipeline stages for research comparison.
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root before anything else is read.
# override=False means existing shell environment variables take priority.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
VECTORSTORE_DIR = BASE_DIR / "vectorstore" / "index"
LOG_FILE = BASE_DIR / "logs" / "pipeline.log"

# ── Ingestion ─────────────────────────────────────────────────────────────────
CHUNK_SIZE = 512          # tokens (approximate via character proxy: ~4 chars/token)
CHUNK_OVERLAP = 64
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".html", ".md"]

# ── Embeddings ────────────────────────────────────────────────────────────────
# OpenAI embeddings are used by default (best quality, consistent with retrieval space).
# Swap to "sentence-transformers/all-MiniLM-L6-v2" for fully local, no-cost embeddings.
EMBEDDING_MODEL = "text-embedding-3-large"
VECTORSTORE_BACKEND = "faiss"    # "faiss" | "chroma"

# ── LLM Provider ──────────────────────────────────────────────────────────────
# Controls which LLM is used across ALL pipeline nodes (planner, generator, critic, etc.)
# Options:
#   "openai"   → OpenAI GPT models   (requires OPENAI_API_KEY)
#   "google"   → Google Gemini models (requires GOOGLE_API_KEY)
#   "anthropic"→ Anthropic Claude     (requires ANTHROPIC_API_KEY)
LLM_PROVIDER = "openai"          # ← change this one line to switch the entire pipeline

# ── LLM Models (per provider) ─────────────────────────────────────────────────
OPENAI_LLM_MODEL    = "gpt-4o"
GOOGLE_LLM_MODEL    = "gemini-2.0-flash"   # fast, low-cost, strong reasoning
ANTHROPIC_LLM_MODEL = "claude-sonnet-4-6"
GROQ_LLM_MODEL      = "llama-3.3-70b-versatile"   # free tier, fast

# Active model (resolved by utils/llm_factory.py — do not set manually)
LLM_MODEL = {
    "openai":    OPENAI_LLM_MODEL,
    "google":    GOOGLE_LLM_MODEL,
    "anthropic": ANTHROPIC_LLM_MODEL,
    "groq":      GROQ_LLM_MODEL,
}[LLM_PROVIDER]

LLM_TEMPERATURE = 0.0     # deterministic for faithfulness
LLM_MAX_TOKENS  = 2048

# ── Retrieval ─────────────────────────────────────────────────────────────────
RETRIEVAL_K_MIN     = 4
RETRIEVAL_K_MAX     = 12
RETRIEVAL_K_DEFAULT = 6
MMR_FETCH_K_MULTIPLIER = 3    # fetch_k = k * multiplier for MMR diversity pass
MMR_LAMBDA_MULT        = 0.5  # 0 = max diversity, 1 = max relevance

# ── Validation ────────────────────────────────────────────────────────────────
EVIDENCE_SCORE_THRESHOLD = 0.30   # calibrated for sentence-transformers (OpenAI: ~0.65)
MIN_VALID_PASSAGES       = 2      # retry retrieval if fewer passages pass

# ── Critic / Self-Reflection ──────────────────────────────────────────────────
CRITIC_MIN_SCORE = 4    # all dimensions must be >= 4 (scale 1–5)
MAX_RETRIES      = 3

# ── Faithfulness constraint (formal objective) ────────────────────────────────
FAITHFULNESS_THRESHOLD = 0.80    # τ in: Faith(a, R(q,D)) ≥ τ

# ── Entry Router ─────────────────────────────────────────────────────────────
# Queries with similarity >= threshold are routed to the RAG pipeline.
# Queries below the threshold receive an "I don't know" response.
ROUTER_SIMILARITY_THRESHOLD = EVIDENCE_SCORE_THRESHOLD   # reuses same scale

# ── Ablation flags ────────────────────────────────────────────────────────────
USE_RETRIEVAL_PLANNER = True
USE_VALIDATOR         = False
USE_CONTEXT_REFINER   = True
USE_CRITIC            = True

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"    # "DEBUG" for verbose stage traces
