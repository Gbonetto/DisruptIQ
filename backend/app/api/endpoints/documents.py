"""
Document Management Endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import os
from pathlib import Path

from app.core.database import get_db
from app.models.document import Document
from app.services.document_service import DocumentService
from app.services.rag_service import RAGService

router = APIRouter()
logger = structlog.get_logger()

# Upload directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and index a document

    Supported formats: PDF, DOCX, DOC, TXT
    """
    try:
        # Validate file type
        if not DocumentService.is_supported_format(file.content_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Supported: PDF, DOCX, DOC, TXT"
            )

        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: 10MB"
            )

        logger.info("document_upload_started", filename=file.filename, size=len(file_content))

        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info("file_saved", path=str(file_path))

        # Extract text
        doc_service = DocumentService()
        extracted_text, success = await doc_service.extract_text(
            file_content,
            file.content_type,
            file.filename
        )

        if not success or not extracted_text:
            # Clean up file
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to extract text from document"
            )

        logger.info("text_extracted", length=len(extracted_text))

        # Create database record
        db_document = Document(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=len(file_content),
            mime_type=file.content_type,
            extracted_text=extracted_text,
            processed=True,
            processed_at=datetime.now()
        )

        db.add(db_document)
        await db.flush()  # Get the ID without committing

        logger.info("document_record_created", document_id=db_document.id)

        # Index in Qdrant
        rag_service = RAGService()

        # Chunk text for better retrieval
        chunks = doc_service.chunk_text(extracted_text, chunk_size=1000, overlap=200)

        if chunks:
            # Index all chunks
            point_ids = await rag_service.index_document_chunks(
                document_id=db_document.id,
                chunks=chunks,
                metadata={
                    "filename": file.filename,
                    "mime_type": file.content_type,
                    "uploaded_at": datetime.now().isoformat()
                }
            )

            # Store first point ID as reference
            db_document.qdrant_id = point_ids[0] if point_ids else None
            db_document.indexed = True

            logger.info("document_indexed", document_id=db_document.id, chunks=len(chunks))
        else:
            logger.warning("no_chunks_to_index", document_id=db_document.id)

        # Commit transaction
        await db.commit()
        await db.refresh(db_document)

        logger.info("document_upload_complete", document_id=db_document.id)

        return {
            "message": "Document uploaded and indexed successfully",
            "document_id": db_document.id,
            "filename": file.filename,
            "chunks_indexed": len(chunks),
            "text_length": len(extracted_text)
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("document_upload_failed", error=str(e), filename=file.filename)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.post("/bulk-upload")
async def bulk_upload_documents(files: List[UploadFile] = File(...)):
    """Upload multiple documents"""
    results = []

    for file in files:
        try:
            # TODO: Process each file
            results.append({
                "filename": file.filename,
                "status": "success",
                "document_id": None
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })

    return {
        "total": len(files),
        "successful": len([r for r in results if r['status'] == 'success']),
        "results": results
    }


@router.get("/")
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all documents"""
    try:
        # Get total count
        from sqlalchemy import func
        total = await db.scalar(select(func.count()).select_from(Document))

        # Get documents
        result = await db.execute(
            select(Document)
            .order_by(Document.uploaded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        documents = result.scalars().all()

        return {
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.original_filename,
                    "mime_type": doc.mime_type,
                    "file_size": doc.file_size,
                    "indexed": doc.indexed,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                }
                for doc in documents
            ],
            "total": total or 0,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error("list_documents_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get document details"""
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )

        return {
            "id": document.id,
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
            "extracted_text_length": len(document.extracted_text) if document.extracted_text else 0,
            "indexed": document.indexed,
            "processed": document.processed,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "qdrant_id": document.qdrant_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_document_failed", document_id=document_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a document"""
    try:
        # Get document
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )

        # Delete from Qdrant
        if document.indexed and document.qdrant_id:
            rag_service = RAGService()
            await rag_service.delete_document(document_id)
            logger.info("document_deleted_from_qdrant", document_id=document_id)

        # Delete file from disk
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
            logger.info("file_deleted", path=document.file_path)

        # Delete from database
        await db.delete(document)
        await db.commit()

        logger.info("document_deleted", document_id=document_id)

        return {
            "message": "Document deleted successfully",
            "document_id": document_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_document_failed", document_id=document_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )
