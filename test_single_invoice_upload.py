"""
Test Single Invoice Upload to Capture Detailed Error Traceback

This script uploads ONE invoice to capture the full error traceback
"""

import requests
from pathlib import Path

BACKEND_URL = "http://localhost:8000"
INVOICES_DIR = r"C:\Users\grego\Desktop\FacturesOCR"

def test_single_upload():
    """Upload a single invoice and print detailed error if it fails"""

    # Get first PDF invoice
    invoices_path = Path(INVOICES_DIR)
    pdf_files = list(invoices_path.glob("*.pdf"))

    if not pdf_files:
        print("❌ No PDF files found")
        return

    test_file = pdf_files[0]

    print(f"\n{'='*80}")
    print(f"🧪 SINGLE INVOICE UPLOAD TEST")
    print(f"{'='*80}\n")
    print(f"📄 File: {test_file.name}")
    print(f"📦 Size: {test_file.stat().st_size / 1024:.1f} KB")
    print(f"🌐 Backend: {BACKEND_URL}")
    print(f"\n{'='*80}\n")

    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}

            print(f"⏳ Uploading to {BACKEND_URL}/api/documents/upload...")
            response = requests.post(
                f"{BACKEND_URL}/api/documents/upload",
                files=files,
                timeout=180
            )

            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📝 Response Headers: {dict(response.headers)}")
            print(f"\n📄 Response Body:")
            print(response.text)

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ SUCCESS!")
                print(f"   Document ID: {data.get('document_id')}")
                print(f"   Text Length: {data.get('text_length')} chars")
                print(f"   Doc Type: {data.get('doc_type')}")
            else:
                print(f"\n❌ FAILED!")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ REQUEST ERROR: {e}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_upload()
