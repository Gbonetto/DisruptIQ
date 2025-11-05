"""
Vendor Indexing Service
Converts vendors to searchable text and indexes them in Qdrant
"""

import structlog
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.models.professionnel import Vendor  # Vendor est un alias de Professionnel
from app.services.rag_service import get_rag_service

logger = structlog.get_logger()


class VendorIndexService:
    """Service for indexing vendors in Qdrant for RAG"""

    def __init__(self):
        self.rag_service = get_rag_service()

    def vendor_to_text(self, vendor: Vendor) -> str:
        """
        Convert a vendor object to searchable text

        Args:
            vendor: Vendor model instance

        Returns:
            Formatted text representation
        """
        # Build comprehensive text representation
        text_parts = [
            f"FOURNISSEUR: {vendor.name}",
            f"Type: {vendor.category}" if vendor.category else None,
        ]

        if vendor.company_name:
            text_parts.append(f"Entreprise: {vendor.company_name}")

        # Contact information
        text_parts.append(f"Email: {vendor.email}")
        if vendor.phone:
            text_parts.append(f"Téléphone: {vendor.phone}")

        # Location
        if vendor.address:
            text_parts.append(f"Adresse: {vendor.address}")
        if vendor.city:
            text_parts.append(f"Ville: {vendor.city}")
        if vendor.postal_code:
            text_parts.append(f"Code postal: {vendor.postal_code}")

        # Specialties
        if vendor.specialties:
            specialties_text = ", ".join(vendor.specialties)
            text_parts.append(f"Spécialités: {specialties_text}")

        # Performance data
        if vendor.rating and vendor.rating > 0:
            text_parts.append(f"Note: {vendor.rating}/5")
        if vendor.total_jobs and vendor.total_jobs > 0:
            text_parts.append(f"Nombre d'interventions: {vendor.total_jobs}")

        # Notes
        if vendor.notes:
            text_parts.append(f"Notes: {vendor.notes}")

        # Filter None values and join
        text = "\n".join([part for part in text_parts if part])

        return text

    async def index_vendor(self, vendor: Vendor, db: Optional[AsyncSession] = None) -> bool:
        """
        Index a single vendor in Qdrant and update database status

        Args:
            vendor: Vendor to index
            db: Database session (optional, for updating is_indexed status)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert vendor to text
            text = self.vendor_to_text(vendor)

            # Prepare metadata
            metadata = {
                "source": "vendor",
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "vendor_email": vendor.email,
                "category": vendor.category or "Non spécifié",
                "city": vendor.city or "Non spécifié",
            }

            # Index in Qdrant using a special document_id format
            # We use negative IDs to distinguish vendors from documents
            qdrant_doc_id = -vendor.id  # Negative to avoid conflict with real documents

            await self.rag_service.index_document(
                document_id=qdrant_doc_id,
                text=text,
                metadata=metadata
            )

            # Update database status if db session provided
            if db:
                vendor.is_indexed = True
                vendor.last_indexed_at = datetime.now(timezone.utc)
                db.add(vendor)
                await db.commit()

            logger.info(
                "vendor_indexed",
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                db_updated=db is not None
            )

            return True

        except Exception as e:
            logger.error(
                "vendor_indexing_failed",
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                error=str(e)
            )
            return False

    async def index_vendors_batch(self, vendors: List[Vendor], db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Index multiple vendors in batch

        Args:
            vendors: List of vendors to index
            db: Database session (optional, for updating is_indexed status)

        Returns:
            Dictionary with indexing results
        """
        indexed_count = 0
        failed_count = 0
        errors = []

        for vendor in vendors:
            try:
                success = await self.index_vendor(vendor, db=db)
                if success:
                    indexed_count += 1
                else:
                    failed_count += 1
                    errors.append({
                        "vendor_id": vendor.id,
                        "vendor_name": vendor.name,
                        "error": "Indexing returned False"
                    })

            except Exception as e:
                failed_count += 1
                errors.append({
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "error": str(e)
                })
                logger.error(
                    "vendor_batch_index_error",
                    vendor_id=vendor.id,
                    error=str(e)
                )

        result = {
            "total": len(vendors),
            "indexed": indexed_count,
            "failed": failed_count,
            "errors": errors
        }

        logger.info(
            "vendor_batch_indexing_complete",
            total=len(vendors),
            indexed=indexed_count,
            failed=failed_count
        )

        return result

    async def reindex_all_vendors(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Reindex all vendors from database and update their indexed status

        Args:
            db: Database session

        Returns:
            Dictionary with reindexing results
        """
        try:
            # Fetch all vendors
            result = await db.execute(select(Vendor))
            vendors = result.scalars().all()

            logger.info("reindexing_all_vendors", count=len(vendors))

            # Index in batch with database updates
            index_result = await self.index_vendors_batch(vendors, db=db)

            return {
                "status": "success",
                **index_result
            }

        except Exception as e:
            logger.error("reindex_all_vendors_failed", error=str(e))
            return {
                "status": "error",
                "message": str(e),
                "total": 0,
                "indexed": 0,
                "failed": 0
            }

    async def remove_vendor_from_index(self, vendor_id: int, db: Optional[AsyncSession] = None) -> bool:
        """
        Remove a vendor from Qdrant index and update database status

        Args:
            vendor_id: ID of the vendor to remove
            db: Database session (optional, for updating is_indexed status)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use negative document_id format
            qdrant_doc_id = -vendor_id

            await self.rag_service.delete_document(qdrant_doc_id)

            # Update database status if db session provided
            if db:
                result = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
                vendor = result.scalar_one_or_none()
                if vendor:
                    vendor.is_indexed = False
                    vendor.last_indexed_at = None
                    db.add(vendor)
                    await db.commit()

            logger.info("vendor_removed_from_index", vendor_id=vendor_id, db_updated=db is not None)
            return True

        except Exception as e:
            logger.error(
                "vendor_removal_failed",
                vendor_id=vendor_id,
                error=str(e)
            )
            return False
