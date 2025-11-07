"""
Test OPTIMIZED - Facture 202503060002 (1).pdf (3.3 MB)
Validation des optimisations:
- Traitement parallèle des pages PDF
- DPI adaptatif (150 pour gros fichiers)
- Model instance caching
- Timeout 15 minutes
"""

import requests
from pathlib import Path
import time
from datetime import datetime

BACKEND_URL = "http://localhost:8000"
TEST_FILE = r"C:\Users\grego\Desktop\FacturesOCR\202503060002 (1).pdf"

def test_large_pdf():
    """Test de performance avec la facture volumineuse"""

    print(f"\n{'='*100}")
    print(f"🚀 TEST OPTIMIZATIONS - LARGE PDF")
    print(f"{'='*100}\n")
    print(f"📄 File: 202503060002 (1).pdf (3.3 MB)")
    print(f"🌐 Backend: {BACKEND_URL}")
    print(f"⚙️  Optimizations:")
    print(f"   ✅ Parallel page processing (asyncio.gather)")
    print(f"   ✅ Adaptive DPI (150 for large files)")
    print(f"   ✅ Model instance caching")
    print(f"   ✅ 15 min timeout")
    print(f"\n⏰ Start: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*100}\n")

    test_file = Path(TEST_FILE)
    if not test_file.exists():
        print(f"❌ File not found: {TEST_FILE}")
        return

    file_size_mb = test_file.stat().st_size / (1024 * 1024)
    print(f"📦 File size: {file_size_mb:.2f} MB\n")

    try:
        start_time = time.time()

        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}

            print(f"⏳ Uploading and processing with OPTIMIZED pipeline...")
            response = requests.post(
                f"{BACKEND_URL}/api/documents/upload",
                files=files,
                timeout=900  # 15 minutes
            )

            elapsed_time = time.time() - start_time

            print(f"\n{'='*100}")
            print(f"📊 RESULTS")
            print(f"{'='*100}\n")
            print(f"⏱️  Processing time: {elapsed_time:.1f}s ({elapsed_time/60:.1f} min)")
            print(f"📈 Status code: {response.status_code}\n")

            if response.status_code == 200:
                data = response.json()

                text_length = data.get('text_length', 0)
                chunks = data.get('chunks_count', 0)

                print(f"✅ SUCCESS! File processed with optimizations\n")
                print(f"📄 Document ID: {data.get('document_id')}")
                print(f"📝 Text extracted: {text_length:,} chars")
                print(f"📋 Doc type: {data.get('doc_type')}")
                print(f"🧩 Chunks created: {chunks}")
                print(f"🔍 Indexed: {data.get('indexed')}")

                # Performance metrics
                chars_per_sec = text_length / elapsed_time if elapsed_time > 0 else 0
                mb_per_sec = file_size_mb / elapsed_time if elapsed_time > 0 else 0

                print(f"\n⚡ Performance:")
                print(f"   • {chars_per_sec:.0f} chars/sec")
                print(f"   • {mb_per_sec:.3f} MB/sec")
                print(f"   • {elapsed_time/chunks:.1f}s per chunk" if chunks > 0 else "")

                # Comparison with previous attempt
                previous_timeout = 300  # 5 min
                if elapsed_time < previous_timeout:
                    improvement = ((previous_timeout - elapsed_time) / previous_timeout) * 100
                    print(f"\n🎉 IMPROVEMENT: Successfully processed within timeout!")
                    print(f"   Previous: TIMEOUT (>5 min)")
                    print(f"   Now: {elapsed_time:.1f}s")
                else:
                    print(f"\n⚠️  Still slower than ideal but COMPLETED successfully")

            else:
                print(f"❌ FAILED!")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text[:500]}")

    except requests.exceptions.Timeout:
        print(f"\n⚠️  TIMEOUT - Processing took more than 15 minutes")
        print(f"   This indicates the optimizations may need further tuning")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n⏰ End: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    test_large_pdf()
