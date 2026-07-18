"""Behavior: pymupdf4llm parsing with light cleaning.

Real collaborators: real PyMuPDF-built PDFs on disk (tmp_path), real
pymupdf4llm markdown conversion. No doubles — heading detection and
hyphenation repair come from pymupdf4llm itself; this module is responsible
for dropping repeated headers/footers and collapsing whitespace.
"""

import fitz

from app.ingest.parsing import parse_pdf


def build_pdf(path, pages: list[list[tuple[tuple[float, float], str, float]]]) -> None:
    """Each page is a list of (position, text, fontsize) insertions."""
    doc = fitz.open()
    for insertions in pages:
        page = doc.new_page()
        for position, text, fontsize in insertions:
            page.insert_text(position, text, fontsize=fontsize, fontname="helv")
    doc.save(str(path))


def test_parses_heading_and_body_text(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [
            [
                ((72, 72), "Cartridge Replacement", 18),
                ((72, 110), "Open the front cover and slide out the tray.", 10),
            ]
        ],
    )

    pages = parse_pdf(pdf_path).pages

    assert len(pages) == 1
    assert pages[0].number == 1
    assert "# Cartridge Replacement" in pages[0].markdown
    assert "Open the front cover and slide out the tray." in pages[0].markdown


def test_drops_repeated_footer_across_pages(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [
            [
                ((72, 72), "First page body text.", 10),
                ((72, 750), "HP Confidential", 8),
            ],
            [
                ((72, 72), "Second page body text.", 10),
                ((72, 750), "HP Confidential", 8),
            ],
        ],
    )

    pages = parse_pdf(pdf_path).pages

    assert "HP Confidential" not in pages[0].markdown
    assert "HP Confidential" not in pages[1].markdown
    assert "First page body text." in pages[0].markdown
    assert "Second page body text." in pages[1].markdown


def test_page_specific_text_is_not_treated_as_boilerplate(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [[((72, 72), "Only appears once.", 10)]],
    )

    pages = parse_pdf(pdf_path).pages

    assert "Only appears once." in pages[0].markdown


def test_collapses_excess_blank_lines(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [[((72, 72), "Paragraph one.", 10), ((72, 400), "Paragraph two.", 10)]],
    )

    pages = parse_pdf(pdf_path).pages

    assert "\n\n\n" not in pages[0].markdown


def test_page_numbers_use_the_documents_own_printed_numbering(tmp_path):
    """A manual's front matter (cover, notices, table of contents) sits
    before its own "page 1" — pymupdf4llm's page_number is the physical
    position in the PDF, which is offset from what a reader actually sees
    printed on the page and would type into a citation. Real HP manuals
    confirmed this: a constant offset between physical and printed page
    number, holding for the whole document (verified against both attached
    PDFs, including their appendices/index).
    """
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [
            # Front matter: no printed page number next to the footer.
            [((72, 72), "Cover page.", 10), ((72, 750), "ACME Corp", 8)],
            [((72, 72), "Notices page.", 10), ((72, 750), "ACME Corp", 8)],
            # Body: printed page number sits right before the running footer.
            [
                ((72, 72), "Chapter 1 begins here.", 10),
                ((72, 700), "1 Chapter 1", 8),
                ((72, 750), "ACME Corp", 8),
            ],
            [
                ((72, 72), "More content.", 10),
                ((72, 700), "2 Chapter 1", 8),
                ((72, 750), "ACME Corp", 8),
            ],
            [
                ((72, 72), "Even more content.", 10),
                ((72, 700), "3 Chapter 2", 8),
                ((72, 750), "ACME Corp", 8),
            ],
        ],
    )

    parsed = parse_pdf(pdf_path)

    assert [p.number for p in parsed.pages] == [1, 1, 1, 2, 3]
    assert parsed.page_offset == 2


def test_page_numbers_work_without_a_repeating_footer_line(tmp_path):
    """Not every manual has a repeating company-name footer next to the
    page number — one of the two attached HP manuals doesn't. The printed
    number can be the page's own last line, with nothing else around it.
    """
    pdf_path = tmp_path / "doc.pdf"
    build_pdf(
        pdf_path,
        [
            [((72, 72), "Cover page.", 10)],
            [
                ((72, 72), "Chapter 1 begins here.", 10),
                ((72, 750), "Chapter 1 overview 1", 8),
            ],
            [
                ((72, 72), "More content.", 10),
                ((72, 750), "Chapter 1 overview 2", 8),
            ],
            [
                ((72, 72), "Even more content.", 10),
                ((72, 750), "Chapter 2 overview 3", 8),
            ],
        ],
    )

    parsed = parse_pdf(pdf_path)

    assert [p.number for p in parsed.pages] == [1, 1, 2, 3]
    assert parsed.page_offset == 1
