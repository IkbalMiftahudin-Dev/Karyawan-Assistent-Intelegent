from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import KnowledgeDocument
from backend.schemas import KnowledgeCreate, KnowledgeOut
from backend.services import knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


@router.get("", response_model=List[KnowledgeOut])
def list_documents(
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(KnowledgeDocument)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (KnowledgeDocument.title.ilike(like))
            | (KnowledgeDocument.category.ilike(like))
            | (KnowledgeDocument.content.ilike(like))
        )
    return query.order_by(KnowledgeDocument.created_at.desc()).all()


@router.post("", response_model=KnowledgeOut, status_code=201)
def create_document(payload: KnowledgeCreate, db: Session = Depends(get_db)):
    doc = KnowledgeDocument(
        title=payload.title.strip(),
        category=payload.category.strip() or "SOP Umum",
        filename="",
        content=payload.content.strip(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/upload", response_model=KnowledgeOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("SOP & Kebijakan"),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="File kosong.")
    try:
        extracted = knowledge_service.extract_text_from_upload(file.filename or "dokumen.txt", raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    doc_title = title.strip() or (file.filename or "Dokumen Tanpa Judul").rsplit(".", 1)[0]
    doc = KnowledgeDocument(
        title=doc_title,
        category=category.strip() or "SOP & Kebijakan",
        filename=file.filename or "",
        content=extracted,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    db.delete(doc)
    db.commit()
    return {"deleted": True, "id": doc_id}
