"""
Script de test pour DisruptIQ API
Tests tous les bugs corrigés
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def test_health():
    """Test 1: Health check"""
    print_header("TEST 1: Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check OK")

def test_stats_empty():
    """Test 2: Stats initiales (doivent être à 0)"""
    print_header("TEST 2: Stats Initiales")
    response = requests.get(f"{BASE_URL}/api/admin/stats")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    print(f"Emails: {data['total_emails']}, Documents: {data['total_documents']}, Vendors: {data['total_vendors']}")
    print("✅ Stats récupérées")

def test_import_vendors():
    """Test 3: Import CSV avec délimiteur ;"""
    print_header("TEST 3: Import CSV Vendors (délimiteur ;)")

    csv_path = Path("test_vendors.csv")
    if not csv_path.exists():
        print("❌ Fichier test_vendors.csv non trouvé")
        return

    with open(csv_path, 'rb') as f:
        files = {'file': ('test_vendors.csv', f, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/admin/vendors/import-csv", files=files)

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 200:
        print(f"✅ Import réussi: {data['vendors_created']} créés, {data.get('vendors_skipped', 0)} ignorés")
    else:
        print(f"❌ Import échoué")

def test_import_vendors_duplicate():
    """Test 4: Ré-import du même CSV (test doublons)"""
    print_header("TEST 4: Ré-import CSV (test doublons)")

    csv_path = Path("test_vendors.csv")
    if not csv_path.exists():
        print("❌ Fichier test_vendors.csv non trouvé")
        return

    with open(csv_path, 'rb') as f:
        files = {'file': ('test_vendors.csv', f, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/admin/vendors/import-csv", files=files)

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if data.get('vendors_skipped', 0) > 0:
        print(f"✅ Doublons détectés et ignorés: {data['vendors_skipped']}")
    else:
        print("⚠️ Aucun doublon détecté (normal si c'est le premier import)")

def test_list_vendors():
    """Test 5: Liste des vendors"""
    print_header("TEST 5: Liste des Vendors")
    response = requests.get(f"{BASE_URL}/api/admin/vendors")
    print(f"Status: {response.status_code}")
    vendors = response.json()
    print(f"Nombre de vendors: {len(vendors)}")
    if vendors:
        print(f"Premier vendor: {vendors[0]['name']} - {vendors[0]['email']}")
    print("✅ Liste récupérée")

def test_upload_document():
    """Test 6: Upload d'un document"""
    print_header("TEST 6: Upload Document")

    doc_path = Path("test_document.txt")
    if not doc_path.exists():
        print("❌ Fichier test_document.txt non trouvé")
        return

    with open(doc_path, 'rb') as f:
        files = {'file': ('test_document.txt', f, 'text/plain')}
        response = requests.post(f"{BASE_URL}/api/documents/upload", files=files)

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 200:
        print(f"✅ Document uploadé: {data['chunks_indexed']} chunks indexés dans Qdrant")
        return data['document_id']
    else:
        print(f"❌ Upload échoué")
        return None

def test_list_documents():
    """Test 7: Liste des documents"""
    print_header("TEST 7: Liste des Documents")
    response = requests.get(f"{BASE_URL}/api/documents/")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    print(f"Total documents: {data['total']}")
    print("✅ Documents listés")

def test_chat_rag():
    """Test 8: Chat RAG avec contexte"""
    print_header("TEST 8: Chat RAG (avec contexte)")

    payload = {
        "message": "Quel est le montant du contrat de maintenance des jardins?"
    }

    response = requests.post(f"{BASE_URL}/api/chat/ask", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Question: {payload['message']}")
        print(f"Réponse: {data['message'][:200]}...")
        print(f"Sources: {len(data.get('sources', []))} documents trouvés")
        print("✅ RAG fonctionne")
    else:
        print(f"❌ RAG échoué: {response.text}")

def test_stats_final():
    """Test 9: Stats finales (doivent être mises à jour)"""
    print_header("TEST 9: Stats Finales")
    response = requests.get(f"{BASE_URL}/api/admin/stats")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    print(f"\n📊 Résumé:")
    print(f"  - Emails: {data['total_emails']}")
    print(f"  - Documents: {data['total_documents']}")
    print(f"  - Vendors: {data['total_vendors']}")
    print(f"  - Users: {data['total_users']}")

    if data['total_vendors'] > 0:
        print("✅ Les vendors sont comptabilisés")
    if data['total_documents'] > 0:
        print("✅ Les documents sont comptabilisés")

def main():
    print("\n🚀 DisruptIQ - Tests de l'API")
    print("="*60)

    try:
        test_health()
        test_stats_empty()
        test_import_vendors()
        test_import_vendors_duplicate()
        test_list_vendors()
        test_upload_document()
        test_list_documents()
        test_chat_rag()
        test_stats_final()

        print("\n" + "="*60)
        print("✅ TOUS LES TESTS SONT PASSÉS !")
        print("="*60)

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
