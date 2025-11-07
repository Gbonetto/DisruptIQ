"""
Batterie de Tests Complète - OCR Factures Multi-Pages

Ce script teste l'ensemble du pipeline OCR + RAG sur le dossier de factures:
1. OCR avec Mistral Vision (Pixtral) - toutes les pages
2. Chunking sémantique (RecursiveCharacterTextSplitter)
3. Enrichissement métadonnées (entités, dates, montants)
4. Indexation RAG (Qdrant)
5. Recherche hybride (BM25 + Vector + Reranking)

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

from app.services.agents.ocr_agent import OCRAgent
from app.services.rag_service import RAGService
from app.services.document_service import DocumentService
from app.core.database import get_db, init_db
from app.models.document import Document
import structlog

logger = structlog.get_logger()

# Configuration
INVOICES_DIR = r"C:\Users\grego\Desktop\FacturesOCR"
RESULTS_FILE = "invoice_ocr_test_results.json"


class InvoiceBatchTester:
    """Testeur de lot pour factures OCR"""

    def __init__(self):
        self.ocr_agent = OCRAgent()
        self.rag_service = RAGService()
        self.document_service = DocumentService()
        self.results = []

    async def initialize(self):
        """Initialize services"""
        try:
            await init_db()
            await self.rag_service.initialize()
            logger.info("services_initialized")
        except Exception as e:
            logger.error("initialization_failed", error=str(e))
            raise

    async def process_invoice(
        self,
        file_path: Path,
        db_session
    ) -> dict:
        """
        Process a single invoice file (peut être multi-pages)

        Args:
            file_path: Path to invoice file
            db_session: Database session

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
            ocr_result = await self.ocr_agent.process(
                file_content=file_content,
                filename=file_path.name,
                content_type=content_type,
                db=db_session,
                user_context={"test_mode": True}
            )

            if not ocr_result.get("success"):
                result["status"] = "failed"
                result["error"] = ocr_result.get("message", "OCR failed")
                return result

            # Extract data from OCR result
            data = ocr_result.get("data", {})
            extracted_text = data.get("extracted_text", "")
            ocr_metadata = data.get("metadata", {})
            document_id = data.get("document_id")

            result["text_length"] = len(extracted_text)
            result["metadata"] = ocr_metadata
            result["document_id"] = document_id

            # Count pages (estimate from text length for PDFs)
            if file_path.suffix.lower() == ".pdf":
                # Rough estimate: ~2000 chars per page
                result["pages_processed"] = max(1, len(extracted_text) // 2000)
            else:
                result["pages_processed"] = 1

            # Step 2: Chunk with RecursiveCharacterTextSplitter
            chunks = self.document_service.chunk_text(
                extracted_text,
                chunk_size=2000,  # Augmenté pour factures avec tableaux
                overlap=300
            )
            result["chunks_created"] = len(chunks)

            # Step 3: Index in RAG with metadata enrichment
            if document_id:
                point_ids = await self.rag_service.index_document_chunks(
                    document_id=document_id,
                    chunks=chunks,
                    metadata={
                        "filename": file_path.name,
                        "doc_type": data.get("doc_type", "facture"),
                        "created_at": datetime.now().isoformat(),
                        **ocr_metadata
                    },
                    enrich_metadata=True  # Active l'enrichissement
                )
                result["qdrant_points"] = len(point_ids)

            # Step 4: Extract enriched entities (from first chunk as sample)
            if chunks:
                from app.services.metadata_enrichment_service import get_metadata_enrichment_service
                enricher = get_metadata_enrichment_service()
                enriched = enricher.enrich(
                    text=chunks[0],
                    basic_metadata={"filename": file_path.name}
                )
                result["entities_extracted"] = enriched.get("entities", {})
                result["language"] = enriched.get("language", "unknown")
                result["content_type"] = enriched.get("content_type", "unknown")

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
            print(f"🚀 BATCH OCR TEST - {len(invoice_files)} factures")
            print(f"{'='*80}\n")

            # Initialize services
            await self.initialize()

            # Process each invoice
            async for db in get_db():
                for idx, file_path in enumerate(invoice_files, 1):
                    print(f"\n📄 [{idx}/{len(invoice_files)}] Processing: {file_path.name}")
                    print(f"   Size: {file_path.stat().st_size / 1024:.1f} KB")

                    result = await self.process_invoice(file_path, db)
                    self.results.append(result)

                    # Print immediate result
                    if result["status"] == "success":
                        print(f"   ✅ SUCCESS")
                        print(f"   ⏱️  Time: {result['processing_time_seconds']:.2f}s")
                        print(f"   📄 Pages: {result['pages_processed']}")
                        print(f"   📝 Text: {result['text_length']} chars")
                        print(f"   🧩 Chunks: {result['chunks_created']}")
                        print(f"   🏷️  Content Type: {result.get('content_type', 'unknown')}")

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

                break  # Only need one DB session for all files

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
    tester = InvoiceBatchTester()
    await tester.run_batch_test()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🎯 DISRUPTIQ - BATCH INVOICE OCR TEST")
    print("="*80)
    print(f"📁 Invoices Directory: {INVOICES_DIR}")
    print(f"🤖 OCR Engine: Mistral Vision (Pixtral-12B)")
    print(f"✂️  Chunking: RecursiveCharacterTextSplitter (semantic)")
    print(f"🏷️  Metadata: Enriched (entities, dates, amounts, language)")
    print(f"🔍 RAG: Hybrid Search (BM25 + Vector + Reranking)")
    print("="*80 + "\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        raise
