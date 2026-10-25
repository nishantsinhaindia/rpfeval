"""Document Tool: extract clean text from a PDF."""
import re

import pymupdf

MAX_CHARS = 60000


def extract_text(pdf_bytes: bytes) -> str:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        pages = [p.get_text("text") for p in doc]
    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CHARS]
