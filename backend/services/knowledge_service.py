import io
import re
from typing import List
from sqlalchemy.orm import Session
from pypdf import PdfReader
from backend.models import KnowledgeDocument

STOP_WORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "apa", "bagaimana", "berapa", "kapan", "siapa", "saya",
    "aku", "bisa", "boleh", "ada", "tidak", "atau", "jika", "kalau", "the",
    "and", "for", "with", "how", "what", "is", "are", "to", "of", "in",
}


def extract_text_from_upload(filename: str, content_bytes: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content_bytes))
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[Halaman {idx}]\n{text}")
        extracted = "\n\n".join(pages).strip()
        if not extracted:
            raise ValueError("File PDF tidak memiliki teks yang dapat dibaca (kemungkinan hasil scan gambar).")
        return extracted
    elif lower.endswith((".txt", ".md", ".csv", ".json")):
        try:
            return content_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return content_bytes.decode("latin-1").strip()
    else:
        raise ValueError("Format file belum didukung. Gunakan file .pdf, .txt, atau .md.")


def _extract_snippet(content: str, tokens: List[str], max_len: int = 900) -> str:
    if len(content) <= max_len:
        return content
    lower = content.lower()
    first_pos = len(content)
    for tok in tokens:
        idx = lower.find(tok)
        if idx != -1 and idx < first_pos:
            first_pos = idx
    if first_pos == len(content):
        return content[:max_len] + "..."
    start = max(0, first_pos - 180)
    end = min(len(content), start + max_len)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"


def search_documents(db: Session, query: str, limit: int = 4) -> List[dict]:
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()
    if not docs:
        return []

    raw_tokens = re.findall(r"[a-zA-Z0-9]+", (query or "").lower())
    tokens = [t for t in raw_tokens if len(t) >= 2 and t not in STOP_WORDS]

    if not tokens:
        return [
            {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "snippet": d.content[:700] + ("..." if len(d.content) > 700 else ""),
            }
            for d in docs[:limit]
        ]

    scored = []
    for d in docs:
        title_l = d.title.lower()
        cat_l = d.category.lower()
        content_l = d.content.lower()
        score = 0
        for tok in tokens:
            if tok in title_l:
                score += 6
            if tok in cat_l:
                score += 4
            hits = content_l.count(tok)
            if hits:
                score += min(hits, 10)
        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, d in scored[:limit]:
        results.append(
            {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "score": score,
                "snippet": _extract_snippet(d.content, tokens),
            }
        )
    return results
