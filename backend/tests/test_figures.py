"""Behavior: extract figures from a PDF, filtering decorative images by size
(SPEC §7.4). Real collaborators: real PyMuPDF-built PDFs on disk (tmp_path).
"""

import fitz

from app.ingest.figures import extract_figures


def solid_pixmap(width: int, height: int, color: tuple[int, int, int]) -> fitz.Pixmap:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pix.set_rect(pix.irect, color)
    return pix


def build_pdf(path, pages_images: list[list[tuple[fitz.Pixmap, fitz.Rect]]]) -> None:
    doc = fitz.open()
    for images in pages_images:
        page = doc.new_page()
        for pixmap, rect in images:
            page.insert_image(rect, pixmap=pixmap)
    doc.save(str(path))


def test_keeps_large_figures_and_drops_decorative_icons(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    big = solid_pixmap(200, 200, (255, 0, 0))
    small = solid_pixmap(20, 20, (0, 255, 0))
    build_pdf(
        pdf_path,
        [
            [
                (big, fitz.Rect(50, 50, 250, 250)),
                (small, fitz.Rect(300, 50, 320, 70)),
            ]
        ],
    )

    figures = extract_figures(pdf_path, min_dimension=100)

    assert len(figures) == 1
    assert figures[0].page == 1
    assert figures[0].index == 0


def test_figures_are_tagged_with_their_page_number(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    big = solid_pixmap(150, 150, (0, 0, 255))
    build_pdf(
        pdf_path,
        [
            [],
            [(big, fitz.Rect(50, 50, 200, 200))],
        ],
    )

    figures = extract_figures(pdf_path, min_dimension=100)

    assert len(figures) == 1
    assert figures[0].page == 2


def test_image_bytes_are_valid_png(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    big = solid_pixmap(150, 150, (10, 20, 30))
    build_pdf(pdf_path, [[(big, fitz.Rect(50, 50, 200, 200))]])

    [figure] = extract_figures(pdf_path, min_dimension=100)

    assert figure.image_bytes.startswith(b"\x89PNG")


def test_cmyk_images_are_converted_to_a_valid_png(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    cmyk = fitz.Pixmap(fitz.csCMYK, fitz.IRect(0, 0, 150, 150), False)
    cmyk.set_rect(cmyk.irect, (0, 0, 0, 50))
    build_pdf(pdf_path, [[(cmyk, fitz.Rect(50, 50, 200, 200))]])

    [figure] = extract_figures(pdf_path, min_dimension=100)

    assert figure.image_bytes.startswith(b"\x89PNG")
