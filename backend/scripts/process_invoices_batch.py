#!/usr/bin/env python3
"""
Script de traitement en lot de factures OCR

Usage:
    python scripts/process_invoices_batch.py --dir /path/to/invoices --copropriete-id 1

Traite tous les fichiers PDF/images d'un répertoire et les extrait en base.
"""

import asyncio
import argparse
from pathlib import Path
import sys
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ocr_invoice_service import OCRInvoiceService, OCRBackend
from app.core.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

logger = structlog.get_logger()


async def process_invoice_file(
    service: OCRInvoiceService,
    file_path: Path,
    db: AsyncSession,
    copropriete_id: int,
    backend: OCRBackend
):
    """
    Traite un fichier facture

    Args:
        service: Service OCR
        file_path: Chemin vers fichier
        db: Session DB
        copropriete_id: ID copropriété
        backend: Backend OCR à utiliser

    Returns:
        Tuple (success, facture_id or error_message)
    """
    try:
        logger.info("processing_file", file_path=str(file_path))

        # Extraction
        extracted = await service.extract_from_file(
            file_path=file_path,
            backend=backend,
            copropriete_id=copropriete_id
        )

        # Enregistrement
        facture_id = await service.save_to_database(
            db=db,
            invoice=extracted,
            copropriete_id=copropriete_id
        )

        logger.info(
            "file_processed_success",
            file_path=str(file_path),
            facture_id=facture_id,
            numero=extracted.numero,
            montant_ttc=float(extracted.montant_ttc),
            needs_review=extracted.needs_review
        )

        return True, facture_id

    except Exception as e:
        logger.error(
            "file_processing_failed",
            file_path=str(file_path),
            error=str(e),
            exc_info=True
        )
        return False, str(e)


async def main(args):
    """Main async function"""

    # Vérifier répertoire
    invoice_dir = Path(args.dir)
    if not invoice_dir.exists():
        print(f"❌ Répertoire non trouvé: {invoice_dir}")
        sys.exit(1)

    # Lister fichiers
    supported_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    files = [
        f for f in invoice_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    if not files:
        print(f"⚠️  Aucun fichier trouvé dans {invoice_dir}")
        sys.exit(0)

    print(f"📄 Trouvé {len(files)} fichier(s) à traiter")
    print(f"🏢 Copropriété ID: {args.copropriete_id}")
    print(f"🔍 Backend OCR: {args.backend}")
    print()

    # Service OCR
    backend = OCRBackend(args.backend)
    service = OCRInvoiceService(default_backend=backend)

    # Stats
    stats = {
        "total": len(files),
        "success": 0,
        "failed": 0,
        "needs_review": 0,
        "total_montant_ttc": Decimal("0.00")
    }

    # Database session
    async for db in get_async_session():
        # Traiter chaque fichier
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Traitement: {file_path.name} ...", end=" ")

            success, result = await process_invoice_file(
                service=service,
                file_path=file_path,
                db=db,
                copropriete_id=args.copropriete_id,
                backend=backend
            )

            if success:
                facture_id = result
                print(f"✅ ID: {facture_id}")
                stats["success"] += 1

                # Récupérer info facture
                from sqlalchemy import text
                query = text("""
                    SELECT montant_ttc, needs_review
                    FROM factures_global
                    WHERE id = :id
                """)
                row = (await db.execute(query, {"id": facture_id})).fetchone()
                if row:
                    stats["total_montant_ttc"] += Decimal(str(row.montant_ttc))
                    if row.needs_review:
                        stats["needs_review"] += 1
            else:
                error = result
                print(f"❌ Erreur: {error[:50]}...")
                stats["failed"] += 1

            # Pause entre fichiers
            if i < len(files):
                await asyncio.sleep(0.5)

        # Fin de session
        break

    # Résumé
    print()
    print("=" * 60)
    print("📊 RÉSUMÉ DU TRAITEMENT")
    print("=" * 60)
    print(f"Total fichiers:       {stats['total']}")
    print(f"✅ Succès:            {stats['success']}")
    print(f"❌ Échecs:            {stats['failed']}")
    print(f"⚠️  À valider:         {stats['needs_review']}")
    print(f"💰 Montant total TTC: {stats['total_montant_ttc']:.2f} €")
    print()

    if stats['needs_review'] > 0:
        print(f"⚠️  {stats['needs_review']} facture(s) nécessitent validation manuelle")
        print("   Consultez: http://localhost:8000/api/invoices/?needs_review=true")
        print()

    # Exit code
    if stats['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Traitement en lot de factures OCR"
    )
    parser.add_argument(
        "--dir",
        required=True,
        help="Répertoire contenant les factures (PDF, images)"
    )
    parser.add_argument(
        "--copropriete-id",
        type=int,
        required=True,
        help="ID de la copropriété"
    )
    parser.add_argument(
        "--backend",
        choices=["tesseract", "azure"],
        default="tesseract",
        help="Backend OCR à utiliser (défaut: tesseract)"
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(main(args))
