"""
Test avec le plus petit PDF (Cogelec - 215 KB, 1 page)
pour valider le pipeline complet: OCR → Chunking → Enrichissement → Indexation RAG
"""

import requests
from pathlib import Path

BACKEND_URL = "http://localhost:8000"
TEST_FILE = r"C:\Users\grego\Desktop\FacturesOCR\202504150027.pdf"

def test_small_pdf():
    """Test complet du pipeline avec un petit PDF"""

    print(f"\n{'='*80}")
    print(f"🧪 TEST PIPELINE COMPLET - PETIT PDF")
    print(f"{'='*80}\n")
    print(f"📄 File: 202504150027.pdf (Cogelec)")
    print(f"🌐 Backend: {BACKEND_URL}")
    print(f"⚙️  Pipeline: OCR → Chunking → Enrichissement → RAG")
    print(f"\n{'='*80}\n")

    test_file = Path(TEST_FILE)
    if not test_file.exists():
        print(f"❌ File not found: {TEST_FILE}")
        return

    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}

            print(f"⏳ Uploading and processing...")
            response = requests.post(
                f"{BACKEND_URL}/api/documents/upload",
                files=files,
                timeout=300  # 5 minutes pour être sûr
            )

            print(f"\n📊 Response Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ SUCCESS! Pipeline complet validé\n")
                print(f"📄 Document ID: {data.get('document_id')}")
                print(f"📝 Text Length: {data.get('text_length')} chars")
                print(f"📋 Doc Type: {data.get('doc_type')}")
                print(f"🧩 Chunks: {data.get('chunks_count', 'N/A')}")
                print(f"🔍 Indexed: {data.get('indexed', False)}")

                # Test RAG search
                print(f"\n{'='*80}")
                print(f"🔍 TEST RAG SEARCH")
                print(f"{'='*80}\n")

                doc_id = data.get('document_id')
                if doc_id:
                    # Search for "Cogelec"
                    search_response = requests.post(
                        f"{BACKEND_URL}/api/search",
                        json={
                            "query": "Cogelec montant total",
                            "top_k": 3
                        },
                        timeout=30
                    )

                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        results = search_data.get("results", [])
                        print(f"✅ Search successful: {len(results)} results found")

                        for i, result in enumerate(results[:3], 1):
                            print(f"\n   [{i}] Score: {result.get('score', 0):.3f}")
                            print(f"       Document: {result.get('document_id')}")
                            text_preview = result.get('text', '')[:200]
                            print(f"       Text: {text_preview}...")
                    else:
                        print(f"❌ Search failed: {search_response.status_code}")

            else:
                print(f"\n❌ FAILED!")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text}")

    except requests.exceptions.Timeout:
        print(f"\n⚠️  TIMEOUT - Processing took too long")
        print(f"   But OCR might still be processing in background")
        print(f"   Check backend logs for progress")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_small_pdf()
