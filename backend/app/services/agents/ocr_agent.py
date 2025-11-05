"""
OCR Agent - Document Ingestion and Processing
Extracts text and metadata from PDF and image files
"""

import structlog
import io
import re
from typing import Dict, Any, List, Optional, BinaryIO
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image
import pytesseract
from pypdf import PdfReader

from app.services.llm_service import LLMService
from app.services.rag_service import get_rag_service
from app.models.document import Document

logger = structlog.get_logger()


class OCRAgent:
    """
    OCR Agent for document ingestion

    Capabilities:
    - Extract text from PDF files
    - Extract text from images (PNG, JPG, JPEG)
    - Classify document type (facture, contrat, règlement, etc.)
    - Extract key metadata (dates, amounts, entities)
    - Store in RAG system for semantic search
    - Persist document records in database

    Technologies:
    - PyTesseract for OCR
    - pypdf for PDF text extraction
    - GPT-4 for metadata extraction and classification
    - Qdrant for vector storage
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = get_rag_service()

        # Document type classification
        self.document_types = [
            "facture",
            "devis",
            "contrat",
            "règlement",
            "procès-verbal",
            "convocation",
            "courrier",
            "rapport",
            "autre"
        ]

    async def process(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        db: AsyncSession,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a document file

        Args:
            file_content: Binary file content
            filename: Original filename
            content_type: MIME type
            db: Database session
            user_context: Optional context from user

        Returns:
            Dict with success, extracted_text, metadata, document_id
        """
        try:
            logger.info("ocr_agent_processing", filename=filename, content_type=content_type)

            # Step 1: Extract text based on file type
            extracted_text = await self._extract_text(file_content, filename, content_type)

            if not extracted_text or len(extracted_text.strip()) < 10:
                return {
                    "success": False,
                    "message": "Impossible d'extraire du texte du document. Le document est peut-être vide ou illisible.",
                    "extracted_text": extracted_text
                }

            logger.info("text_extracted", text_length=len(extracted_text))

            # Step 2: Classify document type
            doc_type = await self._classify_document(extracted_text)
            logger.info("document_classified", type=doc_type)

            # Step 3: Extract metadata
            metadata = await self._extract_metadata(extracted_text, doc_type)
            logger.info("metadata_extracted", metadata=metadata)

            # Step 4: Store in RAG system
            await self.rag_service.initialize()
            doc_id = await self._store_in_rag(
                text=extracted_text,
                filename=filename,
                doc_type=doc_type,
                metadata=metadata
            )
            logger.info("stored_in_rag", doc_id=doc_id)

            # Step 5: Persist in database
            db_document = await self._persist_in_db(
                db=db,
                filename=filename,
                file_path=filename,  # In production, store in S3/MinIO
                doc_type=doc_type,
                extracted_text=extracted_text,
                metadata=metadata
            )
            logger.info("persisted_in_db", document_id=db_document.id)

            return {
                "success": True,
                "message": f"Document '{filename}' traité avec succès. Type identifié : {doc_type}",
                "data": {
                    "document_id": db_document.id,
                    "filename": filename,
                    "doc_type": doc_type,
                    "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
                    "text_length": len(extracted_text),
                    "metadata": metadata,
                    "rag_doc_id": doc_id
                }
            }

        except Exception as e:
            logger.error("ocr_agent_error", error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"Erreur lors du traitement du document : {str(e)}"
            }

    async def _extract_text(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Extract text from PDF or image"""
        try:
            filename_lower = filename.lower()

            # PDF extraction
            if content_type == 'application/pdf' or filename_lower.endswith('.pdf'):
                return await self._extract_text_from_pdf(file_content)

            # Image extraction (PNG, JPG, JPEG)
            elif content_type.startswith('image/') or filename_lower.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                return await self._extract_text_from_image(file_content)

            else:
                raise ValueError(f"Type de fichier non supporté : {content_type}")

        except Exception as e:
            logger.error("text_extraction_failed", error=str(e))
            raise

    async def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF using pypdf"""
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PdfReader(pdf_file)

            text_parts = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            full_text = "\n\n".join(text_parts)

            # If PDF text extraction failed or returned very little, try OCR on images
            if len(full_text.strip()) < 50:
                logger.info("pdf_text_extraction_failed_trying_ocr")
                # TODO: Convert PDF pages to images and run OCR
                # For now, return what we have
                return full_text

            return full_text

        except Exception as e:
            logger.error("pdf_extraction_error", error=str(e))
            raise

    async def _extract_text_from_image(self, file_content: bytes) -> str:
        """Extract text from image using Tesseract OCR"""
        try:
            image = Image.open(io.BytesIO(file_content))

            # Run OCR
            text = pytesseract.image_to_string(image, lang='fra+eng')  # French + English

            return text

        except Exception as e:
            logger.error("image_ocr_error", error=str(e))
            raise

    async def _classify_document(self, text: str) -> str:
        """Classify document type using LLM"""
        try:
            prompt = f"""
Tu es un expert en classification de documents pour la gestion immobilière.

Analyse le texte suivant et détermine le type de document parmi ces catégories :
{', '.join(self.document_types)}

TEXTE DU DOCUMENT :
{text[:2000]}  # Limite à 2000 caractères pour éviter les tokens excessifs

Réponds UNIQUEMENT avec le type de document (un seul mot). Ne donne aucune explication.
"""

            response = await self.llm_service.generate(
                prompt=prompt,
                temperature=0.0,
                max_tokens=50
            )

            doc_type = response.strip().lower()

            # Validate response
            if doc_type in self.document_types:
                return doc_type
            else:
                # Default to "autre" if classification failed
                logger.warning("document_classification_failed", response=doc_type)
                return "autre"

        except Exception as e:
            logger.error("document_classification_error", error=str(e))
            return "autre"

    async def _extract_metadata(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract metadata from document using LLM"""
        try:
            prompt = f"""
Tu es un expert en extraction d'informations à partir de documents.

Le document est de type : {doc_type}

Analyse le texte suivant et extrait les métadonnées suivantes au format JSON :
- dates : liste des dates trouvées (format ISO 8601)
- montants : liste des montants trouvés (avec devise)
- entités : liste des personnes, entreprises ou organisations mentionnées
- numéro_document : numéro de facture/contrat/etc si présent
- description : résumé en une phrase (max 100 caractères)

TEXTE DU DOCUMENT :
{text[:3000]}

Réponds UNIQUEMENT avec un objet JSON valide. Exemple :
{{
  "dates": ["2024-01-15"],
  "montants": ["1500.00 EUR", "TTC: 1800.00 EUR"],
  "entités": ["Société ABC", "Jean Dupont"],
  "numéro_document": "F-2024-001",
  "description": "Facture de travaux de plomberie"
}}
"""

            response = await self.llm_service.generate(
                prompt=prompt,
                temperature=0.0,
                max_tokens=500
            )

            # Parse JSON response
            import json
            try:
                metadata = json.loads(response)
                return metadata
            except json.JSONDecodeError:
                # Try to extract JSON from response if wrapped in markdown
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    metadata = json.loads(match.group())
                    return metadata
                else:
                    logger.warning("metadata_extraction_failed_invalid_json", response=response[:200])
                    return {}

        except Exception as e:
            logger.error("metadata_extraction_error", error=str(e))
            return {}

    async def _store_in_rag(
        self,
        text: str,
        filename: str,
        doc_type: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Store document in RAG system (Qdrant)"""
        try:
            # Add document to RAG with metadata
            doc_id = await self.rag_service.add_document(
                text=text,
                metadata={
                    "filename": filename,
                    "doc_type": doc_type,
                    "uploaded_at": datetime.now().isoformat(),
                    **metadata
                }
            )

            return doc_id

        except Exception as e:
            logger.error("rag_storage_error", error=str(e))
            raise

    async def _persist_in_db(
        self,
        db: AsyncSession,
        filename: str,
        file_path: str,
        doc_type: str,
        extracted_text: str,
        metadata: Dict[str, Any]
    ) -> Document:
        """Persist document record in PostgreSQL"""
        try:
            document = Document(
                filename=filename,
                file_path=file_path,
                file_type=doc_type,
                content=extracted_text,
                metadata=metadata,
                is_indexed=True,
                indexed_at=datetime.now()
            )

            db.add(document)
            await db.commit()
            await db.refresh(document)

            return document

        except Exception as e:
            logger.error("db_persistence_error", error=str(e))
            await db.rollback()
            raise
