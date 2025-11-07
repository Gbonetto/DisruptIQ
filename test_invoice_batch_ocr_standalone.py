"""
Batterie de Tests Complète - OCR Factures Multi-Pages (STANDALONE)

Ce script teste l'ensemble du pipeline OCR + Chunking + Enrichissement SANS base de données:
1. OCR avec Mistral Vision (Pixtral) - toutes les pages
2. Chunking sémantique (RecursiveCharacterTextSplitter)
3. Enrichissement métadonnées (entités, dates, montants)

Dossier: C:\\Users\\grego\\Desktop\\FacturesOCR
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.ocr_mistral_service import MistralOCRService
from app.services.document_service import DocumentService
from app.services.metadata_enrichment_service import get_metadata_enrichment_service
import structlog

logger = structlog.get_logger()

# Configuration
INVOICES_DIR = r"C:\Users\grego\Desktop\FacturesOCR"
RESULTS_FILE = "invoice_ocr_test_results_standalone.json"


class InvoiceBatchTesterStandalone:
    """Testeur de lot pour factures OCR (sans DB)"""

    def __init__(self):
        self.ocr_service = MistralOCRService()
        self.document_service = DocumentService()
        self.metadata_enricher = get_metadata_enrichment_service()
        self.results = []

    async def process_invoice(
        self,
        file_path: Path
    ) -> dict:
        """
        Process a single invoice file (peut être multi-pages)

        Args:
            file_path: Path to invoice file

        Returns:
            Test result dictionary
        """
        start_time = datetime.now()
        result = {
            "filename": file_path.name,
            "file_path": str(file_path),
            "file_size_kb": file_path.stat().st_size / 1024,
            "status": "pending",
            "error": None,
            "processing_time_seconds": 0,
            "pages_processed": 0,
            "text_length": 0,
            "chunks_created": 0,
            "entities_extracted": {},
            "metadata": {},
        }

        try:
            # Read file
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Determine content type
            content_type = self._get_content_type(file_path.suffix)

            logger.info(
                "processing_invoice",
                filename=file_path.name,
                size_kb=result["file_size_kb"]
            )

            # Step 1: OCR with Mistral Vision (handles multi-page PDFs)
            if file_path.suffix.lower() == ".pdf":
                # Multi-page PDF handling
                from pdf2image import convert_from_bytes

                logger.info("converting_pdf_to_images", filename=file_path.name)
                images = convert_from_bytes(file_content, dpi=200)

                text_parts = []
                for i, image in enumerate(images):
                    logger.info("processing_pdf_page", page=i+1, total=len(images))

                    # Convert PIL Image to bytes
                    import io
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()

                    # Extract text with Pixtral
                    text, success = await self.ocr_service.extract_text_from_pdf_page(img_bytes)

                    if success and text.strip():
                        text_parts.append(text.strip())

                extracted_text = "\n\n".join(text_parts)
                result["pages_processed"] = len(images)

            elif file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".tiff"]:
                # Single image
                extracted_text, success = await self.ocr_service.extract_text_from_image(
                    file_content,
                    content_type
                )
                result["pages_processed"] = 1

                if not success:
                    result["status"] = "failed"
                    result["error"] = "OCR failed for image"
                    return result
            else:
                result["status"] = "failed"
                result["error"] = f"Unsupported file type: {file_path.suffix}"
                return result

            result["text_length"] = len(extracted_text)

            # Step 2: Chunk with RecursiveCharacterTextSplitter
            chunks = self.document_service.chunk_text(
                extracted_text,
                chunk_size=2000,  # Augmenté pour factures avec tableaux
                overlap=300
            )
            result["chunks_created"] = len(chunks)

            # Step 3: Enrich metadata (from first chunk as sample)
            if chunks:
                enriched = self.metadata_enricher.enrich(
                    text=chunks[0],
                    basic_metadata={"filename": file_path.name}
                )
                result["entities_extracted"] = enriched.get("entities", {})
                result["language"] = enriched.get("language", "unknown")
                result["content_type"] = enriched.get("content_type", "unknown")
                result["keywords"] = enriched.get("keywords", [])

            # Success
            result["status"] = "success"
            logger.info(
                "invoice_processed_successfully",
                filename=file_path.name,
                text_length=result["text_length"],
                chunks=result["chunks_created"]
            )

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(
                "invoice_processing_error",
                filename=file_path.name,
                error=str(e),
                exc_info=True
            )

        finally:
            # Calculate processing time
            end_time = datetime.now()
            result["processing_time_seconds"] = (end_time - start_time).total_seconds()

        return result

    def _get_content_type(self, suffix: str) -> str:
        """Get MIME type from file extension"""
        mapping = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp"
        }
        return mapping.get(suffix.lower(), "application/octet-stream")

    async def run_batch_test(self):
        """Run batch test on all invoices in directory"""
        try:
            # Check directory exists
            invoices_path = Path(INVOICES_DIR)
            if not invoices_path.exists():
                print(f"❌ Directory not found: {INVOICES_DIR}")
                return

            # Get all invoice files
            invoice_files = []
            for ext in [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]:
                invoice_files.extend(list(invoices_path.glob(f"*{ext}")))
                invoice_files.extend(list(invoices_path.glob(f"*{ext.upper()}")))

            if not invoice_files:
                print(f"❌ No invoice files found in {INVOICES_DIR}")
                return

            print(f"\n{'='*80}")
            print(f"🚀 BATCH OCR TEST (STANDALONE) - {len(invoice_files)} factures")
            print(f"{'='*80}\n")

            # Process each invoice
            for idx, file_path in enumerate(invoice_files, 1):
                print(f"\n📄 [{idx}/{len(invoice_files)}] Processing: {file_path.name}")
                print(f"   Size: {file_path.stat().st_size / 1024:.1f} KB")

                result = await self.process_invoice(file_path)
                self.results.append(result)

                # Print immediate result
                if result["status"] == "success":
                    print(f"   ✅ SUCCESS")
                    print(f"   ⏱️  Time: {result['processing_time_seconds']:.2f}s")
                    print(f"   📄 Pages: {result['pages_processed']}")
                    print(f"   📝 Text: {result['text_length']} chars")
                    print(f"   🧩 Chunks: {result['chunks_created']}")
                    print(f"   🏷️  Content Type: {result.get('content_type', 'unknown')}")
                    print(f"   🌐 Language: {result.get('language', 'unknown')}")

                    # Show extracted entities
                    entities = result.get("entities_extracted", {})
                    if entities:
                        print(f"   🔍 Entities:")
                        for entity_type, values in entities.items():
                            if values:
                                print(f"      - {entity_type}: {len(values)} found")
                                if entity_type in ["amounts", "dates"]:
                                    print(f"        {values[:3]}")  # Show first 3

                else:
                    print(f"   ❌ FAILED: {result.get('error', 'Unknown error')}")

            # Generate summary report
            await self.generate_report()

        except Exception as e:
            logger.error("batch_test_failed", error=str(e), exc_info=True)
            print(f"\n❌ Batch test failed: {e}")

    async def generate_report(self):
        """Generate comprehensive test report"""
        print(f"\n{'='*80}")
        print("📊 TEST SUMMARY REPORT")
        print(f"{'='*80}\n")

        # Overall stats
        total = len(self.results)
        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = total - successful

        print(f"Total invoices: {total}")
        print(f"✅ Successful: {successful} ({successful/total*100:.1f}%)")
        print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")

        if successful > 0:
            # Processing time stats
            success_results = [r for r in self.results if r["status"] == "success"]
            avg_time = sum(r["processing_time_seconds"] for r in success_results) / successful
            total_time = sum(r["processing_time_seconds"] for r in success_results)

            print(f"\n⏱️  Processing Time:")
            print(f"   Total: {total_time:.2f}s")
            print(f"   Average: {avg_time:.2f}s per invoice")
            print(f"   Min: {min(r['processing_time_seconds'] for r in success_results):.2f}s")
            print(f"   Max: {max(r['processing_time_seconds'] for r in success_results):.2f}s")

            # Text extraction stats
            total_text = sum(r["text_length"] for r in success_results)
            avg_text = total_text / successful

            print(f"\n📝 Text Extraction:")
            print(f"   Total: {total_text:,} chars")
            print(f"   Average: {avg_text:,.0f} chars per invoice")

            # Chunking stats
            total_chunks = sum(r["chunks_created"] for r in success_results)
            avg_chunks = total_chunks / successful

            print(f"\n🧩 Chunking:")
            print(f"   Total: {total_chunks} chunks")
            print(f"   Average: {avg_chunks:.1f} chunks per invoice")

            # Entity extraction stats
            all_entities = {}
            for result in success_results:
                entities = result.get("entities_extracted", {})
                for entity_type, values in entities.items():
                    if entity_type not in all_entities:
                        all_entities[entity_type] = 0
                    all_entities[entity_type] += len(values)

            if all_entities:
                print(f"\n🔍 Entity Extraction (total across all invoices):")
                for entity_type, count in sorted(all_entities.items(), key=lambda x: x[1], reverse=True):
                    if count > 0:
                        print(f"   - {entity_type}: {count}")

        # Failed invoices details
        if failed > 0:
            print(f"\n❌ Failed Invoices:")
            for result in self.results:
                if result["status"] != "success":
                    print(f"   - {result['filename']}: {result.get('error', 'Unknown error')}")

        # Save results to JSON
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "total_invoices": total,
                "successful": successful,
                "failed": failed,
                "results": self.results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed results saved to: {RESULTS_FILE}")
        print(f"\n{'='*80}\n")


async def main():
    """Main test runner"""
    tester = InvoiceBatchTesterStandalone()
    await tester.run_batch_test()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🎯 DISRUPTIQ - BATCH INVOICE OCR TEST (STANDALONE)")
    print("="*80)
    print(f"📁 Invoices Directory: {INVOICES_DIR}")
    print(f"🤖 OCR Engine: Mistral Vision (Pixtral-12B)")
    print(f"✂️  Chunking: RecursiveCharacterTextSplitter (semantic)")
    print(f"🏷️  Metadata: Enriched (entities, dates, amounts, language)")
    print("="*80 + "\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        raise
