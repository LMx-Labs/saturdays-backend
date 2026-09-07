from pathlib import Path

import markdown
from pypdf import PdfReader, PdfWriter
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE = DOCS / "FRONTEND_BACKEND_INTEGRATION.md"
STYLESHEET = DOCS / "pdf.css"
OUTPUT = DOCS / "FRONTEND_BACKEND_INTEGRATION.pdf"


def main() -> None:
    body = markdown.markdown(
        SOURCE.read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables"],
    )
    css = STYLESHEET.read_text(encoding="utf-8")
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<style>{css}</style></head><body>{body}</body></html>"
    )
    rendered = OUTPUT.with_suffix(".rendered.pdf")
    with rendered.open("wb") as target:
        result = pisa.CreatePDF(html, dest=target, encoding="utf-8")
    if result.err:
        rendered.unlink(missing_ok=True)
        raise RuntimeError(f"PDF rendering failed with {result.err} error(s)")

    reader = PdfReader(rendered)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.add_metadata(
        {
            "/Title": "DineGuru Frontend-Backend Integration Contract",
            "/Author": "Saturdays Engineering",
            "/Subject": "DineGuru product API, security, and role workspace contract",
        }
    )
    with OUTPUT.open("wb") as target:
        writer.write(target)
    rendered.unlink()
    verified = PdfReader(OUTPUT)
    print(f"[OK] Generated {OUTPUT.name}: {len(verified.pages)} pages")


if __name__ == "__main__":
    main()
