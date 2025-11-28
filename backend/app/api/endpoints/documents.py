"""
Document Management Endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import os
import re
import io
from pathlib import Path
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.models.document import Document
from app.services.document_service import DocumentService
from app.services.rag_service import RAGService
from app.services.agents.state_registry import get_state_manager
from app.services.agents.ocr_agent import OCRAgent
# from app.services.invoice_extraction_service import InvoiceExtractionService  # TODO: Create this service
# from app.services.excel_export_service import ExcelExportService  # TODO: Create this service if needed
# from app.schemas.invoice import InvoiceData  # TODO: Create this schema if needed
from app.services.ocr_progress_service import ocr_progress_service, OCRStatus
from app.utils.file_validation import validate_upload

router = APIRouter()
logger = structlog.get_logger()

# Rate limiter for upload endpoint
limiter = Limiter(key_func=get_remote_address)

# Upload directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def needs_ocr(content_type: str, filename: str) -> bool:
    """
    Determine if a file needs OCR processing

    Args:
        content_type: MIME type of file
        filename: Original filename

    Returns:
        True if file is an image or PDF that may need OCR
    """
    # Image types that need OCR
    image_types = [
        'image/png',
        'image/jpeg',
        'image/jpg',
        'image/tiff',
        'image/bmp',
        'image/gif'
    ]

    # PDF may contain scanned images
    pdf_types = ['application/pdf']

    # Check by content type
    if content_type in image_types:
        return True

    if content_type in pdf_types:
        return True

    # Check by extension as fallback
    filename_lower = filename.lower()
    if filename_lower.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.pdf')):
        return True

    return False


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

    Supported formats: PDF, DOCX, DOC, TXT, PNG, JPG, JPEG, TIFF, BMP

    Rate limit: 100 uploads per hour per IP address (dev mode)

    Args:
        session_id: Session identifier for tracking uploaded documents
    """
    try:
        # Read file content first for validation
        file_content = await file.read()

        # SECURITY: Strict file validation (MIME, extension, size, content)
        is_valid, error_message = validate_upload(
            filename=file.filename,
            content_type=file.content_type,
            file_content=file_content
        )

        if not is_valid:
            logger.warning(
                "file_upload_rejected",
                filename=file.filename,
                content_type=file.content_type,
                reason=error_message
            )
            raise HTTPException(
                status_code=400,
                detail=error_message
            )

        # SECURITY: Sanitize filename to prevent path traversal
        sanitized_original_filename = sanitize_filename(file.filename)

        # Generate task ID for OCR progress tracking
        task_id = str(uuid.uuid4())

        # Estimate OCR cost based on file size (rough estimate: $0.005 per MB)
        estimated_cost = 0.005 * (len(file_content) / 1024 / 1024)

        # Start progress tracking
        ocr_progress_service.start_progress(task_id, sanitized_original_filename, estimated_cost)

        logger.info(
            "document_upload_started",
            filename=file.filename,
            sanitized_filename=sanitized_original_filename,
            size=len(file_content),
            task_id=task_id
        )

        # Generate unique filename with sanitized extension
        file_extension = Path(sanitized_original_filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info("file_saved", path=str(file_path))

        # Check if file needs OCR
        requires_ocr = needs_ocr(file.content_type, file.filename)

        extracted_text = None
        invoice_data = None
        ocr_metadata = None
        document_type = "document"  # Default type

        if requires_ocr:
            # Use OCR pipeline for images and PDFs
            logger.info("ocr_detection", filename=file.filename, mime_type=file.content_type)

            try:
                # Update progress: Starting OCR extraction
                await ocr_progress_service.update_progress(
                    task_id, 25, "Extraction du texte...", OCRStatus.PROCESSING
                )

                # Initialize OCR services
                ocr_service = OCRAgent()
                # extraction_service = InvoiceExtractionService()  # TODO: Implement this service

                # Step 1: OCR extraction using Mistral Vision (Pixtral)
                result = await ocr_service.process(
                    file_content=file_content,
                    filename=file.filename,
                    content_type=file.content_type,
                    db=db
                )

                if not result.get("success"):
                    raise Exception(result.get("message", "OCR failed"))

                extracted_text = result["data"]["extracted_text"]
                ocr_metadata = result["data"].get("metadata", {})

                logger.info("ocr_completed",
                           method=ocr_metadata.get("method"),
                           text_length=len(extracted_text),
                           pages=ocr_metadata.get("pages"))

                # Update progress: Analyzing document
                await ocr_progress_service.update_progress(
                    task_id, 50, "Analyse de la facture...", OCRStatus.PROCESSING
                )

                # Step 2: Use OCR Agent's metadata extraction instead of separate invoice service
                invoice_data = ocr_metadata
                document_type = result["data"].get("doc_type", "autre")

                # TODO: When InvoiceExtractionService is implemented, use it for detailed extraction
                # if extracted_text:
                #     try:
                #         invoice_data_obj = await extraction_service.extract_invoice_data(
                #             raw_text=extracted_text,
                #             extract_line_items=True,
                #             detect_business=True
                #         )
                #         invoice_data = invoice_data_obj.model_dump(mode='json')
                #         document_type = invoice_data.get("type_document", "facture")
                #     except Exception as e:
                #         logger.warning("invoice_extraction_failed", error=str(e))
                #         invoice_data = None

            except Exception as e:
                # If OCR fails completely, try standard text extraction
                logger.error("ocr_failed", error=str(e))
                doc_service = DocumentService()
                extracted_text, success = await doc_service.extract_text(
                    file_content,
                    file.content_type,
                    file.filename
                )
                if not success:
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=500,
                        detail=f"OCR failed: {str(e)}"
                    )
        else:
            # Standard text extraction for non-OCR documents (DOCX, TXT)
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

        logger.info("text_extraction_complete", length=len(extracted_text) if extracted_text else 0)

        # Create database record with sanitized filename and OCR metadata
        document_metadata = {}
        if invoice_data:
            document_metadata["invoice_data"] = invoice_data
        if ocr_metadata:
            document_metadata["ocr_metadata"] = ocr_metadata

        db_document = Document(
            filename=unique_filename,
            original_filename=sanitized_original_filename,  # Store sanitized version
            file_path=str(file_path),
            file_size=len(file_content),
            mime_type=file.content_type,
            document_type=document_type,  # Store detected document type
            extracted_text=extracted_text,
            document_metadata=document_metadata if document_metadata else None,
            processed=True,
            processed_at=datetime.now()
        )

        db.add(db_document)
        await db.flush()  # Get the ID without committing

        logger.info("document_record_created", document_id=db_document.id)

        # Update progress: Starting indexation
        await ocr_progress_service.update_progress(
            task_id, 75, "Indexation dans la base...", OCRStatus.INDEXING
        )

        # Initialize services for indexation
        doc_service = DocumentService()
        rag_service = RAGService()
        await rag_service.initialize()  # Initialize Qdrant collection

        # INTERGALACTIC MODE: Adaptive chunking based on document type
        def detect_document_type(text: str, filename: str) -> str:
            """
            Classify document type for optimal chunking

            Returns: "invoice" | "legal" | "narrative" | "technical"
            """
            text_lower = text.lower()

            # Invoice indicators
            invoice_keywords = ["facture", "invoice", "devis", "montant", "tva", "total ttc"]
            invoice_score = sum(1 for kw in invoice_keywords if kw in text_lower)

            # Legal indicators
            legal_keywords = ["règlement", "article", "copropriété", "contrat", "clause", "alinéa"]
            legal_score = sum(1 for kw in legal_keywords if kw in text_lower)

            # Filename hints
            if "facture" in filename.lower() or "invoice" in filename.lower():
                return "invoice"
            if "reglement" in filename.lower() or "contrat" in filename.lower():
                return "legal"

            # Text-based classification
            if invoice_score >= 3:
                return "invoice"
            if legal_score >= 3:
                return "legal"

            # Length-based fallback
            if len(text) < 2000:
                return "invoice"  # Short docs likely invoices
            if len(text) > 20000:
                return "legal"    # Long docs likely legal

            return "narrative"  # Default

        doc_type = detect_document_type(extracted_text, db_document.original_filename)

        # Adaptive chunk sizing - optimized for document type
        chunk_config = {
            "invoice": {"size": 800, "overlap": 150},    # Small, focused chunks for invoices
            "legal": {"size": 1200, "overlap": 250},     # Medium chunks for legal docs (structured content)
            "narrative": {"size": 1000, "overlap": 200}, # Balanced for general text
            "technical": {"size": 1000, "overlap": 200}  # Balanced for technical docs
        }

        config = chunk_config[doc_type]

        logger.info("adaptive_chunking_applied",
                   document_id=db_document.id,
                   doc_type=doc_type,
                   chunk_size=config["size"],
                   overlap=config["overlap"],
                   text_length=len(extracted_text))

        # Apply adaptive chunking
        chunks = doc_service.chunk_text(
            extracted_text,
            chunk_size=config["size"],
            overlap=config["overlap"]
        )

        if chunks:
            # Build enhanced metadata for indexation
            index_metadata = {
                "filename": file.filename,
                "original_filename": db_document.original_filename,
                "title": db_document.original_filename,
                "mime_type": file.content_type,
                "document_type": document_type,
                "detected_doc_type": doc_type,  # INTERGALACTIC: Add detected type for adaptive retrieval
                "chunk_size_used": config["size"],  # INTERGALACTIC: Track chunk configuration
                "uploaded_at": datetime.now().isoformat()
            }

            # Add invoice data to metadata for enhanced RAG retrieval
            if invoice_data:
                index_metadata["invoice_numero"] = invoice_data.get("numero")
                index_metadata["invoice_date"] = str(invoice_data.get("date_emission")) if invoice_data.get("date_emission") else None
                index_metadata["invoice_supplier"] = invoice_data.get("fournisseur", {}).get("nom")
                index_metadata["invoice_amount_ttc"] = str(invoice_data.get("montant_ttc")) if invoice_data.get("montant_ttc") else None
                index_metadata["invoice_type"] = invoice_data.get("type_document")
                index_metadata["confidence_score"] = invoice_data.get("confidence_score")

            # Index all chunks with metadata enrichment enabled
            point_ids = await rag_service.index_document_chunks(
                document_id=db_document.id,
                chunks=chunks,
                metadata=index_metadata,
                enrich_metadata=True  # Enable entity extraction, language detection, etc.
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

        # Update progress: Completed!
        await ocr_progress_service.update_progress(
            task_id, 100, "✅ Terminé !", OCRStatus.COMPLETED
        )

        logger.info("document_upload_complete", document_id=db_document.id, task_id=task_id)

        # Update conversation state to track uploaded document
        state_manager = get_state_manager(session_id)
        state_manager.state.add_uploaded_document(
            filename=file.filename,
            document_id=db_document.id,
            mime_type=file.content_type
        )
        logger.info("document_added_to_state",
                   session_id=session_id,
                   document_id=db_document.id,
                   filename=file.filename)

        # Build response with OCR information and task_id
        response = {
            "message": "Document uploaded and indexed successfully",
            "document_id": db_document.id,
            "filename": file.filename,
            "doc_type": document_type,
            "chunks_count": len(chunks),
            "chunks_indexed": len(chunks),
            "indexed": db_document.indexed,
            "text_length": len(extracted_text) if extracted_text else 0,
            "task_id": task_id  # Include task_id for frontend WebSocket connection
        }

        # Add OCR metadata if available
        if ocr_metadata:
            response["ocr"] = {
                "method": ocr_metadata.get("method"),
                "pages": ocr_metadata.get("pages"),
                "cost_estimate": ocr_metadata.get("cost_estimate")
            }

        # Add invoice data if extracted
        if invoice_data:
            response["invoice"] = {
                "type": invoice_data.get("type_document"),
                "numero": invoice_data.get("numero"),
                "supplier": invoice_data.get("fournisseur", {}).get("nom"),
                "amount_ttc": invoice_data.get("montant_ttc"),
                "confidence_score": invoice_data.get("confidence_score")
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        error_traceback = traceback.format_exc()
        logger.error("document_upload_failed", error=str(e), traceback=error_traceback, filename=file.filename)
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
                    "filename": doc.filename,  # UUID filename
                    "original_filename": doc.original_filename,  # User's original filename
                    "mime_type": doc.mime_type,
                    "file_size": doc.file_size,
                    "document_type": doc.document_type if hasattr(doc, 'document_type') else None,
                    "indexed": doc.indexed,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "chunk_count": None,  # TODO: Add chunk count if needed
                    # Include invoice summary if available
                    "invoice_summary": (
                        {
                            "numero": doc.document_metadata.get("invoice_data", {}).get("numero"),
                            "supplier": doc.document_metadata.get("invoice_data", {}).get("fournisseur", {}).get("nom"),
                            "amount_ttc": doc.document_metadata.get("invoice_data", {}).get("montant_ttc"),
                            "confidence": doc.document_metadata.get("invoice_data", {}).get("confidence_score")
                        }
                        if doc.document_metadata and doc.document_metadata.get("invoice_data")
                        else None
                    )
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


@router.post("/export-excel")
async def export_invoices_to_excel(
    request: Request,
    session_id: str = "default",
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Excel export from selected invoices

    Body:
        document_ids: Optional list of document IDs to export (defaults to active documents)
        columns: Optional list of columns to include
        template: Optional template name ("custom", "sage", "quickbooks")

    Returns:
        Excel file as download
    """
    try:
        # Parse JSON body
        body = await request.json()
        document_ids = body.get("document_ids")
        columns = body.get("columns")
        template = body.get("template", "custom")

        # If no document_ids provided, use active documents from state
        if document_ids is None:
            state_manager = get_state_manager(session_id)
            document_ids = state_manager.state.active_document_ids

        if not document_ids or len(document_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="No documents selected. Please select documents first."
            )

        logger.info("excel_export_started",
                   document_count=len(document_ids),
                   template=template)

        # Get documents from database
        result = await db.execute(
            select(Document)
            .where(Document.id.in_(document_ids))
            .order_by(Document.uploaded_at.desc())
        )
        documents = result.scalars().all()

        if not documents:
            raise HTTPException(
                status_code=404,
                detail="No documents found with provided IDs"
            )

        # Extract invoice data from documents
        invoices = []
        for doc in documents:
            if doc.document_metadata and doc.document_metadata.get("invoice_data"):
                invoice_dict = doc.document_metadata["invoice_data"]
                # Convert to InvoiceData object
                invoice_data = InvoiceData(**invoice_dict)
                invoices.append(invoice_data)

        if not invoices:
            raise HTTPException(
                status_code=400,
                detail="No invoice data found in selected documents. Please select documents with invoice data."
            )

        logger.info("invoices_found_for_export", count=len(invoices))

        # Generate Excel
        # TODO: Implement ExcelExportService
        raise HTTPException(status_code=501, detail="Excel export feature not yet implemented. Please create ExcelExportService.")
        # excel_service = ExcelExportService()
        # excel_bytes = await excel_service.export_to_excel(
        #     invoices=invoices,
        #     columns=columns,
        #     template=template,
        #     include_totals=True
        # )

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"factures_export_{timestamp}.xlsx"

        logger.info("excel_export_completed",
                   filename=filename,
                   size_kb=len(excel_bytes) / 1024)

        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("excel_export_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export to Excel: {str(e)}"
        )


@router.websocket("/ws/ocr/{task_id}")
async def ocr_progress_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time OCR progress updates

    The frontend connects to this endpoint after uploading a document
    to receive real-time progress updates during OCR processing.

    Args:
        task_id: Unique task identifier returned by upload endpoint
    """
    await websocket.accept()
    logger.info("websocket_connected", task_id=task_id)

    # Register websocket with progress service
    ocr_progress_service.register_websocket(task_id, websocket)

    try:
        # Send current progress if available
        progress = ocr_progress_service.get_progress(task_id)
        if progress:
            await websocket.send_json(progress)

        # Keep connection alive and listen for messages
        while True:
            # Wait for any message (heartbeat or close signal)
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", task_id=task_id)
    except Exception as e:
        logger.error("websocket_error", task_id=task_id, error=str(e))
    finally:
        # Unregister websocket
        ocr_progress_service.unregister_websocket(task_id, websocket)
        logger.info("websocket_cleaned_up", task_id=task_id)


# ============================================================================
# ROUTES PREMIUM - Extraction et Génération de Tableaux
# ============================================================================

from pydantic import BaseModel
from typing import Dict, Any


class ExtractionTableauxRequest(BaseModel):
    """Requête extraction tableaux depuis document"""
    document_id: int


class GenerationTableauRequest(BaseModel):
    """Requête génération tableau depuis prompt utilisateur"""
    document_id: int
    prompt_utilisateur: str


@router.post("/{document_id}/extraire-tableaux")
async def extraire_tableaux_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Extraire tous les tableaux d'un document

    Utilise AgentGenerationTableaux pour:
    - Détection automatique de tableaux
    - Extraction via Vision (Pixtral) si image disponible
    - Extraction via LLM sur texte en fallback
    - Export JSON/CSV/Excel/Markdown

    Returns:
        Liste de tableaux structurés avec métadonnées
    """
    try:
        from app.services.agents.agent_generation_tableaux import AgentGenerationTableaux

        # Récupérer document
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=404, detail="Document non trouvé")

        logger.info("extraction_tableaux_demarree", document_id=document_id)

        # Initialiser agent
        agent = AgentGenerationTableaux()

        # Extraire tableaux
        tableaux = await agent.extraire_tableaux_depuis_document(
            texte_document=document.extracted_text or "",
            contenu_image=None,  # TODO: Ajouter support image si disponible
            nom_fichier=document.original_filename
        )

        # Sérialiser pour JSON
        resultats = []
        for tableau in tableaux:
            resultats.append({
                "titre": tableau.titre,
                "entetes": tableau.entetes,
                "lignes": tableau.lignes,
                "confiance": tableau.confiance,
                "metadonnees": tableau.metadonnees,
                "exports": {
                    "csv": tableau.vers_csv(),
                    "markdown": tableau.vers_markdown()
                }
            })

        logger.info("extraction_tableaux_terminee",
                   document_id=document_id,
                   nombre_tableaux=len(resultats))

        return {
            "document_id": document_id,
            "nom_fichier": document.original_filename,
            "tableaux": resultats,
            "total_tableaux": len(resultats)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("extraction_tableaux_echouee",
                    document_id=document_id,
                    erreur=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec extraction tableaux: {str(e)}"
        )


@router.post("/{document_id}/generer-tableau")
async def generer_tableau_depuis_prompt(
    document_id: int,
    request: GenerationTableauRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Générer un tableau personnalisé depuis un prompt utilisateur

    FONCTIONNALITÉ PHARE: L'utilisateur dit "fais-moi un tableau avec fournisseur, montant, date"
    et on le génère automatiquement!

    Args:
        document_id: ID du document source
        prompt_utilisateur: Demande utilisateur (ex: "tableau avec fournisseur, montant TTC, date")

    Returns:
        Tableau structuré correspondant à la demande
    """
    try:
        from app.services.agents.agent_generation_tableaux import AgentGenerationTableaux

        # Récupérer document
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=404, detail="Document non trouvé")

        logger.info("generation_tableau_depuis_prompt_demarree",
                   document_id=document_id,
                   prompt=request.prompt_utilisateur[:100])

        # Initialiser agent
        agent = AgentGenerationTableaux()

        # Générer tableau
        tableau = await agent.generer_tableau_depuis_prompt(
            prompt_utilisateur=request.prompt_utilisateur,
            texte_document=document.extracted_text or "",
            contexte={
                "document_id": document_id,
                "nom_fichier": document.original_filename
            }
        )

        logger.info("generation_tableau_terminee",
                   document_id=document_id,
                   nombre_lignes=len(tableau.lignes))

        return {
            "document_id": document_id,
            "prompt_utilisateur": request.prompt_utilisateur,
            "tableau": {
                "titre": tableau.titre,
                "entetes": tableau.entetes,
                "lignes": tableau.lignes,
                "confiance": tableau.confiance,
                "metadonnees": tableau.metadonnees
            },
            "exports": {
                "csv": tableau.vers_csv(),
                "markdown": tableau.vers_markdown()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generation_tableau_echouee",
                    document_id=document_id,
                    erreur=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec génération tableau: {str(e)}"
        )


@router.get("/{document_id}/tableaux/{index}/export-excel")
async def exporter_tableau_excel(
    document_id: int,
    index: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Exporter un tableau spécifique en Excel

    Args:
        document_id: ID du document
        index: Index du tableau (0-based)

    Returns:
        Fichier Excel en StreamingResponse
    """
    try:
        from app.services.agents.agent_generation_tableaux import AgentGenerationTableaux

        # Récupérer document
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=404, detail="Document non trouvé")

        # Extraire tableaux
        agent = AgentGenerationTableaux()
        tableaux = await agent.extraire_tableaux_depuis_document(
            texte_document=document.extracted_text or "",
            nom_fichier=document.original_filename
        )

        if index >= len(tableaux):
            raise HTTPException(
                status_code=404,
                detail=f"Tableau {index} non trouvé (total: {len(tableaux)})"
            )

        tableau = tableaux[index]

        # Générer Excel
        excel_bytes = tableau.vers_bytes_excel()

        # Retourner en streaming
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=tableau_{document_id}_{index}.xlsx"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("export_excel_echoue",
                    document_id=document_id,
                    index=index,
                    erreur=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Échec export Excel: {str(e)}"
        )


# ============================================================================
# ROUTE PREMIUM - Question & Answer sur Documents (RAG)
# ============================================================================

from pydantic import BaseModel

class DocumentQuestionRequest(BaseModel):
    """Requête question sur documents"""
    question: str
    document_ids: Optional[List[int]] = None  # Si None, cherche dans tous les docs
    top_k: Optional[int] = 3  # Nombre de chunks à retourner
    use_reranker: Optional[bool] = True
    use_hybrid: Optional[bool] = True
    use_query_planning: Optional[bool] = False  # Agentic RAG pour questions complexes


@router.post("/ask")
async def poser_question_documents(
    request: DocumentQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Poser une question sur un ou plusieurs documents (RAG Q&A)

    Utilise le RAGService existant avec toutes ses optimisations:
    - Recherche vectorielle (Qdrant + Mistral embeddings)
    - Hybrid search (BM25 + Vector)
    - Reranking (cross-encoder)
    - Query planning (agentic RAG pour questions complexes)
    - Verification & Reflection agents

    Use Cases:
    - "Quel est le montant total des factures ?"
    - "Liste tous les numéros d'appartement mentionnés"
    - "Résume les travaux prévus en 2024"
    - "Qui sont les fournisseurs cités dans les documents ?"

    Args:
        question: Question utilisateur
        document_ids: IDs documents à interroger (optionnel, tous par défaut)
        top_k: Nombre de passages pertinents à retourner
        use_reranker: Activer reranking pour meilleure précision
        use_hybrid: Activer hybrid search (BM25 + vector)
        use_query_planning: Activer agentic RAG pour questions multi-hop

    Returns:
        - question: Question originale
        - reponse: Réponse générée par LLM
        - sources: Passages sources utilisés (avec scores)
        - contexte_complet: Texte complet utilisé pour génération
    """
    try:
        from app.services.rag_service import RAGService
        from app.services.llm_service import LLMService

        logger.info("question_document_recue",
                   question=request.question[:100],
                   document_ids=request.document_ids,
                   top_k=request.top_k)

        # Initialiser services
        rag_service = RAGService()
        await rag_service.initialize()

        llm_service = LLMService()

        # 1. Rechercher passages pertinents avec RAG
        chunks = await rag_service.search(
            query=request.question,
            limit=request.top_k,
            document_ids=request.document_ids,
            use_reranker=request.use_reranker,
            use_hybrid=request.use_hybrid,
            use_query_planning=request.use_query_planning
        )

        if not chunks:
            return {
                "question": request.question,
                "reponse": "Aucune information pertinente trouvée dans les documents disponibles.",
                "sources": [],
                "contexte_complet": "",
                "confiance": 0.0
            }

        # 2. Construire contexte à partir des chunks
        contexte_parts = []
        sources = []

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get('content') or chunk.get('text', '')
            score = chunk.get('reranked_score', chunk.get('score', 0))
            doc_id = chunk.get('document_id')

            contexte_parts.append(f"[Passage {i}]\n{text}\n")

            sources.append({
                "passage_num": i,
                "document_id": doc_id,
                "text": text[:300] + "..." if len(text) > 300 else text,
                "score": round(score, 4),
                "metadata": chunk.get('metadata', {})
            })

        contexte_complet = "\n---\n".join(contexte_parts)

        # 3. Générer réponse avec LLM
        prompt = f"""Tu es un assistant expert en analyse de documents pour la gestion de copropriétés.

Question: {request.question}

Contexte (passages pertinents des documents):
{contexte_complet}

Instructions:
- Réponds de manière précise et concise à la question
- Base-toi UNIQUEMENT sur les passages fournis ci-dessus
- Si l'information n'est pas dans le contexte, dis-le clairement
- Cite les numéros de passages ([Passage X]) quand tu utilises une information
- Pour les montants, dates, noms: cite EXACTEMENT ce qui est écrit
- Si plusieurs éléments sont demandés (ex: liste), structure ta réponse clairement

Réponse:"""

        reponse = await llm_service.generate_response(
            prompt=prompt,
            temperature=0.1,  # Basse température pour précision factuelle
            max_tokens=800
        )

        # 4. Calculer confiance (score moyen des sources)
        confiance = sum(s['score'] for s in sources) / len(sources) if sources else 0.0

        logger.info("reponse_generee",
                   chunks_utilises=len(sources),
                   confiance=confiance,
                   longueur_reponse=len(reponse))

        return {
            "question": request.question,
            "reponse": reponse.strip(),
            "sources": sources,
            "contexte_complet": contexte_complet,
            "confiance": round(confiance, 4),
            "metadata": {
                "chunks_count": len(chunks),
                "reranker_used": request.use_reranker,
                "hybrid_used": request.use_hybrid,
                "query_planning_used": request.use_query_planning
            }
        }

    except Exception as e:
        logger.error("question_document_echouee",
                    question=request.question[:100],
                    erreur=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Échec traitement question: {str(e)}"
        )
