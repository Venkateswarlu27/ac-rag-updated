"""
ingestion package
Exposes the full ingest pipeline as a single callable: ingest_documents()
"""

from ingestion.loader import load_document, load_directory
from ingestion.chunker import chunk_documents
from ingestion.metadata_tagger import tag_chunks
from ingestion.figure_extractor import extract_figures

__all__ = [
    "load_document", "load_directory", "chunk_documents",
    "tag_chunks", "extract_figures", "ingest_documents",
]


def ingest_documents(source):
    """
    Full ingestion pipeline: load → chunk → tag → figure extraction.

    For PDF files, figures are extracted separately using GPT-4o Vision
    and merged with the text chunks. Each figure becomes one Document
    tagged modality="figure" with a rich visual description as its content.

    Args:
        source: path to a single file or a directory.

    Returns:
        List[Document] — tagged, chunked, metadata-enriched documents
                         including GPT-4o Vision descriptions for figures.
    """
    from pathlib import Path
    path = Path(source)

    if path.is_dir():
        raw_docs = load_directory(path)
    else:
        raw_docs = load_document(path)

    chunks = chunk_documents(raw_docs)
    tagged = tag_chunks(chunks)

    # Extract figures from PDF files using GPT-4o Vision
    # Figure chunks are already sized correctly — skip the text splitter
    if path.is_dir():
        pdf_files = list(path.rglob("*.pdf"))
    else:
        pdf_files = [path] if path.suffix.lower() == ".pdf" else []

    figure_chunks = []
    for pdf_path in pdf_files:
        figure_chunks.extend(extract_figures(pdf_path))

    if figure_chunks:
        import logging
        logging.getLogger(__name__).info(
            "Merged %d figure chunk(s) into ingest output", len(figure_chunks)
        )

    return tagged + figure_chunks
