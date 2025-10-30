"""
Document Processing Service
Handles text extraction from various document formats
"""

import structlog
from typing import Optional, Tuple
import io
from pathlib import Path

logger = structlog.get_logger()


class DocumentService:
    """Service for document text extraction"""

    SUPPORTED_FORMATS = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/msword': '.doc',
        'text/plain': '.txt',
    }

    async def extract_text(self, file_content: bytes, mime_type: str, filename: str) -> Tuple[str, bool]:
        """
        Extract text from document

        Args:
            file_content: File content as bytes
            mime_type: MIME type of the file
            filename: Original filename

        Returns:
            Tuple of (extracted_text, success)
        """
        try:
            if mime_type == 'application/pdf':
                return await self._extract_from_pdf(file_content)
            elif mime_type in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword'
            ]:
                return await self._extract_from_docx(file_content, mime_type)
            elif mime_type == 'text/plain':
                return await self._extract_from_txt(file_content)
            else:
                logger.warning("unsupported_file_type", mime_type=mime_type)
                return "", False

        except Exception as e:
            logger.error("text_extraction_failed", filename=filename, error=str(e))
            return "", False

    async def _extract_from_pdf(self, content: bytes) -> Tuple[str, bool]:
        """Extract text from PDF"""
        try:
            from pypdf import PdfReader

            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            extracted_text = "\n\n".join(text_parts)

            if not extracted_text.strip():
                logger.warning("pdf_no_text_extracted_might_need_ocr")
                # TODO: Implement OCR fallback with Tesseract if needed
                return "", False

            logger.info("pdf_text_extracted", pages=len(reader.pages))
            return extracted_text, True

        except ImportError:
            logger.error("pypdf_not_installed")
            return "", False
        except Exception as e:
            logger.error("pdf_extraction_error", error=str(e))
            return "", False

    async def _extract_from_docx(self, content: bytes, mime_type: str) -> Tuple[str, bool]:
        """Extract text from DOCX/DOC"""
        try:
            from docx import Document as DocxDocument

            doc_file = io.BytesIO(content)
            doc = DocxDocument(doc_file)

            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    text_parts.append(paragraph.text)

            extracted_text = "\n\n".join(text_parts)

            logger.info("docx_text_extracted", paragraphs=len(doc.paragraphs))
            return extracted_text, True

        except ImportError:
            logger.error("python_docx_not_installed")
            return "", False
        except Exception as e:
            logger.error("docx_extraction_error", error=str(e))
            return "", False

    async def _extract_from_txt(self, content: bytes) -> Tuple[str, bool]:
        """Extract text from plain text file"""
        try:
            # Try multiple encodings
            encodings = ['utf-8', 'iso-8859-1', 'windows-1252', 'cp1252']

            for encoding in encodings:
                try:
                    text = content.decode(encoding)
                    logger.info("txt_text_extracted", encoding=encoding)
                    return text, True
                except UnicodeDecodeError:
                    continue

            logger.error("txt_decoding_failed_all_encodings")
            return "", False

        except Exception as e:
            logger.error("txt_extraction_error", error=str(e))
            return "", False

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """
        Split text into overlapping chunks for better retrieval

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk (characters)
            overlap: Overlap between chunks (characters)

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size

            # Try to break at sentence boundary if possible
            if end < text_length:
                # Look for sentence ending in the last 100 chars
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n', start, end)
                break_point = max(last_period, last_newline)

                if break_point > start + chunk_size // 2:
                    end = break_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        logger.info("text_chunked", chunks=len(chunks))
        return chunks

    @staticmethod
    def is_supported_format(mime_type: str) -> bool:
        """Check if the MIME type is supported"""
        return mime_type in DocumentService.SUPPORTED_FORMATS
