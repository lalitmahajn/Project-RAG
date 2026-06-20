import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from .session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Book(Base):
    __tablename__ = "books"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    vachans = relationship("Vachan", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="chapters")
    vachans = relationship("Vachan", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number", name="uq_book_chapter"),
    )


class Vachan(Base):
    __tablename__ = "vachans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    vachan_number = Column(Integer, nullable=False)
    original_text = Column(String, nullable=False)
    hindi_meaning = Column(String, nullable=False)
    status = Column(String(20), default="draft")  # draft, review, approved
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="vachans")
    chapter = relationship("Chapter", back_populates="vachans")

    # No unique constraint: numbering resets on section changes


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")  # pending, parsing, completed, failed
    error_message = Column(String, nullable=True)
    book_id = Column(String(36), ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    book = relationship("Book")

