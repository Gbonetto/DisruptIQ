"""
Test Invoice Processing via Backend API

This script tests the complete pipeline by uploading invoices to the backend API:
1. OCR with Mistral Vision (Pixtral)
2. Chunking with RecursiveCharacterTextSplitter
3. Metadata enrichment (entities, dates, amounts)
4. RAG indexing with Qdrant
5. Search and query testing

Directory: C:\\Users\\grego\\Desktop\\FacturesOCR
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
INVOICES_DIR = r"C:\Users\grego\Desktop\FacturesOCR"
RESULTS_FILE = "invoice_api_test_results.json"


class InvoiceAPITester:
    """Test invoice processing via backend API"""

    def __init__(self):
        self.backend_url = BACKEND_URL
        self.results = []
        self.document_ids = []

    def upload_document(self, file_path: Path) -> dict:
        """
        Upload a document to the backend API

        Args:
            file_path: Path to invoice file

        Returns:
            Response from API
        """
        start_time = datetime.now()
        result = {
            "filename": file_path.name,
            "file_path": str(file_path),
            "file_size_kb": file_path.stat().st_size / 1024,
            "status": "pending",
            "error": None,
            "processing_time_seconds": 0,
            "response": None
        }

        try:
            # Read file
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, self._get_content_type(file_path.suffix))}

                # Upload to backend
                print(f"   Uploading to {self.backend_url}/api/documents/upload...")
                response = requests.post(
                    f"{self.backend_url}/api/documents/upload",
                    files=files,
                    timeout=180  # 3 minutes timeout for large documents
                )

                # Parse response
                if response.status_code == 200:
                    data = response.json()
                    result["status"] = "success"
                    result["response"] = data
                    result["document_id"] = data.get("document_id")

                    # Store document ID for later queries
                    if result["document_id"]:
                        self.document_ids.append(result["document_id"])

                    print(f"   ✅ SUCCESS")
                    print(f"   Document ID: {result['document_id']}")
                    if "text_length" in data:
                        print(f"   Text extracted: {data['text_length']} chars")
                    if "doc_type" in data:
                        print(f"   Document type: {data['doc_type']}")

                else:
                    result["status"] = "failed"
                    result["error"] = f"HTTP {response.status_code}: {response.text}"
                    print(f"   ❌ FAILED: {result['error']}")

        except requests.exceptions.RequestException as e:
            result["status"] = "error"
            result["error"] = f"Request error: {str(e)}"
            print(f"   ❌ ERROR: {result['error']}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"   ❌ ERROR: {result['error']}")

        finally:
            end_time = datetime.now()
            result["processing_time_seconds"] = (end_time - start_time).total_seconds()
            print(f"   ⏱️  Time: {result['processing_time_seconds']:.2f}s")

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

    def test_search(self, query: str, top_k: int = 3) -> dict:
        """
        Test RAG search with a query

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Search results
        """
        try:
            print(f"\n🔍 Testing search: \"{query}\"")

            response = requests.post(
                f"{self.backend_url}/api/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "document_ids": self.document_ids  # Filter to uploaded documents
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                print(f"   ✅ Found {len(results)} results")
                for i, result in enumerate(results[:3], 1):
                    print(f"   [{i}] Score: {result.get('score', 0):.3f}")
                    print(f"       Document ID: {result.get('document_id')}")
                    text_preview = result.get('text', '')[:100]
                    print(f"       Text: {text_preview}...")

                return {"success": True, "results": results}

            else:
                print(f"   ❌ Search failed: HTTP {response.status_code}")
                return {"success": False, "error": response.text}

        except Exception as e:
            print(f"   ❌ Search error: {e}")
            return {"success": False, "error": str(e)}

    def run_batch_test(self):
        """Run batch test on all invoices"""
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
            print(f"🚀 BATCH INVOICE PROCESSING VIA API - {len(invoice_files)} factures")
            print(f"{'='*80}\n")

            # Process each invoice
            for idx, file_path in enumerate(invoice_files, 1):
                print(f"\n📄 [{idx}/{len(invoice_files)}] {file_path.name}")
                print(f"   Size: {file_path.stat().st_size / 1024:.1f} KB")

                result = self.upload_document(file_path)
                self.results.append(result)

                # Small delay between uploads
                if idx < len(invoice_files):
                    time.sleep(1)

            # Generate summary report
            self.generate_report()

            # Test search queries
            if self.document_ids:
                print(f"\n{'='*80}")
                print("🔍 TESTING RAG SEARCH")
                print(f"{'='*80}\n")

                test_queries = [
                    "Cogelec",
                    "montant total",
                    "facture 2025",
                    "net à payer"
                ]

                for query in test_queries:
                    self.test_search(query)
                    time.sleep(0.5)

        except Exception as e:
            print(f"\n❌ Batch test failed: {e}")

    def generate_report(self):
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

            print(f"\n📄 Document IDs indexed: {len(self.document_ids)}")
            print(f"   {self.document_ids[:5]}")

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
                "document_ids": self.document_ids,
                "results": self.results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed results saved to: {RESULTS_FILE}")
        print(f"\n{'='*80}\n")


def main():
    """Main test runner"""
    tester = InvoiceAPITester()
    tester.run_batch_test()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🎯 DISRUPTIQ - BATCH INVOICE PROCESSING TEST (via API)")
    print("="*80)
    print(f"📁 Invoices Directory: {INVOICES_DIR}")
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"🤖 Testing: OCR + Chunking + Metadata + RAG Indexing + Search")
    print("="*80 + "\n")

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        raise
