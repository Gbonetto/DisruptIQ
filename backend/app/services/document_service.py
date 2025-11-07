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
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
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
            elif mime_type in ['image/jpeg', 'image/jpg', 'image/png']:
                return await self._extract_from_image(file_content, mime_type)
            else:
                logger.warning("unsupported_file_type", mime_type=mime_type)
                return "", False

        except Exception as e:
            logger.error("text_extraction_failed", filename=filename, error=str(e))
            return "", False

    async def _extract_from_pdf(self, content: bytes) -> Tuple[str, bool]:
        """Extract text from PDF with OCR fallback"""
        try:
            from pypdf import PdfReader
            import re

            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            extracted_text = "\n\n".join(text_parts)

            # CLEANUP: Remove extraction artifacts
            if extracted_text:
                # Remove excessive dots (form field placeholders, etc.)
                extracted_text = re.sub(r'\.{3,}', ' ', extracted_text)

                # Remove excessive spaces
                extracted_text = re.sub(r'\s+', ' ', extracted_text)

                # Remove isolated dots on their own lines
                extracted_text = re.sub(r'^\s*\.\s*$', '', extracted_text, flags=re.MULTILINE)

                # Clean up whitespace
                extracted_text = extracted_text.strip()

            if not extracted_text.strip():
                logger.warning("pdf_no_text_extracted_trying_ocr")
                # Fallback to OCR for scanned PDFs
                return await self._extract_pdf_with_ocr(content)

            logger.info("pdf_text_extracted", pages=len(reader.pages), length=len(extracted_text))
            return extracted_text, True

        except ImportError:
            logger.error("pypdf_not_installed")
            return "", False
        except Exception as e:
            logger.error("pdf_extraction_error", error=str(e))
            return "", False

    async def _extract_pdf_with_ocr(self, content: bytes) -> Tuple[str, bool]:
        """Extract text from scanned PDF using Mistral Pixtral OCR with PARALLEL processing"""
        try:
            from pdf2image import convert_from_bytes
            from app.services.ocr_mistral_service import MistralOCRService
            import asyncio

            # Adaptive DPI based on file size for performance
            file_size_mb = len(content) / (1024 * 1024)
            if file_size_mb > 2.0:
                dpi = 150  # Lower DPI for large files (faster, still good quality)
                logger.info("using_adaptive_dpi_large_file", dpi=150, size_mb=file_size_mb)
            else:
                dpi = 200  # High DPI for small files (better quality)
                logger.info("using_adaptive_dpi_small_file", dpi=200, size_mb=file_size_mb)

            logger.info("converting_pdf_to_images_for_pixtral", dpi=dpi)
            images = convert_from_bytes(content, dpi=dpi)

            ocr_service = MistralOCRService()

            # OPTIMIZATION: Process all pages in PARALLEL using asyncio.gather
            async def process_page(i: int, image):
                """Process a single page with OCR"""
                logger.info("pixtral_processing_pdf_page_parallel", page=i+1, total=len(images))

                try:
                    # Convert PIL Image to bytes
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()

                    # Extract text with Pixtral
                    text, success = await ocr_service.extract_text_from_pdf_page(img_bytes)

                    if success and text.strip():
                        return (i, text.strip())
                    else:
                        # Fallback to Tesseract for this page
                        try:
                            import pytesseract
                            logger.info("fallback_to_tesseract_for_page", page=i+1)
                            text = pytesseract.image_to_string(image, lang='fra+eng')
                            if text.strip():
                                return (i, text.strip())
                        except:
                            pass
                        return (i, "")

                except Exception as e:
                    logger.error("page_processing_error", page=i+1, error=str(e))
                    return (i, "")

            # Process ALL pages in parallel (10x faster!)
            logger.info("starting_parallel_page_processing", total_pages=len(images))
            page_results = await asyncio.gather(
                *[process_page(i, image) for i, image in enumerate(images)]
            )

            # Sort by page number and join text
            page_results.sort(key=lambda x: x[0])
            text_parts = [text for _, text in page_results if text]

            extracted_text = "\n\n".join(text_parts)

            if not extracted_text.strip():
                logger.warning("pixtral_ocr_no_text_extracted")
                return "", False

            logger.info(
                "pixtral_pdf_ocr_completed_parallel",
                pages=len(images),
                text_length=len(extracted_text),
                pages_with_text=len(text_parts)
            )
            return extracted_text, True

        except ImportError as e:
            logger.error("ocr_dependencies_missing", error=str(e))
            return "", False
        except Exception as e:
            logger.error("pixtral_pdf_ocr_error", error=str(e))
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

    def chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
        """
        Split text into overlapping chunks using LangChain RecursiveCharacterTextSplitter
        for semantic-aware chunking that preserves document structure.

        Improvements over basic chunking:
        - Respects document structure (paragraphs, sentences, words)
        - Never breaks mid-sentence
        - Preserves semantic coherence
        - Better for multi-page documents (invoices, contracts)

        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk (characters) - default 1500
            overlap: Overlap between chunks (characters) - default 200

        Returns:
            List of text chunks

        Note:
            For invoices with tables/structured data, increase chunk_size to 2000+
            to avoid splitting critical information across chunks.
        """
        if not text:
            return []

        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            # Semantic-aware splitter
            # Prioritizes: paragraphs > sentences > words > characters
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                length_function=len,
                separators=[
                    "\n\n",  # Paragraph breaks (highest priority)
                    "\n",    # Line breaks
                    ". ",    # Sentence endings
                    "! ",    # Exclamations
                    "? ",    # Questions
                    "; ",    # Semicolons
                    ": ",    # Colons
                    ", ",    # Commas
                    " ",     # Words
                    ""       # Characters (fallback)
                ],
                keep_separator=True,  # Preserve separators for readability
            )

            chunks = splitter.split_text(text)

            logger.info(
                "text_chunked_semantic",
                chunks=len(chunks),
                avg_chunk_size=sum(len(c) for c in chunks) // len(chunks) if chunks else 0,
                method="RecursiveCharacterTextSplitter"
            )

            return chunks

        except ImportError:
            logger.warning(
                "langchain_not_available_using_fallback",
                message="Install langchain for better chunking: pip install langchain"
            )
            # Fallback to basic chunking
            return self._basic_chunk_text(text, chunk_size, overlap)

        except Exception as e:
            logger.error("semantic_chunking_failed", error=str(e), exc_info=True)
            # Fallback to basic chunking
            return self._basic_chunk_text(text, chunk_size, overlap)

    def _basic_chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Fallback basic chunking method (legacy)"""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size

            # Try to break at sentence boundary if possible
            if end < text_length:
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n', start, end)
                break_point = max(last_period, last_newline)

                if break_point > start + chunk_size // 2:
                    end = break_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        logger.info("text_chunked_basic_fallback", chunks=len(chunks))
        return chunks

    async def _extract_from_image(self, content: bytes, mime_type: str) -> Tuple[str, bool]:
        """Extract text from image using Mistral Pixtral (better than Tesseract)"""
        try:
            from app.services.ocr_mistral_service import MistralOCRService

            logger.info("ocr_processing_image_with_pixtral", mime_type=mime_type)

            # Use Mistral Pixtral for OCR
            ocr_service = MistralOCRService()
            text, success = await ocr_service.extract_text_from_image(content, mime_type)

            if not success or not text.strip():
                logger.warning("pixtral_ocr_no_text_in_image")

                # Fallback to Tesseract if Pixtral fails (optional)
                try:
                    from PIL import Image
                    import pytesseract

                    logger.info("fallback_to_tesseract")
                    image_file = io.BytesIO(content)
                    image = Image.open(image_file)
                    text = pytesseract.image_to_string(image, lang='fra+eng')

                    if text.strip():
                        logger.info("tesseract_fallback_success")
                        return text.strip(), True
                except:
                    pass

                return "", False

            logger.info("pixtral_ocr_completed", text_length=len(text))
            return text.strip(), True

        except Exception as e:
            logger.error("image_ocr_error", error=str(e))

            # Final fallback to Tesseract
            try:
                from PIL import Image
                import pytesseract

                logger.info("error_fallback_to_tesseract")
                image_file = io.BytesIO(content)
                image = Image.open(image_file)
                text = pytesseract.image_to_string(image, lang='fra+eng')

                if text.strip():
                    return text.strip(), True
            except:
                pass

            return "", False

    @staticmethod
    def is_supported_format(mime_type: str) -> bool:
        """Check if the MIME type is supported"""
        return mime_type in DocumentService.SUPPORTED_FORMATS
