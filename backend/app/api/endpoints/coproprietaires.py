"""
Copropriétaires Endpoints
CRUD operations for property owners/residents
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, date
import structlog

from app.models.coproprietaire import Coproprietaire
from app.models.copropriete import Copropriete
from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)


class CoproprietaireCreate(BaseModel):
    """Schema for creating a copropriétaire"""
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    telephone_mobile: Optional[str] = None
    copropriete_id: int = Field(..., gt=0)
    numero_lot: str = Field(..., min_length=1, max_length=50)
    type_lot: Optional[str] = None
    etage: Optional[int] = None
    surface: Optional[float] = None
    statut: Optional[str] = "proprietaire"
    statut_special: Optional[str] = None
    est_resident: Optional[bool] = True
    date_acquisition: Optional[date] = None
    tantiemes: Optional[int] = None
    adresse_postale: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "nom": "Dupont",
                "prenom": "Marie",
                "email": "marie.dupont@example.fr",
                "telephone": "0145678901",
                "telephone_mobile": "0612345678",
                "copropriete_id": 1,
                "numero_lot": "A12",
                "type_lot": "appartement",
                "etage": 3,
                "surface": 65.5,
                "statut": "proprietaire",
                "est_resident": True,
                "tantiemes": 850
            }
        }


class CoproprietaireUpdate(BaseModel):
    """Schema for updating a copropriétaire"""
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    telephone_mobile: Optional[str] = None
    numero_lot: Optional[str] = None
    type_lot: Optional[str] = None
    etage: Optional[int] = None
    surface: Optional[float] = None
    statut: Optional[str] = None
    statut_special: Optional[str] = None
    est_resident: Optional[bool] = None
    date_acquisition: Optional[date] = None
    tantiemes: Optional[int] = None
    adresse_postale: Optional[str] = None
    notes: Optional[str] = None


class CoproprietaireResponse(BaseModel):
    """Schema for copropriétaire response"""
    id: int
    nom: str
    prenom: str
    email: Optional[str]
    telephone: Optional[str]
    telephone_mobile: Optional[str]
    copropriete_id: int
    numero_lot: str
    type_lot: Optional[str]
    etage: Optional[int]
    surface: Optional[float]
    statut: str
    statut_special: Optional[str]
    est_resident: bool
    tantiemes: Optional[int]
    is_indexed: bool
    created_at: datetime
    copropriete_nom: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=CoproprietaireResponse, status_code=201)
@limiter.limit("30/minute")  # Moderate limit for creation
async def create_coproprietaire(
    coproprietaire_data: CoproprietaireCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new copropriétaire

    Creates a new resident/owner in a copropriété.
    Validates that the copropriété exists.
    """
    try:
        # Check if copropriete exists
        copro_result = await db.execute(
            select(Copropriete).where(Copropriete.id == coproprietaire_data.copropriete_id)
        )
        copropriete = copro_result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(
                status_code=404,
                detail=f"Copropriété with ID {coproprietaire_data.copropriete_id} not found"
            )

        # Create coproprietaire
        coproprietaire = Coproprietaire(
            **coproprietaire_data.model_dump(exclude_unset=True)
        )

        db.add(coproprietaire)
        await db.commit()
        await db.refresh(coproprietaire)

        logger.info(
            "coproprietaire_created",
            coproprietaire_id=coproprietaire.id,
            nom=coproprietaire.nom,
            copropriete_id=coproprietaire.copropriete_id
        )

        # Add copropriete name
        response_dict = coproprietaire.__dict__.copy()
        response_dict['copropriete_nom'] = copropriete.nom

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("coproprietaire_creation_failed", error=str(e), exc_info=True)

        # Provide more specific error messages for common issues
        error_msg = str(e).lower()

        if "foreign key" in error_msg or "violates foreign key constraint" in error_msg:
            # Get list of available coproprietes for helpful message
            copro_result = await db.execute(select(Copropriete.id, Copropriete.nom))
            available_copros = copro_result.all()
            copro_list = ", ".join([f"{c.id}: {c.nom}" for c in available_copros[:5]])

            raise HTTPException(
                status_code=400,
                detail=f"La copropriété avec l'ID {coproprietaire_data.copropriete_id} n'existe pas. "
                       f"Copropriétés disponibles: {copro_list}{'...' if len(available_copros) > 5 else ''}"
            )
        elif "unique constraint" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Un copropriétaire existe déjà pour le lot {coproprietaire_data.numero_lot} "
                       f"dans cette copropriété (contrainte d'unicité)"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la création du copropriétaire: {str(e)}"
            )


@router.get("/", response_model=List[CoproprietaireResponse])
async def list_coproprietaires(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    copropriete_id: Optional[int] = None,
    statut: Optional[str] = None,
    statut_special: Optional[str] = None,
    search: Optional[str] = None
):
    """
    List all copropriétaires with optional filters

    Filters:
    - copropriete_id: Filter by specific copropriété
    - statut: Filter by status (proprietaire, locataire, etc.)
    - statut_special: Filter by special role (président, syndic, etc.)
    - search: Search in nom, prenom, email, numero_lot
    """
    try:
        # Build query with JOIN to get copropriete name
        query = select(Coproprietaire, Copropriete.nom).join(
            Copropriete,
            Coproprietaire.copropriete_id == Copropriete.id
        )

        # Apply filters
        if copropriete_id:
            query = query.where(Coproprietaire.copropriete_id == copropriete_id)
        if statut:
            query = query.where(Coproprietaire.statut == statut)
        if statut_special:
            query = query.where(Coproprietaire.statut_special == statut_special)
        if search:
            query = query.where(
                or_(
                    Coproprietaire.nom.ilike(f"%{search}%"),
                    Coproprietaire.prenom.ilike(f"%{search}%"),
                    Coproprietaire.email.ilike(f"%{search}%"),
                    Coproprietaire.numero_lot.ilike(f"%{search}%")
                )
            )

        # Add pagination
        query = query.offset(skip).limit(limit).order_by(
            Coproprietaire.nom,
            Coproprietaire.prenom
        )

        result = await db.execute(query)
        rows = result.all()

        # Build response with copropriete name
        response_list = []
        for coproprietaire, copropriete_nom in rows:
            copro_dict = coproprietaire.__dict__.copy()
            copro_dict['copropriete_nom'] = copropriete_nom
            response_list.append(copro_dict)

        logger.info("coproprietaires_listed", count=len(response_list))
        return response_list

    except Exception as e:
        logger.error("coproprietaires_list_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list copropriétaires: {str(e)}"
        )


@router.get("/{coproprietaire_id}", response_model=CoproprietaireResponse)
async def get_coproprietaire(
    coproprietaire_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific copropriétaire by ID

    Returns full details including copropriété name.
    """
    try:
        # Join with copropriete to get name
        query = select(Coproprietaire, Copropriete.nom).join(
            Copropriete,
            Coproprietaire.copropriete_id == Copropriete.id
        ).where(Coproprietaire.id == coproprietaire_id)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Copropriétaire not found")

        coproprietaire, copropriete_nom = row

        response_dict = coproprietaire.__dict__.copy()
        response_dict['copropriete_nom'] = copropriete_nom

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error("coproprietaire_get_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get copropriétaire: {str(e)}"
        )


@router.put("/{coproprietaire_id}", response_model=CoproprietaireResponse)
async def update_coproprietaire(
    coproprietaire_id: int,
    coproprietaire_data: CoproprietaireUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a copropriétaire

    Updates only the fields provided in the request.
    """
    try:
        result = await db.execute(
            select(Coproprietaire).where(Coproprietaire.id == coproprietaire_id)
        )
        coproprietaire = result.scalar_one_or_none()

        if not coproprietaire:
            raise HTTPException(status_code=404, detail="Copropriétaire not found")

        # Update fields
        update_data = coproprietaire_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(coproprietaire, field, value)

        coproprietaire.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(coproprietaire)

        # Get copropriete name
        copro_result = await db.execute(
            select(Copropriete.nom).where(Copropriete.id == coproprietaire.copropriete_id)
        )
        copropriete_nom = copro_result.scalar()

        logger.info(
            "coproprietaire_updated",
            coproprietaire_id=coproprietaire_id,
            fields_updated=list(update_data.keys())
        )

        response_dict = coproprietaire.__dict__.copy()
        response_dict['copropriete_nom'] = copropriete_nom

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("coproprietaire_update_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update copropriétaire: {str(e)}"
        )


@router.delete("/{coproprietaire_id}")
async def delete_coproprietaire(
    coproprietaire_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a copropriétaire

    Removes a resident/owner from the database.
    """
    try:
        result = await db.execute(
            select(Coproprietaire).where(Coproprietaire.id == coproprietaire_id)
        )
        coproprietaire = result.scalar_one_or_none()

        if not coproprietaire:
            raise HTTPException(status_code=404, detail="Copropriétaire not found")

        await db.delete(coproprietaire)
        await db.commit()

        logger.info("coproprietaire_deleted", coproprietaire_id=coproprietaire_id)

        return {
            "message": "Copropriétaire deleted successfully",
            "id": coproprietaire_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("coproprietaire_deletion_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete copropriétaire: {str(e)}"
        )


@router.get("/by-copropriete/{copropriete_id}")
async def get_coproprietaires_by_copropriete(
    copropriete_id: int,
    db: AsyncSession = Depends(get_db),
    etage: Optional[int] = None
):
    """
    Get all copropriétaires for a specific copropriété

    Optional filter by floor (etage).
    """
    try:
        # Check copropriete exists
        copro_result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        copropriete = copro_result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(status_code=404, detail="Copropriété not found")

        # Build query
        query = select(Coproprietaire).where(
            Coproprietaire.copropriete_id == copropriete_id
        )

        if etage is not None:
            query = query.where(Coproprietaire.etage == etage)

        query = query.order_by(Coproprietaire.numero_lot)

        result = await db.execute(query)
        coproprietaires = result.scalars().all()

        return {
            "copropriete_id": copropriete_id,
            "copropriete_nom": copropriete.nom,
            "total": len(coproprietaires),
            "coproprietaires": [
                {
                    "id": c.id,
                    "nom": c.nom,
                    "prenom": c.prenom,
                    "email": c.email,
                    "numero_lot": c.numero_lot,
                    "etage": c.etage,
                    "statut": c.statut,
                    "statut_special": c.statut_special,
                    "est_resident": c.est_resident
                }
                for c in coproprietaires
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_by_copropriete_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get copropriétaires: {str(e)}"
        )


@router.get("/special-roles/list")
async def get_special_roles(
    db: AsyncSession = Depends(get_db),
    role: Optional[str] = None
):
    """
    Get all copropriétaires with special roles

    Optional filter by specific role (président, syndic, gardien, etc.)
    """
    try:
        query = select(Coproprietaire, Copropriete.nom).join(
            Copropriete,
            Coproprietaire.copropriete_id == Copropriete.id
        ).where(Coproprietaire.statut_special.isnot(None))

        if role:
            query = query.where(Coproprietaire.statut_special.ilike(f"%{role}%"))

        query = query.order_by(Coproprietaire.statut_special, Coproprietaire.nom)

        result = await db.execute(query)
        rows = result.all()

        return {
            "total": len(rows),
            "special_roles": [
                {
                    "id": coproprietaire.id,
                    "nom": coproprietaire.nom,
                    "prenom": coproprietaire.prenom,
                    "email": coproprietaire.email,
                    "telephone": coproprietaire.telephone,
                    "statut_special": coproprietaire.statut_special,
                    "copropriete_id": coproprietaire.copropriete_id,
                    "copropriete_nom": copropriete_nom,
                    "numero_lot": coproprietaire.numero_lot
                }
                for coproprietaire, copropriete_nom in rows
            ]
        }

    except Exception as e:
        logger.error("get_special_roles_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get special roles: {str(e)}"
        )
