import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Figure:
    page: int
    index: int
    image_bytes: bytes


def extract_figures(path: Path, *, min_dimension: int = 100) -> list[Figure]:
    """Extract non-decorative figures from a PDF.

    Filters out small icons/bullets by minimum pixel dimension, keeping
    diagrams and photos worth captioning. Manuals reuse the same image
    across pages (logos, repeated diagrams); identical bytes are extracted
    once, attributed to their first page.
    """
    doc = fitz.open(str(path))
    figures = []
    seen: set[bytes] = set()
    for page in doc:
        index = 0
        for img in page.get_images(full=True):
            xref = img[0]
            pixmap = fitz.Pixmap(doc, xref)
            if min(pixmap.width, pixmap.height) < min_dimension:
                continue
            if pixmap.n - pixmap.alpha >= 4:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
            image_bytes = pixmap.tobytes("png")
            digest = hashlib.sha256(image_bytes).digest()
            if digest in seen:
                continue
            seen.add(digest)
            figures.append(
                Figure(page=page.number + 1, index=index, image_bytes=image_bytes)
            )
            index += 1
    logger.info("figures_extracted", path=str(path), count=len(figures))
    return figures
