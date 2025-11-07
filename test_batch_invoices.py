"""
Test Batch - Upload toutes les factures du dossier FacturesOCR
Pipeline: OCR → Chunking → Enrichissement → RAG Indexing
"""

import requests
from pathlib import Path
import time
from datetime import datetime

BACKEND_URL = "http://localhost:8000"
INVOICES_DIR = r"C:\Users\grego\Desktop\FacturesOCR"

def test_batch_invoices():
    """Upload et traite toutes les factures PDF"""

    print(f"\n{'='*100}")
    print(f"🚀 TEST BATCH - TOUTES LES FACTURES")
    print(f"{'='*100}\n")
    print(f"📁 Dossier: {INVOICES_DIR}")
    print(f"🌐 Backend: {BACKEND_URL}")
    print(f"⏰ Démarrage: {datetime.now().strftime('%H:%M:%S')}")
    print(f"\n{'='*100}\n")

    # Récupérer tous les PDFs
    invoices_path = Path(INVOICES_DIR)
    pdf_files = sorted(invoices_path.glob("*.pdf"))

    if not pdf_files:
        print("❌ Aucun PDF trouvé!")
        return

    print(f"📊 Total: {len(pdf_files)} factures\n")

    results = []
    start_time = time.time()

    for i, pdf_file in enumerate(pdf_files, 1):
        file_size_kb = pdf_file.stat().st_size / 1024

        print(f"[{i}/{len(pdf_files)}] {pdf_file.name} ({file_size_kb:.1f} KB)")

        try:
            with open(pdf_file, 'rb') as f:
                files = {'file': (pdf_file.name, f, 'application/pdf')}

                # Upload avec timeout de 15 minutes par fichier (optimisé pour gros PDFs)
                upload_start = time.time()
                response = requests.post(
                    f"{BACKEND_URL}/api/documents/upload",
                    files=files,
                    timeout=900  # 15 minutes pour les gros fichiers multi-pages
                )
                upload_time = time.time() - upload_start

                if response.status_code == 200:
                    data = response.json()
                    results.append({
                        'filename': pdf_file.name,
                        'success': True,
                        'document_id': data.get('document_id'),
                        'text_length': data.get('text_length'),
                        'chunks': data.get('chunks_count'),
                        'indexed': data.get('indexed'),
                        'time': upload_time,
                        'size_kb': file_size_kb
                    })

                    print(f"   ✅ OK - ID: {data.get('document_id')} | "
                          f"Text: {data.get('text_length')} chars | "
                          f"Chunks: {data.get('chunks_count')} | "
                          f"Indexed: {data.get('indexed')} | "
                          f"⏱️  {upload_time:.1f}s")
                else:
                    results.append({
                        'filename': pdf_file.name,
                        'success': False,
                        'error': f"HTTP {response.status_code}",
                        'time': upload_time,
                        'size_kb': file_size_kb
                    })
                    print(f"   ❌ ÉCHEC - {response.status_code}: {response.text[:100]}")

        except requests.exceptions.Timeout:
            results.append({
                'filename': pdf_file.name,
                'success': False,
                'error': 'TIMEOUT (>15min)',
                'size_kb': file_size_kb
            })
            print(f"   ⚠️  TIMEOUT - Le traitement a pris plus de 15 minutes")

        except Exception as e:
            results.append({
                'filename': pdf_file.name,
                'success': False,
                'error': str(e),
                'size_kb': file_size_kb
            })
            print(f"   ❌ ERREUR: {e}")

        print()  # Ligne vide entre chaque fichier

    # Statistiques finales
    total_time = time.time() - start_time
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]

    total_chunks = sum(r.get('chunks', 0) for r in successful)
    total_chars = sum(r.get('text_length', 0) for r in successful)
    avg_time = sum(r.get('time', 0) for r in successful) / len(successful) if successful else 0

    print(f"\n{'='*100}")
    print(f"📈 RÉSULTATS FINAUX")
    print(f"{'='*100}\n")
    print(f"✅ Succès: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"❌ Échecs: {len(failed)}/{len(results)}")
    print(f"\n📊 Statistiques:")
    print(f"   • Chunks totaux créés: {total_chunks}")
    print(f"   • Caractères extraits: {total_chars:,}")
    print(f"   • Temps moyen/facture: {avg_time:.1f}s")
    print(f"   • Temps total: {total_time/60:.1f} min")
    print(f"   • Débit: {len(successful)/(total_time/60):.1f} factures/min")

    if failed:
        print(f"\n❌ Échecs détaillés:")
        for r in failed:
            print(f"   • {r['filename']}: {r.get('error', 'Unknown')}")

    print(f"\n⏰ Fin: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    test_batch_invoices()
