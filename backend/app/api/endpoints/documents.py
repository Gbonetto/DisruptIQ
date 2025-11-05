"""
Document Management Endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from typing import List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import os
import re
from pathlib import Path
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.models.document import Document
from app.services.document_service import DocumentService
from app.services.rag_service import get_rag_service
from app.services.agents.state_registry import get_state_manager

router = APIRouter()
logger = structlog.get_logger()

# Rate limiter for upload endpoint
limiter = Limiter(key_func=get_remote_address)

# Upload directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other security issues

    Security measures:
    - Remove path separators (/, \\)
    - Remove parent directory references (..)
    - Allow only alphanumeric, underscore, dash, and dot
    - Preserve file extension
    - Limit length to 255 characters

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem storage
    """
    # Extract extension first
    name_parts = filename.rsplit('.', 1)
    name = name_parts[0] if len(name_parts) > 1 else filename
    extension = f".{name_parts[1]}" if len(name_parts) > 1 else ""

    # Remove path separators and parent refs
    name = name.replace('/', '_').replace('\\', '_').replace('..', '_')

    # Keep only safe characters (alphanumeric, underscore, dash)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)

    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # If name is empty after sanitization, use a default
    if not name:
        name = "document"

    # Limit total length to 255 chars (filesystem limit)
    max_length = 255 - len(extension)
    if len(name) > max_length:
        name = name[:max_length]

    sanitized = f"{name}{extension}"

    # Log if sanitization changed the filename
    if sanitized != filename:
        logger.info(
            "filename_sanitized",
            original=filename,
            sanitized=sanitized
        )

    return sanitized


@router.post("/upload")
@limiter.limit("100/hour")  # SECURITY: Rate limit to prevent DoS via mass uploads (100/hour for dev)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = "default",  # Session ID for state tracking
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and index a document

    Supported formats: PDF, DOCX, DOC, TXT

    Rate limit: 100 uploads per hour per IP address (dev mode)

    Args:
        session_id: Session identifier for tracking uploaded documents
    """
    logger.info("document_upload_started", filename=file.filename)

    # Use internal helper for processing
    result = await _process_single_upload_internal(
        file=file,
        session_id=session_id,
        db=db
    )

    logger.info("document_upload_complete", document_id=result["document_id"])

    return {
        "message": "Document uploaded and indexed successfully",
        "document_id": result["document_id"],
        "filename": result["filename"],
        "chunks_indexed": result["chunks_indexed"],
        "text_length": result["text_length"]
    }


async def _cleanup_failed_upload(
    file_path: Optional[Path],
    db_document: Optional[Document],
    indexed_in_qdrant: bool,
    db: AsyncSession
):
    """
    Cleanup resources on failed upload - ensures atomicity

    Args:
        file_path: Path to file on disk (if saved)
        db_document: Database document record (if created)
        indexed_in_qdrant: Whether document was indexed in Qdrant
        db: Database session
    """
    try:
        # Rollback DB transaction
        await db.rollback()
        logger.info("cleanup_db_rollback")

        # Delete file from disk
        if file_path and file_path.exists():
            file_path.unlink(missing_ok=True)
            logger.info("cleanup_file_deleted", path=str(file_path))

        # Delete from Qdrant if indexed
        if indexed_in_qdrant and db_document and db_document.id:
            try:
                rag_service = get_rag_service()
                await rag_service.delete_document(db_document.id)
                logger.info("cleanup_qdrant_deleted", document_id=db_document.id)
            except Exception as e:
                logger.error("cleanup_qdrant_failed", error=str(e), document_id=db_document.id)

    except Exception as e:
        logger.error("cleanup_failed", error=str(e))


@router.post("/bulk-upload")
async def bulk_upload_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    session_id: str = "default",
    db: AsyncSession = Depends(get_db)
):
    """
    Upload multiple documents in batch

    Processes files sequentially to avoid overwhelming the system
    Maximum 20 files per batch
    """
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 files per batch upload"
        )

    results = []
    successful_count = 0

    for file in files:
        try:
            # Process each file using internal helper
            result = await _process_single_upload_internal(
                file=file,
                session_id=session_id,
                db=db
            )

            results.append({
                "filename": file.filename,
                "status": "success",
                "document_id": result["document_id"],
                "chunks_indexed": result["chunks_indexed"]
            })
            successful_count += 1

        except HTTPException as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": e.detail
            })
        except Exception as e:
            logger.error("bulk_upload_file_failed", filename=file.filename, error=str(e))
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })

    logger.info("bulk_upload_completed",
                total=len(files),
                successful=successful_count,
                failed=len(files) - successful_count)

    return {
        "total": len(files),
        "successful": successful_count,
        "failed": len(files) - successful_count,
        "results": results
    }


async def _process_single_upload_internal(
    file: UploadFile,
    session_id: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Internal helper to process a single file upload
    Used by both single and bulk upload endpoints

    Returns:
        Dict with document_id, filename, chunks_indexed, text_length

    Raises:
        HTTPException on validation or processing errors
    """
    file_path = None
    db_document = None
    indexed_in_qdrant = False

    try:
        # Validate file type
        if not DocumentService.is_supported_format(file.content_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}"
            )

        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: 10MB"
            )

        # Sanitize filename
        sanitized_original_filename = sanitize_filename(file.filename)

        # Extract text BEFORE saving to disk
        doc_service = DocumentService()
        extracted_text, success = await doc_service.extract_text(
            file_content,
            file.content_type,
            file.filename
        )

        if not success or not extracted_text:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract text from document"
            )

        # Chunk text BEFORE saving (validation)
        chunks = doc_service.chunk_text(extracted_text, chunk_size=1000, overlap=200)

        if not chunks:
            raise HTTPException(
                status_code=500,
                detail="No text chunks generated from document"
            )

        # NOW save file to disk (after validation)
        file_extension = Path(sanitized_original_filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create DB record
        db_document = Document(
            filename=unique_filename,
            original_filename=sanitized_original_filename,
            file_path=str(file_path),
            file_size=len(file_content),
            mime_type=file.content_type,
            extracted_text=extracted_text,
            processed=True,
            processed_at=datetime.now()
        )

        db.add(db_document)
        await db.flush()  # Get ID

        # Index in Qdrant
        rag_service = get_rag_service()
        point_ids = await rag_service.index_document_chunks(
            document_id=db_document.id,
            chunks=chunks,
            metadata={
                "filename": file.filename,
                "original_filename": db_document.original_filename,
                "title": db_document.original_filename,
                "mime_type": file.content_type,
                "uploaded_at": datetime.now().isoformat()
            }
        )

        indexed_in_qdrant = True

        db_document.qdrant_id = point_ids[0] if point_ids else None
        db_document.indexed = True

        # Commit transaction
        await db.commit()
        await db.refresh(db_document)

        # Update state
        state_manager = get_state_manager(session_id)
        state_manager.state.add_uploaded_document(
            filename=file.filename,
            document_id=db_document.id,
            mime_type=file.content_type
        )

        return {
            "document_id": db_document.id,
            "filename": file.filename,
            "chunks_indexed": len(chunks),
            "text_length": len(extracted_text)
        }

    except HTTPException:
        await _cleanup_failed_upload(file_path, db_document, indexed_in_qdrant, db)
        raise
    except Exception as e:
        await _cleanup_failed_upload(file_path, db_document, indexed_in_qdrant, db)
        logger.error("upload_processing_failed", error=str(e), filename=file.filename)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


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
                    "filename": doc.filename,  # UUID filename
                    "original_filename": doc.original_filename,  # User's original filename
                    "mime_type": doc.mime_type,
                    "file_size": doc.file_size,
                    "indexed": doc.indexed,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "chunk_count": None  # TODO: Add chunk count if needed
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
            rag_service = get_rag_service()
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


@router.post("/active")
async def set_active_documents(
    request: Request,
    session_id: str = "default"
):
    """
    Set active documents for RAG filtering (checkbox selection)

    Args:
        document_ids: List of document IDs currently selected
        session_id: Session identifier for state tracking
    """
    try:
        # Parse JSON body
        body = await request.json()
        document_ids = body.get("document_ids", [])

        # Validate that document_ids is a list
        if not isinstance(document_ids, list):
            raise HTTPException(
                status_code=400,
                detail="document_ids must be a list"
            )

        # Get state manager for session
        state_manager = get_state_manager(session_id)

        # Update active document IDs in state
        state_manager.state.set_active_document_ids(document_ids)

        logger.info("active_documents_updated",
                   session_id=session_id,
                   count=len(document_ids),
                   ids=document_ids)

        return {
            "message": "Active documents updated successfully",
            "session_id": session_id,
            "document_ids": document_ids,
            "count": len(document_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("set_active_documents_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set active documents: {str(e)}"
        )
