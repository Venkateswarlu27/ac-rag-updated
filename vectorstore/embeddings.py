"""
vectorstore/embeddings.py
Embedding model factory.

Design:
  - Centralised here so swapping embedding models (OpenAI → local HuggingFace)
    requires a change in ONE place (config/settings.py EMBEDDING_MODEL).
  - Returns a LangChain Embeddings object, which is the interface FAISS/Chroma expect.
"""

import logging
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from config.settings import EMBEDDING_MODEL

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> Embeddings:
    """
    Returns a cached embedding model instance.
    lru_cache ensures the model is loaded only once per process.

    Supported EMBEDDING_MODEL values (set in config/settings.py):
      - "text-embedding-3-small"   → OpenAI (default, best cost/quality)
      - "text-embedding-3-large"   → OpenAI (higher quality, ~6x cost)
      - "text-embedding-ada-002"   → OpenAI legacy
      - "sentence-transformers/..."→ HuggingFace local (no API key needed)
    """
    model_name = EMBEDDING_MODEL.lower()

    # OpenAI embeddings
    if model_name.startswith("text-embedding"):
        from langchain_openai import OpenAIEmbeddings
        logger.info("Loading OpenAI embedding model: %s", EMBEDDING_MODEL)
        return OpenAIEmbeddings(model=EMBEDDING_MODEL)

    # HuggingFace / sentence-transformers (local, no API key)
    if "sentence-transformers" in model_name or "/" in model_name:
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info("Loading HuggingFace embedding model: %s", EMBEDDING_MODEL)
        return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    raise ValueError(
        f"Unrecognised EMBEDDING_MODEL: '{EMBEDDING_MODEL}'. "
        "Set a valid model name in config/settings.py."
    )
