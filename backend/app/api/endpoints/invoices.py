"""
Invoice OCR Extraction API Endpoints

API pour l'extraction OCR de factures :
- Upload et extraction automatique
- Liste des factures extraites
- Validation manuelle
- Réextraction si nécessaire
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import tempfile
import structlog

from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.ocr_invoice_service import (
    OCRInvoiceService,
    OCRBackend,
    ExtractedInvoice
)

router = APIRouter()
logger = structlog.get_logger()


class InvoiceUploadResponse(BaseModel):
    """Réponse après upload et extraction"""
    facture_id: int
    numero: str
    date_facture: date
    montant_ttc: Decimal
    ocr_confidence: Decimal
    needs_review: bool
    extraction_notes: List[str]
    processing_time_ms: int


class InvoiceListItem(BaseModel):
    """Item dans la liste des factures"""
    id: int
    numero: str
    date_facture: date
    fournisseur_nom: Optional[str]
    montant_ttc: Decimal
    statut: str
    needs_review: bool
    ocr_confidence: Optional[Decimal]
    created_at: datetime


class InvoiceDetail(BaseModel):
    """Détails complets d'une facture"""
    id: int
    numero: str
    date_facture: date
    date_echeance: Optional[date]
    fournisseur_id: Optional[int]
    fournisseur_nom: Optional[str]
    copropriete_id: Optional[int]
    montant_ht: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    devise: str
    categorie: Optional[str]
    statut: str
    needs_review: bool
    ocr_confidence: Optional[Decimal]
    extraction_method: str
    notes: Optional[str]
    created_at: datetime


class ValidateInvoiceRequest(BaseModel):
    """Requête de validation manuelle"""
    validated: bool = True
    corrections: Optional[dict] = None


@router.post("/upload", response_model=InvoiceUploadResponse)
async def upload_and_extract_invoice(
    file: UploadFile = File(...),
    copropriete_id: Optional[int] = Query(None, description="ID de la copropriété"),
    fournisseur_id: Optional[int] = Query(None, description="ID du fournisseur"),
    backend: OCRBackend = Query(OCRBackend.TESSERACT, description="Backend OCR à utiliser"),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload et extraction OCR automatique d'une facture

    Accepte :
    - PDF (multi-pages supporté)
    - Images (JPG, PNG)

    Processus :
    1. Upload du fichier
    2. Extraction OCR (Tesseract ou Azure)
    3. Parsing intelligent des champs
    4. Validation automatique
    5. Enregistrement en base

    Returns:
        InvoiceUploadResponse avec détails d'extraction

    Example:
        curl -X POST "http://localhost:8000/api/invoices/upload" \\
          -F "file=@facture.pdf" \\
          -F "copropriete_id=1" \\
          -F "backend=tesseract"
    """
    import time

    start_time = time.time()

    try:
        # Validation fichier
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nom de fichier manquant")

        # Extensions supportées
        supported_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Format non supporté. Utilisez: {', '.join(supported_extensions)}"
            )

        logger.info(
            "invoice_upload_start",
            filename=file.filename,
            copropriete_id=copropriete_id,
            backend=backend.value
        )

        # Sauvegarder temporairement
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)

        # Service OCR
        ocr_service = OCRInvoiceService(default_backend=backend)

        # Extraction
        extracted_invoice = await ocr_service.extract_from_file(
            file_path=tmp_path,
            backend=backend,
            copropriete_id=copropriete_id
        )

        # Optionnel : Upload vers storage permanent
        # doc_id = await upload_to_storage(tmp_path, file.filename)

        # Enregistrement en base
        facture_id = await ocr_service.save_to_database(
            db=db,
            invoice=extracted_invoice,
            doc_id=None,  # TODO: doc_id si stockage permanent
            copropriete_id=copropriete_id,
            fournisseur_id=fournisseur_id
        )

        # Nettoyage fichier temporaire
        tmp_path.unlink()

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "invoice_upload_complete",
            facture_id=facture_id,
            numero=extracted_invoice.numero,
            processing_time_ms=processing_time,
            needs_review=extracted_invoice.needs_review
        )

        return InvoiceUploadResponse(
            facture_id=facture_id,
            numero=extracted_invoice.numero,
            date_facture=extracted_invoice.date_facture,
            montant_ttc=extracted_invoice.montant_ttc,
            ocr_confidence=extracted_invoice.ocr_confidence,
            needs_review=extracted_invoice.needs_review,
            extraction_notes=extracted_invoice.extraction_notes,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(
            "invoice_upload_failed",
            error=str(e),
            filename=file.filename,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'extraction : {str(e)}"
        )


@router.get("/", response_model=List[InvoiceListItem])
async def list_invoices(
    copropriete_id: Optional[int] = Query(None, description="Filtrer par copropriété"),
    needs_review: Optional[bool] = Query(None, description="Filtrer par needs_review"),
    statut: Optional[str] = Query(None, description="Filtrer par statut"),
    limit: int = Query(50, le=200, description="Nombre max de résultats"),
    offset: int = Query(0, ge=0, description="Offset pour pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Liste des factures extraites

    Filtres disponibles :
    - copropriete_id : Factures d'une copropriété
    - needs_review : Factures nécessitant validation
    - statut : a_valider, validee, payee, annulee

    Pagination :
    - limit : Nombre de résultats (max 200)
    - offset : Offset pour la page

    Returns:
        Liste de factures avec infos essentielles
    """
    try:
        # Construire query dynamique
        where_clauses = []
        params = {}

        if copropriete_id is not None:
            where_clauses.append("copropriete_id = :copropriete_id")
            params["copropriete_id"] = copropriete_id

        if needs_review is not None:
            where_clauses.append("needs_review = :needs_review")
            params["needs_review"] = needs_review

        if statut:
            where_clauses.append("statut = :statut")
            params["statut"] = statut

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = text(f"""
            SELECT
                fg.id,
                fg.numero,
                fg.date_facture,
                fg.montant_ttc,
                fg.statut,
                fg.needs_review,
                fg.ocr_confidence,
                fg.created_at,
                fg.metadata_json->>'fournisseur_nom' as fournisseur_nom
            FROM factures_global fg
            WHERE {where_sql}
            ORDER BY fg.created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        params["limit"] = limit
        params["offset"] = offset

        result = await db.execute(query, params)
        rows = result.fetchall()

        invoices = []
        for row in rows:
            invoices.append(InvoiceListItem(
                id=row.id,
                numero=row.numero,
                date_facture=row.date_facture,
                fournisseur_nom=row.fournisseur_nom,
                montant_ttc=Decimal(str(row.montant_ttc)),
                statut=row.statut,
                needs_review=row.needs_review,
                ocr_confidence=Decimal(str(row.ocr_confidence)) if row.ocr_confidence else None,
                created_at=row.created_at
            ))

        logger.info(
            "invoices_listed",
            count=len(invoices),
            needs_review_filter=needs_review,
            copropriete_id=copropriete_id
        )

        return invoices

    except Exception as e:
        logger.error("list_invoices_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")


@router.get("/{facture_id}", response_model=InvoiceDetail)
async def get_invoice_detail(
    facture_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Détails complets d'une facture

    Returns:
        Tous les champs de la facture + métadonnées OCR
    """
    try:
        query = text("""
            SELECT
                fg.*,
                fg.metadata_json->>'fournisseur_nom' as fournisseur_nom
            FROM factures_global fg
            WHERE fg.id = :facture_id
        """)

        result = await db.execute(query, {"facture_id": facture_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Facture {facture_id} non trouvée")

        invoice = InvoiceDetail(
            id=row.id,
            numero=row.numero,
            date_facture=row.date_facture,
            date_echeance=row.date_echeance,
            fournisseur_id=row.fournisseur_id,
            fournisseur_nom=row.fournisseur_nom,
            copropriete_id=row.copropriete_id,
            montant_ht=Decimal(str(row.montant_ht)),
            montant_tva=Decimal(str(row.montant_tva)),
            montant_ttc=Decimal(str(row.montant_ttc)),
            devise=row.devise,
            categorie=row.categorie,
            statut=row.statut,
            needs_review=row.needs_review,
            ocr_confidence=Decimal(str(row.ocr_confidence)) if row.ocr_confidence else None,
            extraction_method=row.extraction_method,
            notes=row.notes,
            created_at=row.created_at
        )

        return invoice

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_invoice_failed", facture_id=facture_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")


@router.post("/{facture_id}/validate")
async def validate_invoice(
    facture_id: int,
    request: ValidateInvoiceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Valider manuellement une facture

    Après validation :
    - needs_review = false
    - statut = validee
    - validated_at = now()

    Si corrections fournies, mettre à jour les champs.

    Example:
        POST /api/invoices/123/validate
        {
            "validated": true,
            "corrections": {
                "montant_ttc": 1234.56,
                "date_facture": "2024-01-15"
            }
        }
    """
    try:
        # Vérifier existence
        check_query = text("SELECT id FROM factures_global WHERE id = :id")
        result = await db.execute(check_query, {"id": facture_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Facture {facture_id} non trouvée")

        # Appliquer corrections si présentes
        if request.corrections:
            # TODO: Valider et appliquer corrections
            pass

        # Marquer comme validée
        if request.validated:
            update_query = text("""
                UPDATE factures_global
                SET needs_review = false,
                    statut = 'validee',
                    validated_at = NOW()
                WHERE id = :id
            """)
            await db.execute(update_query, {"id": facture_id})
            await db.commit()

            logger.info("invoice_validated", facture_id=facture_id)

            return {"message": "Facture validée avec succès", "facture_id": facture_id}

        return {"message": "Aucune action effectuée", "facture_id": facture_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("validate_invoice_failed", facture_id=facture_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")


@router.get("/stats/summary")
async def get_invoice_stats(
    copropriete_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Statistiques globales des factures

    Returns:
        - Total factures
        - Total à valider (needs_review)
        - Total montant TTC
        - Moyenne confiance OCR
        - Répartition par statut
    """
    try:
        where_clause = "WHERE copropriete_id = :copropriete_id" if copropriete_id else ""
        params = {"copropriete_id": copropriete_id} if copropriete_id else {}

        query = text(f"""
            SELECT
                COUNT(*) as total_factures,
                SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as needs_review_count,
                SUM(montant_ttc) as total_montant_ttc,
                AVG(ocr_confidence) as avg_confidence,
                COUNT(CASE WHEN statut = 'a_valider' THEN 1 END) as a_valider,
                COUNT(CASE WHEN statut = 'validee' THEN 1 END) as validee,
                COUNT(CASE WHEN statut = 'payee' THEN 1 END) as payee
            FROM factures_global
            {where_clause}
        """)

        result = await db.execute(query, params)
        row = result.fetchone()

        stats = {
            "total_factures": row.total_factures or 0,
            "needs_review_count": row.needs_review_count or 0,
            "total_montant_ttc": float(row.total_montant_ttc) if row.total_montant_ttc else 0.0,
            "avg_ocr_confidence": float(row.avg_confidence) if row.avg_confidence else 0.0,
            "statuts": {
                "a_valider": row.a_valider or 0,
                "validee": row.validee or 0,
                "payee": row.payee or 0
            }
        }

        return stats

    except Exception as e:
        logger.error("get_invoice_stats_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
