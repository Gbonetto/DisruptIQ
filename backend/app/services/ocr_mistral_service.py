"""
Mistral Vision OCR Service
Provides OCR capabilities using Mistral's Pixtral multimodal model
"""

import structlog
import base64
from typing import Tuple, List
from app.core.config import settings

logger = structlog.get_logger()


class MistralOCRService:
    """
    OCR Service using Mistral Vision (Pixtral-12B) for document text extraction

    Capabilities:
    - Extract text from images (PNG, JPG, JPEG, TIFF, BMP)
    - Extract text from PDF pages (converted to images)
    - Multi-language support (French + English)
    - Table and complex layout recognition
    - Better accuracy than traditional OCR for complex documents
    - OPTIMIZED: Reuses model instance for better performance
    """

    def __init__(self):
        """Initialize with shared model instance for performance"""
        self._vision_model = None

    def _get_vision_model(self):
        """Get or create vision model instance (singleton pattern for performance)"""
        if self._vision_model is None:
            from langchain_mistralai import ChatMistralAI
            self._vision_model = ChatMistralAI(
                model=settings.MISTRAL_VISION_MODEL,  # pixtral-12b-2409
                api_key=settings.MISTRAL_API_KEY,
                temperature=0.0,  # Deterministic for OCR
                max_retries=2,  # Faster failure for batch processing
                timeout=60,  # 60s timeout per page
            )
        return self._vision_model

    async def extract_text_from_image(
        self,
        image_content: bytes,
        content_type: str = "image/jpeg"
    ) -> Tuple[str, bool]:
        """
        Extract text from image using Mistral Vision (Pixtral)

        Args:
            image_content: Image content as bytes
            content_type: MIME type of the image

        Returns:
            Tuple of (extracted_text, success_flag)
        """
        try:
            # Encode image to base64 for Mistral API
            image_base64 = base64.b64encode(image_content).decode('utf-8')

            # Use cached model instance
            from langchain.schema import HumanMessage
            vision_model = self._get_vision_model()

            # Create multimodal message with image
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": """Analyse cette image et extrait tout le texte visible avec une grande précision.

Instructions :
- Extrait TOUT le texte, y compris les petits caractères
- Conserve la structure (titres, paragraphes, listes)
- Pour les tableaux, utilise des tabulations pour séparer les colonnes
- Préserve les nombres, dates et montants avec précision
- Si du texte est manuscrit, fais de ton mieux pour le déchiffrer
- Ne traduis RIEN, garde le texte dans sa langue d'origine

Retourne uniquement le texte extrait, sans commentaires."""
                    },
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            )

            # Invoke Mistral Vision
            response = await vision_model.ainvoke([message])
            extracted_text = response.content

            logger.info(
                "mistral_vision_ocr_success",
                text_length=len(extracted_text),
                model=settings.MISTRAL_VISION_MODEL
            )

            return extracted_text, True

        except Exception as e:
            logger.error("mistral_vision_ocr_error", error=str(e), exc_info=True)
            return "", False

    async def extract_text_from_pdf_page(
        self,
        image_content: bytes
    ) -> Tuple[str, bool]:
        """
        Extract text from a single PDF page (rendered as image)

        Args:
            image_content: PDF page rendered as image bytes (PNG format)

        Returns:
            Tuple of (extracted_text, success_flag)
        """
        # Same as extract_text_from_image but specific to PDF pages
        return await self.extract_text_from_image(image_content, "image/png")
