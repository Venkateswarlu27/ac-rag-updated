"""
ingestion/figure_extractor.py
Extracts figures from PDF pages using PyMuPDF and describes them
with GPT-4o Vision, producing retrieval-ready Document chunks.

Why GPT-4o Vision:
  PyMuPDFLoader converts PDF pages to text — images are silently dropped.
  A query like "what does Figure 3 show?" would return zero relevant chunks
  without this extractor. GPT-4o Vision reads the actual pixel content and
  produces a rich text description that is then embedded and stored like any
  other chunk.

Design:
  - Only processes PDFs (other formats have no embedded images to extract).
  - Skips images smaller than MIN_IMAGE_AREA pixels² (icons, decorations).
  - Uses GPT-4o specifically — not get_llm() — because vision is only
    available on OpenAI GPT-4o regardless of the pipeline's LLM_PROVIDER.
  - Each figure becomes one Document tagged modality="figure".
  - If GPT-4o Vision is unavailable or fails, the page's text caption
    (if any) is used as a fallback so ingest never hard-fails.
"""

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Minimum image area in pixels² — skip thumbnails, logos, and decorative icons.
# A typical data figure (chart, diagram) in an A4 PDF is at least 300×200px.
MIN_IMAGE_AREA = 90_000   # ~300×300 px — filters out logos, seals, small icons

_VISION_PROMPT = (
    "You are analyzing a figure extracted from a research paper or technical document. "
    "First, decide: does this figure contain meaningful data or technical content "
    "(e.g. a chart, graph, architecture diagram, table rendered as image, flowchart, "
    "results plot)? "
    "If YES: describe it in detail — the figure type, what data it shows, key values, "
    "labels, axes, and the main insight it conveys. "
    "If NO (e.g. it is a logo, decorative image, photo, or institutional seal with no "
    "data content): respond with exactly: SKIP "
    "Be specific and thorough for data figures — your description is used for retrieval."
)


def _image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _make_figure_chunk_id(source: str, page: int, fig_index: int) -> str:
    raw = f"{source}::page{page}::fig{fig_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _describe_figure_with_vision(image_bytes: bytes, source_name: str, page: int) -> str | None:
    """
    Send image bytes to GPT-4o Vision and return a text description.
    Falls back to a placeholder if the API call fails.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        b64 = _image_to_base64(image_bytes)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=512,
        )
        description = response.choices[0].message.content.strip()
        if description.upper().startswith("SKIP"):
            logger.info("[FigureExtractor] Vision classified image on page %d as non-informational — skipped.", page)
            return None
        logger.debug("[FigureExtractor] Vision description (%d chars) for page %d of '%s'",
                     len(description), page, source_name)
        return description

    except Exception as e:
        logger.warning("[FigureExtractor] GPT-4o Vision failed for page %d of '%s': %s",
                       page, source_name, e)
        return f"[Figure on page {page} of {source_name} — vision description unavailable: {e}]"


def extract_figures(file_path: str | Path) -> List[Document]:
    """
    Extract all figures from a PDF and return them as Document chunks.

    Each Document has:
      - page_content : GPT-4o Vision description of the figure
      - metadata     : source, file_name, page, figure_index, modality="figure",
                       chunk_id, word_count, char_count, section_heading="Figure"

    Non-PDF files are silently ignored (returns empty list).
    """
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        return []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("[FigureExtractor] PyMuPDF (fitz) not installed — figure extraction skipped.")
        return []

    figure_docs: List[Document] = []

    try:
        pdf = fitz.open(str(path))
    except Exception as e:
        logger.error("[FigureExtractor] Cannot open '%s': %s", path.name, e)
        return []

    logger.info("[FigureExtractor] Scanning '%s' (%d pages) for figures...", path.name, len(pdf))

    fig_global_index = 0

    for page_num, page in enumerate(pdf, start=1):
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = pdf.extract_image(xref)
                width  = base_image.get("width", 0)
                height = base_image.get("height", 0)

                if width * height < MIN_IMAGE_AREA:
                    logger.debug("[FigureExtractor] Skipping small image (%dx%d) on page %d",
                                 width, height, page_num)
                    continue

                image_bytes = base_image["image"]
                description = _describe_figure_with_vision(image_bytes, path.name, page_num)

                # Vision said this is a logo/decoration — skip it
                if description is None:
                    continue

                chunk_id = _make_figure_chunk_id(str(path), page_num, fig_global_index)
                doc = Document(
                    page_content=description,
                    metadata={
                        "source":          str(path),
                        "file_name":       path.name,
                        "file_type":       ".pdf",
                        "page":            page_num,
                        "figure_index":    fig_global_index,
                        "image_width":     width,
                        "image_height":    height,
                        "modality":        "figure",
                        "section_heading": "Figure",
                        "chunk_id":        chunk_id,
                        "chunk_index":     fig_global_index,
                        "word_count":      len(description.split()),
                        "char_count":      len(description),
                    },
                )
                figure_docs.append(doc)
                fig_global_index += 1
                logger.info("[FigureExtractor] Figure %d extracted from page %d (%dx%d px)",
                            fig_global_index, page_num, width, height)

            except Exception as e:
                logger.warning("[FigureExtractor] Failed to process image on page %d: %s",
                               page_num, e)

    pdf.close()
    logger.info("[FigureExtractor] Extracted %d figure(s) from '%s'", len(figure_docs), path.name)
    return figure_docs
