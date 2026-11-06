"""Tiny hand-built PDFs for extraction tests (issue #24). No binary fixtures."""

from __future__ import annotations

import io


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(page_streams: list[bytes], *, image: bool = False) -> bytes:
    """Assemble a PDF with one page per content stream and a valid xref table."""
    objects: list[bytes] = []  # objects[i] is object number i + 1

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # filled in below
    pages = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    resources = f"/Font << /F1 {font} 0 R >>"
    if image:
        pixels = b"\x80" * 16
        img = add(
            b"<< /Type /XObject /Subtype /Image /Width 4 /Height 4 /ColorSpace /DeviceGray "
            b"/BitsPerComponent 8 /Length 16 >>\nstream\n" + pixels + b"\nendstream"
        )
        resources += f" /XObject << /Im1 {img} 0 R >>"
    kids = []
    for stream in page_streams:
        content = add(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        kids.append(
            add(
                f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 792] "
                f"/Resources << {resources} >> /Contents {content} 0 R >>".encode()
            )
        )
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages} 0 R >>".encode()
    kid_refs = " ".join(f"{k} 0 R" for k in kids)
    objects[pages - 1] = f"<< /Type /Pages /Kids [{kid_refs}] /Count {len(kids)} >>".encode()

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def text_pdf(*pages: str) -> bytes:
    streams = []
    for page in pages:
        lines = [b"BT /F1 11 Tf 14 TL 72 720 Td"]
        for line in page.splitlines():
            lines.append(f"({_escape(line)}) Tj T*".encode("latin-1"))
        lines.append(b"ET")
        streams.append(b"\n".join(lines))
    return build_pdf(streams)


def image_only_pdf(pages: int = 1, *, footer: str | None = None) -> bytes:
    """A 'scanned' document: each page is an image, optionally with a page footer."""
    streams = []
    for number in range(1, pages + 1):
        stream = b"q 540 0 0 700 36 46 cm /Im1 Do Q"
        if footer:
            stream += f"\nBT /F1 8 Tf 300 20 Td ({_escape(footer.format(number))}) Tj ET".encode()
        streams.append(stream)
    return build_pdf(streams, image=True)


def encrypted_pdf(text: str) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf(text))))
    writer.encrypt(user_password="", owner_password="owner", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


MALFORMED_PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> garbage \x00\xff%%EOF"
