"""
Admin Panel Endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pydantic import BaseModel
from typing import List
import structlog
import csv
import io

from app.core.database import get_db
from app.models.vendor import Vendor
from app.models.email import Email
from app.models.document import Document
from app.models.user import User
from app.schemas.vendor import VendorCreate, VendorResponse
from app.services.vendor_index_service import VendorIndexService

router = APIRouter()
logger = structlog.get_logger()


class SystemStats(BaseModel):
    """System statistics"""
    total_emails: int
    total_documents: int
    total_vendors: int
    total_users: int


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Get system statistics"""
    # Count all entities from database
    total_emails = await db.scalar(select(func.count()).select_from(Email))
    total_documents = await db.scalar(select(func.count()).select_from(Document))
    total_vendors = await db.scalar(select(func.count()).select_from(Vendor))
    total_users = await db.scalar(select(func.count()).select_from(User))

    return {
        "total_emails": total_emails or 0,
        "total_documents": total_documents or 0,
        "total_vendors": total_vendors or 0,
        "total_users": total_users or 0
    }


@router.post("/vendors/import-csv")
async def import_vendors_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Import vendors from CSV file

    Expected CSV format:
    name,company_name,email,phone,category,specialties,address,city,postal_code
    """
    try:
        # Read CSV with automatic encoding detection
        contents = await file.read()

        # Try multiple encodings
        csv_data = None
        encodings = ['utf-8', 'iso-8859-1', 'windows-1252', 'cp1252']

        for encoding in encodings:
            try:
                csv_data = contents.decode(encoding)
                logger.info("csv_encoding_detected", encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if csv_data is None:
            raise HTTPException(
                status_code=400,
                detail="Unable to decode CSV file. Please ensure it's a valid CSV file."
            )

        # Auto-detect CSV delimiter (comma or semicolon)
        try:
            sample = csv_data[:1024]  # Sample first 1KB
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            logger.info("csv_delimiter_detected", delimiter=delimiter)
        except Exception as e:
            # Fallback to comma if detection fails
            delimiter = ','
            logger.warning("csv_delimiter_detection_failed_using_default", error=str(e))

        csv_reader = csv.DictReader(io.StringIO(csv_data), delimiter=delimiter)

        vendors_created = 0
        vendors_skipped = 0
        vendors_reindexed = 0
        errors = []
        vendors_to_reindex = []

        for row in csv_reader:
            try:
                email = row.get("email")

                # Skip rows without email
                if not email:
                    errors.append({
                        "row": row,
                        "error": "Missing email address"
                    })
                    continue

                # Validate email format
                from pydantic import EmailStr, ValidationError
                try:
                    EmailStr._validate(email)
                except (ValidationError, ValueError) as e:
                    errors.append({
                        "row": row,
                        "error": f"Invalid email format: {email}"
                    })
                    logger.warning("invalid_email_skipped", email=email)
                    continue

                # Check if vendor already exists by email
                existing = await db.execute(
                    select(Vendor).where(Vendor.email == email)
                )
                existing_vendor = existing.scalar_one_or_none()

                if existing_vendor:
                    # If exists but not indexed, add to reindex list
                    if not existing_vendor.is_indexed:
                        vendors_to_reindex.append(existing_vendor)
                        logger.info("vendor_exists_not_indexed_will_reindex", email=email)
                    else:
                        vendors_skipped += 1
                        logger.debug("vendor_already_exists_and_indexed", email=email)
                    continue

                # Parse specialties - support both | and ; separators
                specialties_raw = row.get("specialties", "")
                if specialties_raw:
                    # Remove quotes if present
                    specialties_raw = specialties_raw.strip('"').strip("'")
                    # Split by | or ; (whichever is present)
                    if "|" in specialties_raw:
                        specialties = [s.strip() for s in specialties_raw.split("|") if s.strip()]
                    elif ";" in specialties_raw:
                        specialties = [s.strip() for s in specialties_raw.split(";") if s.strip()]
                    else:
                        specialties = [specialties_raw.strip()]
                else:
                    specialties = []

                # Create vendor in database
                vendor = Vendor(
                    name=row.get("name"),
                    company_name=row.get("company_name"),
                    email=email,
                    phone=row.get("phone"),
                    category=row.get("category"),
                    specialties=specialties,
                    address=row.get("address"),
                    city=row.get("city"),
                    postal_code=row.get("postal_code")
                )

                db.add(vendor)
                vendors_created += 1
                logger.info("vendor_imported", name=vendor.name, email=email)

            except Exception as e:
                errors.append({
                    "row": row,
                    "error": str(e)
                })
                logger.error("vendor_import_error", row=row, error=str(e))

        # Commit all vendors at once
        await db.commit()
        logger.info("vendors_csv_import_complete", created=vendors_created, skipped=vendors_skipped)

        # Index newly created vendors and reindex existing non-indexed vendors in Qdrant for RAG
        indexed_count = 0
        index_errors = 0

        if vendors_created > 0 or len(vendors_to_reindex) > 0:
            try:
                index_service = VendorIndexService()
                vendors_to_index = []

                # Fetch newly created vendors
                if vendors_created > 0:
                    logger.info("fetching_newly_created_vendors", count=vendors_created)
                    result = await db.execute(select(Vendor).order_by(Vendor.created_at.desc()).limit(vendors_created))
                    new_vendors = result.scalars().all()
                    vendors_to_index.extend(new_vendors)

                # Add existing vendors that need reindexing
                if vendors_to_reindex:
                    logger.info("reindexing_existing_vendors", count=len(vendors_to_reindex))
                    vendors_to_index.extend(vendors_to_reindex)
                    vendors_reindexed = len(vendors_to_reindex)

                # Index all in batch with database status updates
                logger.info("indexing_vendors_in_qdrant", total_count=len(vendors_to_index))
                index_result = await index_service.index_vendors_batch(vendors_to_index, db=db)
                indexed_count = index_result['indexed']
                index_errors = index_result['failed']

                logger.info("vendors_indexed", indexed=indexed_count, failed=index_errors, reindexed=vendors_reindexed)

            except Exception as e:
                logger.error("vendor_indexing_failed_after_import", error=str(e))
                # Don't fail the whole import if indexing fails
                index_errors = vendors_created + len(vendors_to_reindex)

        return {
            "status": "success",
            "vendors_created": vendors_created,
            "vendors_skipped": vendors_skipped,
            "vendors_reindexed": vendors_reindexed,
            "vendors_indexed": indexed_count,
            "index_errors": index_errors,
            "errors": errors,
            "error_count": len(errors)
        }

    except Exception as e:
        await db.rollback()
        logger.error("csv_import_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import CSV: {str(e)}"
        )


@router.get("/vendors", response_model=List[VendorResponse])
async def list_vendors(
    category: str = None,
    city: str = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List vendors with optional filters"""
    query = select(Vendor)

    # Apply filters
    if category:
        query = query.where(Vendor.category == category)
    if city:
        query = query.where(Vendor.city == city)

    query = query.limit(limit)

    result = await db.execute(query)
    vendors = result.scalars().all()

    return vendors


@router.post("/vendors", response_model=VendorResponse)
async def create_vendor(vendor: VendorCreate):
    """Create a new vendor"""
    # TODO: Save to database
    return {
        **vendor.dict(),
        "id": 1,
        "rating": 0.0,
        "total_jobs": 0,
        "last_contacted": None,
        "created_at": "2024-10-30T00:00:00Z"
    }


@router.put("/vendors/{vendor_id}", response_model=VendorResponse)
async def update_vendor(vendor_id: int, vendor: VendorCreate):
    """Update a vendor"""
    # TODO: Update in database
    return {
        **vendor.dict(),
        "id": vendor_id,
        "rating": 0.0,
        "total_jobs": 0,
        "last_contacted": None,
        "created_at": "2024-10-30T00:00:00Z"
    }


@router.delete("/vendors/{vendor_id}")
async def delete_vendor(vendor_id: int):
    """Delete a vendor"""
    # TODO: Delete from database
    return {
        "message": "Vendor deleted",
        "vendor_id": vendor_id
    }


@router.get("/n8n/config")
async def get_n8n_config():
    """Get N8N configuration"""
    # TODO: Return from config (masked)
    return {
        "base_url": "configured",
        "status": "connected"
    }


@router.post("/n8n/test")
async def test_n8n_connection():
    """Test N8N connection"""
    # TODO: Ping N8N
    return {
        "status": "success",
        "message": "N8N connection successful"
    }


@router.post("/vendors/reindex")
async def reindex_all_vendors(db: AsyncSession = Depends(get_db)):
    """
    Reindex all vendors in Qdrant for RAG search

    This endpoint indexes all vendors from the database into Qdrant,
    allowing the AI assistant to search and retrieve vendor information.

    Use this if:
    - The assistant cannot find vendors
    - After bulk imports
    - After database migrations
    """
    try:
        logger.info("manual_reindex_requested")

        index_service = VendorIndexService()
        result = await index_service.reindex_all_vendors(db)

        if result['status'] == 'success':
            logger.info(
                "reindex_complete",
                total=result['total'],
                indexed=result['indexed'],
                failed=result['failed']
            )

            return {
                "status": "success",
                "message": f"Indexed {result['indexed']} vendors successfully",
                "total_vendors": result['total'],
                "indexed": result['indexed'],
                "failed": result['failed'],
                "errors": result.get('errors', [])
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Reindexing failed: {result.get('message', 'Unknown error')}"
            )

    except Exception as e:
        logger.error("reindex_endpoint_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reindex vendors: {str(e)}"
        )


@router.delete("/vendors/all")
async def delete_all_vendors(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete ALL vendors from PostgreSQL and Qdrant

    WARNING: This is a destructive operation that cannot be undone!

    Args:
        confirm: Must be True to proceed with deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to proceed."
        )

    try:
        logger.warning("delete_all_vendors_requested")

        # Count vendors before deletion
        total_vendors = await db.scalar(select(func.count()).select_from(Vendor))

        # Delete from Qdrant first
        index_service = VendorIndexService()
        result = await db.execute(select(Vendor))
        vendors = result.scalars().all()

        qdrant_deleted = 0
        for vendor in vendors:
            try:
                await index_service.remove_vendor_from_index(vendor.id)
                qdrant_deleted += 1
            except Exception as e:
                logger.warning("qdrant_delete_failed", vendor_id=vendor.id, error=str(e))

        # Delete from PostgreSQL
        await db.execute(delete(Vendor))
        await db.commit()

        logger.warning(
            "all_vendors_deleted",
            total=total_vendors,
            postgres_deleted=total_vendors,
            qdrant_deleted=qdrant_deleted
        )

        return {
            "status": "success",
            "message": f"Deleted {total_vendors} vendors",
            "postgres_deleted": total_vendors,
            "qdrant_deleted": qdrant_deleted
        }

    except Exception as e:
        await db.rollback()
        logger.error("delete_all_vendors_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete vendors: {str(e)}"
        )


@router.delete("/documents/all")
async def delete_all_documents(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete ALL documents from PostgreSQL and Qdrant

    WARNING: This is a destructive operation that cannot be undone!

    Args:
        confirm: Must be True to proceed with deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to proceed."
        )

    try:
        logger.warning("delete_all_documents_requested")

        # Count documents before deletion
        total_docs = await db.scalar(select(func.count()).select_from(Document))

        # Delete from Qdrant
        # TODO: Implement document deletion from Qdrant
        # For now, we'll just delete from PostgreSQL

        # Delete from PostgreSQL
        await db.execute(delete(Document))
        await db.commit()

        logger.warning("all_documents_deleted", total=total_docs)

        return {
            "status": "success",
            "message": f"Deleted {total_docs} documents",
            "postgres_deleted": total_docs
        }

    except Exception as e:
        await db.rollback()
        logger.error("delete_all_documents_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete documents: {str(e)}"
        )


@router.delete("/emails/all")
async def delete_all_emails(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete ALL emails from PostgreSQL

    WARNING: This is a destructive operation that cannot be undone!

    Args:
        confirm: Must be True to proceed with deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to proceed."
        )

    try:
        logger.warning("delete_all_emails_requested")

        # Count emails before deletion
        total_emails = await db.scalar(select(func.count()).select_from(Email))

        # Delete from PostgreSQL
        await db.execute(delete(Email))
        await db.commit()

        logger.warning("all_emails_deleted", total=total_emails)

        return {
            "status": "success",
            "message": f"Deleted {total_emails} emails",
            "postgres_deleted": total_emails
        }

    except Exception as e:
        await db.rollback()
        logger.error("delete_all_emails_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete emails: {str(e)}"
        )


@router.post("/reset")
async def reset_all_data(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    NUCLEAR OPTION: Delete ALL data (vendors, documents, emails) from PostgreSQL and Qdrant

    WARNING: This is an EXTREMELY destructive operation that cannot be undone!
    Use this only for development/testing or when you want to start completely fresh.

    Args:
        confirm: Must be True to proceed with deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset not confirmed. Set confirm=true to proceed with complete data wipe."
        )

    try:
        logger.critical("FULL_SYSTEM_RESET_REQUESTED")

        results = {}

        # Delete vendors
        try:
            vendor_result = await delete_all_vendors(confirm=True, db=db)
            results['vendors'] = vendor_result
        except Exception as e:
            results['vendors'] = {"error": str(e)}

        # Delete documents
        try:
            doc_result = await delete_all_documents(confirm=True, db=db)
            results['documents'] = doc_result
        except Exception as e:
            results['documents'] = {"error": str(e)}

        # Delete emails
        try:
            email_result = await delete_all_emails(confirm=True, db=db)
            results['emails'] = email_result
        except Exception as e:
            results['emails'] = {"error": str(e)}

        logger.critical("FULL_SYSTEM_RESET_COMPLETED", results=results)

        return {
            "status": "success",
            "message": "Complete system reset successful",
            "details": results
        }

    except Exception as e:
        logger.critical("FULL_SYSTEM_RESET_FAILED", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset system: {str(e)}"
        )
