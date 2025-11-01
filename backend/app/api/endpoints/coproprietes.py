"""
Copropriétés Endpoints
CRUD operations for property management
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime
import structlog

from app.models.copropriete import Copropriete
from app.models.coproprietaire import Coproprietaire
from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)


class CoproprieteCreate(BaseModel):
    """Schema for creating a copropriété"""
    nom: str = Field(..., min_length=1, max_length=200)
    adresse: str = Field(..., min_length=1)
    ville: str = Field(..., min_length=1)
    code_postal: str = Field(..., min_length=4, max_length=10)
    nombre_lots: Optional[int] = None
    nombre_batiments: Optional[int] = 1
    annee_construction: Optional[int] = None
    syndic: Optional[str] = None
    contact_syndic: Optional[str] = None
    reference_syndic: Optional[str] = None
    type_copropriete: Optional[str] = None
    surface_totale: Optional[float] = None
    equipements: Optional[List[str]] = []
    notes: Optional[str] = None
    documents_path: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "nom": "Résidence Les Mimosas",
                "adresse": "12 Avenue de la République",
                "ville": "Paris",
                "code_postal": "75013",
                "nombre_lots": 45,
                "nombre_batiments": 2,
                "annee_construction": 1985,
                "syndic": "Syndic Foncia",
                "type_copropriete": "résidentiel",
                "equipements": ["ascenseur", "parking", "interphone"]
            }
        }


class CoproprieteUpdate(BaseModel):
    """Schema for updating a copropriété"""
    nom: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    nombre_lots: Optional[int] = None
    nombre_batiments: Optional[int] = None
    annee_construction: Optional[int] = None
    syndic: Optional[str] = None
    contact_syndic: Optional[str] = None
    reference_syndic: Optional[str] = None
    type_copropriete: Optional[str] = None
    surface_totale: Optional[float] = None
    equipements: Optional[List[str]] = None
    notes: Optional[str] = None
    documents_path: Optional[str] = None


class CoproprieteResponse(BaseModel):
    """Schema for copropriété response"""
    id: int
    nom: str
    adresse: str
    ville: str
    code_postal: str
    nombre_lots: Optional[int]
    nombre_batiments: Optional[int]
    annee_construction: Optional[int]
    syndic: Optional[str]
    contact_syndic: Optional[str]
    type_copropriete: Optional[str]
    surface_totale: Optional[float]
    equipements: Optional[List[str]]
    is_indexed: bool
    created_at: datetime
    coproprietaires_count: Optional[int] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=CoproprieteResponse, status_code=201)
@limiter.limit("20/minute")  # Moderate limit for creation
async def create_copropriete(
    copropriete_data: CoproprieteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new copropriété

    Creates a new property with all its characteristics.
    """
    try:
        # Create copropriété
        copropriete = Copropriete(
            **copropriete_data.model_dump(exclude_unset=True)
        )

        db.add(copropriete)
        await db.commit()
        await db.refresh(copropriete)

        logger.info(
            "copropriete_created",
            copropriete_id=copropriete.id,
            nom=copropriete.nom
        )

        # Add coproprietaires count
        response_dict = copropriete.__dict__.copy()
        response_dict['coproprietaires_count'] = 0

        return response_dict

    except Exception as e:
        await db.rollback()
        logger.error("copropriete_creation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create copropriété: {str(e)}"
        )


@router.get("/", response_model=List[CoproprieteResponse])
async def list_coproprietes(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    ville: Optional[str] = None,
    code_postal: Optional[str] = None,
    syndic: Optional[str] = None,
    search: Optional[str] = None
):
    """
    List all copropriétés with optional filters

    Filters:
    - ville: Filter by city
    - code_postal: Filter by postal code
    - syndic: Filter by syndic name
    - search: Search in nom, adresse, ville
    """
    try:
        # Build query
        query = select(Copropriete)

        # Apply filters
        if ville:
            query = query.where(Copropriete.ville.ilike(f"%{ville}%"))
        if code_postal:
            query = query.where(Copropriete.code_postal.like(f"{code_postal}%"))
        if syndic:
            query = query.where(Copropriete.syndic.ilike(f"%{syndic}%"))
        if search:
            query = query.where(
                or_(
                    Copropriete.nom.ilike(f"%{search}%"),
                    Copropriete.adresse.ilike(f"%{search}%"),
                    Copropriete.ville.ilike(f"%{search}%")
                )
            )

        # Add pagination
        query = query.offset(skip).limit(limit).order_by(Copropriete.created_at.desc())

        result = await db.execute(query)
        coproprietes = result.scalars().all()

        # Add coproprietaires count for each
        response_list = []
        for copro in coproprietes:
            count_query = select(func.count(Coproprietaire.id)).where(
                Coproprietaire.copropriete_id == copro.id
            )
            count_result = await db.execute(count_query)
            count = count_result.scalar()

            copro_dict = copro.__dict__.copy()
            copro_dict['coproprietaires_count'] = count
            response_list.append(copro_dict)

        logger.info("coproprietes_listed", count=len(coproprietes))
        return response_list

    except Exception as e:
        logger.error("coproprietes_list_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list copropriétés: {str(e)}"
        )


@router.get("/{copropriete_id}", response_model=CoproprieteResponse)
async def get_copropriete(
    copropriete_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific copropriété by ID

    Returns full details including count of copropriétaires.
    """
    try:
        result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        copropriete = result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(status_code=404, detail="Copropriété not found")

        # Get coproprietaires count
        count_query = select(func.count(Coproprietaire.id)).where(
            Coproprietaire.copropriete_id == copropriete_id
        )
        count_result = await db.execute(count_query)
        count = count_result.scalar()

        response_dict = copropriete.__dict__.copy()
        response_dict['coproprietaires_count'] = count

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error("copropriete_get_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get copropriété: {str(e)}"
        )


@router.put("/{copropriete_id}", response_model=CoproprieteResponse)
async def update_copropriete(
    copropriete_id: int,
    copropriete_data: CoproprieteUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a copropriété

    Updates only the fields provided in the request.
    """
    try:
        result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        copropriete = result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(status_code=404, detail="Copropriété not found")

        # Update fields
        update_data = copropriete_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(copropriete, field, value)

        copropriete.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(copropriete)

        logger.info(
            "copropriete_updated",
            copropriete_id=copropriete_id,
            fields_updated=list(update_data.keys())
        )

        # Get count
        count_query = select(func.count(Coproprietaire.id)).where(
            Coproprietaire.copropriete_id == copropriete_id
        )
        count_result = await db.execute(count_query)
        count = count_result.scalar()

        response_dict = copropriete.__dict__.copy()
        response_dict['coproprietaires_count'] = count

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("copropriete_update_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update copropriété: {str(e)}"
        )


@router.delete("/{copropriete_id}")
async def delete_copropriete(
    copropriete_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a copropriété

    WARNING: This will also delete all associated copropriétaires (CASCADE).
    """
    try:
        result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        copropriete = result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(status_code=404, detail="Copropriété not found")

        await db.delete(copropriete)
        await db.commit()

        logger.info("copropriete_deleted", copropriete_id=copropriete_id)

        return {
            "message": "Copropriété deleted successfully",
            "id": copropriete_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("copropriete_deletion_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete copropriété: {str(e)}"
        )


@router.get("/{copropriete_id}/coproprietaires")
async def get_copropriete_coproprietaires(
    copropriete_id: int,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get all copropriétaires for a specific copropriété

    Returns a list of residents/owners living in this property.
    """
    try:
        # Check if copropriete exists
        copro_result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        if not copro_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Copropriété not found")

        # Get coproprietaires
        query = select(Coproprietaire).where(
            Coproprietaire.copropriete_id == copropriete_id
        ).offset(skip).limit(limit).order_by(Coproprietaire.nom, Coproprietaire.prenom)

        result = await db.execute(query)
        coproprietaires = result.scalars().all()

        return {
            "copropriete_id": copropriete_id,
            "total": len(coproprietaires),
            "coproprietaires": [
                {
                    "id": c.id,
                    "nom": c.nom,
                    "prenom": c.prenom,
                    "email": c.email,
                    "numero_lot": c.numero_lot,
                    "statut": c.statut,
                    "statut_special": c.statut_special
                }
                for c in coproprietaires
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_coproprietaires_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get copropriétaires: {str(e)}"
        )


@router.get("/{copropriete_id}/stats")
async def get_copropriete_stats(
    copropriete_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics for a copropriété

    Returns counts and breakdowns of residents by status, etc.
    """
    try:
        # Check if exists
        copro_result = await db.execute(
            select(Copropriete).where(Copropriete.id == copropriete_id)
        )
        copropriete = copro_result.scalar_one_or_none()

        if not copropriete:
            raise HTTPException(status_code=404, detail="Copropriété not found")

        # Total coproprietaires
        total_query = select(func.count(Coproprietaire.id)).where(
            Coproprietaire.copropriete_id == copropriete_id
        )
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        # By statut
        statut_query = select(
            Coproprietaire.statut,
            func.count(Coproprietaire.id)
        ).where(
            Coproprietaire.copropriete_id == copropriete_id
        ).group_by(Coproprietaire.statut)

        statut_result = await db.execute(statut_query)
        by_statut = {row[0]: row[1] for row in statut_result.all()}

        # Special roles
        special_query = select(
            Coproprietaire.statut_special,
            func.count(Coproprietaire.id)
        ).where(
            Coproprietaire.copropriete_id == copropriete_id,
            Coproprietaire.statut_special.isnot(None)
        ).group_by(Coproprietaire.statut_special)

        special_result = await db.execute(special_query)
        special_roles = {row[0]: row[1] for row in special_result.all()}

        return {
            "copropriete_id": copropriete_id,
            "nom": copropriete.nom,
            "total_coproprietaires": total,
            "by_statut": by_statut,
            "special_roles": special_roles,
            "nombre_lots": copropriete.nombre_lots,
            "nombre_batiments": copropriete.nombre_batiments
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("copropriete_stats_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )
