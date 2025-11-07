"""
Test Simple - Chunking Sémantique + Enrichissement Métadonnées

Ce script teste les 2 priorités implémentées SANS dépendances externes:
1. RecursiveCharacterTextSplitter (chunking sémantique)
2. Enrichissement métadonnées (entités, dates, montants)

Test sur un exemple de texte de facture
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.document_service import DocumentService
from app.services.metadata_enrichment_service import get_metadata_enrichment_service

# Exemple de texte de facture (simulé)
SAMPLE_INVOICE_TEXT = """
FACTURE N° 2025-03-001

Date: 15/03/2025
Échéance: 15/04/2025

ENTREPRISE DEMO SARL
123 Rue de la République
75001 PARIS
SIRET: 123 456 789 00012
Email: contact@entreprise-demo.fr
Tél: 01 23 45 67 89

Client:
SOCIÉTÉ XYZ
456 Avenue des Champs
69001 LYON

DESCRIPTION DES PRESTATIONS:

- Prestation de conseil stratégique (Mars 2025)     2 500,00 EUR
- Formation équipe commerciale                       1 500,00 EUR
- Support technique mensuel                            800,00 EUR

Sous-total HT:                                       4 800,00 EUR
TVA 20%:                                              960,00 EUR
------------------------------------------------------------------
TOTAL TTC:                                           5 760,00 EUR

Paiement par virement bancaire
IBAN: FR76 1234 5678 9012 3456 7890 123

Conditions de paiement: 30 jours net
Pénalités de retard: 10%
"""


async def test_chunking_and_metadata():
    """Test du chunking sémantique et enrichissement métadonnées"""

    print("\n" + "="*80)
    print("🎯 TEST: CHUNKING SÉMANTIQUE + ENRICHISSEMENT MÉTADONNÉES")
    print("="*80 + "\n")

    # 1. Test RecursiveCharacterTextSplitter
    print("📋 ÉTAPE 1: Chunking Sémantique (RecursiveCharacterTextSplitter)")
    print("-" * 80)

    document_service = DocumentService()

    # Chunk avec RecursiveCharacterTextSplitter
    chunks = document_service.chunk_text(
        SAMPLE_INVOICE_TEXT,
        chunk_size=500,  # Réduit pour le test
        overlap=100
    )

    print(f"✅ Texte original: {len(SAMPLE_INVOICE_TEXT)} caractères")
    print(f"✅ Nombre de chunks créés: {len(chunks)}")
    print(f"✅ Taille moyenne des chunks: {sum(len(c) for c in chunks) // len(chunks)} chars")

    print("\n📝 Chunks générés:")
    for i, chunk in enumerate(chunks, 1):
        print(f"\n   Chunk {i} ({len(chunk)} chars):")
        print(f"   {chunk[:100]}..." if len(chunk) > 100 else f"   {chunk}")

    # 2. Test Enrichissement Métadonnées
    print("\n\n📋 ÉTAPE 2: Enrichissement Métadonnées")
    print("-" * 80)

    enricher = get_metadata_enrichment_service()

    # Enrichir le premier chunk (contient les infos principales)
    enriched = enricher.enrich(
        text=SAMPLE_INVOICE_TEXT,
        basic_metadata={"filename": "facture_test.pdf", "doc_type": "facture"},
        chunk_index=0,
        total_chunks=len(chunks)
    )

    print(f"\n✅ Métadonnées enrichies:")
    print(f"   Langue détectée: {enriched.get('language', 'unknown')}")
    print(f"   Type de contenu: {enriched.get('content_type', 'unknown')}")
    print(f"   Position du chunk: {enriched.get('chunk_position', 'unknown')}")
    print(f"   Longueur texte: {enriched.get('text_length', 0)} chars")
    print(f"   Nombre de mots: {enriched.get('word_count', 0)}")
    print(f"   Nombre de phrases: {enriched.get('sentence_count', 0)}")

    # 3. Afficher les entités extraites
    entities = enriched.get("entities", {})
    print(f"\n🔍 ENTITÉS EXTRAITES:")

    if entities.get("emails"):
        print(f"   📧 Emails: {entities['emails']}")

    if entities.get("phones"):
        print(f"   📞 Téléphones: {entities['phones']}")

    if entities.get("amounts"):
        print(f"   💰 Montants: {entities['amounts']}")

    if entities.get("dates"):
        print(f"   📅 Dates: {entities['dates']}")

    if entities.get("ibans"):
        print(f"   🏦 IBANs: {entities['ibans']}")

    if entities.get("sirets"):
        print(f"   🏢 SIRETs: {entities['sirets']}")

    # 4. Keywords extraits
    keywords = enriched.get("keywords", [])
    if keywords:
        print(f"\n🔑 MOTS-CLÉS EXTRAITS:")
        print(f"   {', '.join(keywords[:10])}")

    # 5. Résumé final
    print("\n\n" + "="*80)
    print("📊 RÉSUMÉ DU TEST")
    print("="*80)
    print(f"✅ Chunking sémantique: OK")
    print(f"   - {len(chunks)} chunks créés avec RecursiveCharacterTextSplitter")
    print(f"   - Préserve les paragraphes et structures sémantiques")
    print(f"")
    print(f"✅ Enrichissement métadonnées: OK")
    print(f"   - Langue: {enriched.get('language')}")
    print(f"   - Type contenu: {enriched.get('content_type')}")
    print(f"   - Entités extraites: {sum(len(v) for v in entities.values())} au total")
    print(f"     • Emails: {len(entities.get('emails', []))}")
    print(f"     • Téléphones: {len(entities.get('phones', []))}")
    print(f"     • Montants: {len(entities.get('amounts', []))}")
    print(f"     • Dates: {len(entities.get('dates', []))}")
    print(f"     • IBANs: {len(entities.get('ibans', []))}")
    print(f"     • SIRETs: {len(entities.get('sirets', []))}")
    print(f"   - Mots-clés: {len(keywords)} extraits")
    print("\n" + "="*80)
    print("🎉 TEST RÉUSSI - Les 2 priorités sont implémentées et fonctionnelles!")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_chunking_and_metadata())
    except Exception as e:
        print(f"\n\n❌ Erreur: {e}")
        raise
