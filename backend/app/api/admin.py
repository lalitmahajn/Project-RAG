import os
import shutil
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..db.session import SessionLocal, get_db
from ..db.models import Book, Document, Vachan
from ..schemas.admin import DocumentResponse, VachanResponse, VachanUpdate
from ..services.pdf_parser import parse_and_ingest_pdf

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Ensure data directory exists
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/raw_pdfs"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


def parse_uploaded_pdf(document_id: str, file_path: str, book_name: str):
    db = SessionLocal()
    try:
        parse_and_ingest_pdf(file_path, book_name, document_id, db)
    finally:
        db.close()

@router.post("/upload", response_model=DocumentResponse)
def upload_pdf(
    background_tasks: BackgroundTasks,
    book_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )

    # Make sure book exists or create it
    book = db.query(Book).filter(Book.name == book_name).first()
    if not book:
        book = Book(name=book_name)
        db.add(book)
        db.commit()
        db.refresh(book)

    # Use original filename (preserves Unicode/Devanagari characters)
    filename = file.filename
    file_path = os.path.join(UPLOAD_DIR, filename)

    # Save PDF locally
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Create document task
    doc = Document(
        filename=filename,
        status="pending",
        book_id=book.id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(parse_uploaded_pdf, doc.id, file_path, book_name)

    return doc

@router.get("/tasks", response_model=List[DocumentResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()

@router.get("/vachans/review", response_model=List[VachanResponse])
def get_vachans_for_review(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return db.query(Vachan).filter(Vachan.status != "approved").offset(skip).limit(limit).all()

@router.put("/vachans/{id}", response_model=VachanResponse)
def update_vachan(
    id: str,
    payload: VachanUpdate,
    db: Session = Depends(get_db)
):
    vachan = db.query(Vachan).filter(Vachan.id == id).first()
    if not vachan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vachan not found"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vachan, field, value)

    # Regenerate embedding if approved
    if vachan.status == "approved":
        import json
        from ..services.llm import generate_embedding
        text_to_embed = f"Original: {vachan.original_text}\nMeaning: {vachan.hindi_meaning}"
        vector = generate_embedding(text_to_embed)
        if vector:
            vachan.embedding = json.dumps(vector)

    db.commit()
    db.refresh(vachan)
    return vachan

@router.post("/vachans/bulk-approve")
def bulk_approve_vachans(
    ids: List[str],
    db: Session = Depends(get_db)
):
    import json
    from ..services.llm import generate_embedding
    vachans = db.query(Vachan).filter(Vachan.id.in_(ids)).all()
    updated_count = 0
    for v in vachans:
        v.status = "approved"
        text_to_embed = f"Original: {v.original_text}\nMeaning: {v.hindi_meaning}"
        vector = generate_embedding(text_to_embed)
        if vector:
            v.embedding = json.dumps(vector)
        updated_count += 1
    db.commit()
    return {"message": f"Successfully approved {updated_count} vachans."}

from fastapi.responses import FileResponse

@router.get("/pdf/{filename}")
def get_pdf_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found."
        )
    return FileResponse(file_path, media_type="application/pdf")
