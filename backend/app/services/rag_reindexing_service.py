"""
RAG Reindexing Service
Détecte les changements de schéma et déclenche réindexation automatique

Architecture:
- Détection de schema drift sur colonnes indexées
- Réindexation par batch (éviter surcharge)
- API admin pour déclencher manuellement
- Métriques et observabilité
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.services.schema_introspection_service import get_schema_service
from app.services.rag_service import RAGService

logger = structlog.get_logger(__name__)


class RAGReindexingService:
    """
    Gère la réindexation RAG lors de changements de schéma

    Capacités:
    - Détecte si des colonnes indexées ont changé
    - Réindexe par batch (pas toute la DB d'un coup)
    - Supporte professionnels, documents, autres entités
    - Métriques et logs détaillés
    """

    # Configuration des tables indexées dans RAG
    # Pour chaque table: text_fields (fulltext search) + metadata_fields (filters)
    INDEXED_TABLES = {
        "professionnels": {
            "text_fields": ["name", "company_name", "description"],
            "metadata_fields": ["category", "city", "rating", "siret", "statut"],
            "id_field": "id",
            "is_indexed_field": "is_indexed",
        },
        "documents": {
            "text_fields": ["extracted_text", "filename"],
            "metadata_fields": ["document_type", "mime_type", "file_type"],
            "id_field": "id",
            "is_indexed_field": None,  # Pas de colonne is_indexed pour documents
        },
        "coproprietes": {
            "text_fields": ["nom", "adresse"],
            "metadata_fields": ["ville", "code_postal", "type_copropriete"],
            "id_field": "id",
            "is_indexed_field": "is_indexed",
        },
    }

    DEFAULT_BATCH_SIZE = 100

    def __init__(self):
        self.schema_service = get_schema_service()
        self.rag_service = RAGService()

    async def detect_indexed_field_changes(
        self,
        db: AsyncSession,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Détecte si des colonnes indexées ont changé dans une table

        Args:
            db: Session database
            table_name: Nom de la table à vérifier

        Returns:
            Dict avec:
                - needs_reindexing: bool
                - affected_fields: List[tuple] (action, field_name)
                - reason: str
                - table: str
        """
        if table_name not in self.INDEXED_TABLES:
            return {
                "needs_reindexing": False,
                "reason": f"Table '{table_name}' not indexed in RAG",
                "table": table_name,
            }

        # Détecter changements de schéma
        schema_changes = await self.schema_service.detect_schema_changes(db, table_name)

        if "error" in schema_changes:
            return {
                "needs_reindexing": False,
                "reason": f"Error detecting schema changes: {schema_changes['error']}",
                "table": table_name,
                "error": schema_changes["error"],
            }

        # Vérifier si colonnes indexées affectées
        config = self.INDEXED_TABLES[table_name]
        all_indexed_fields = config["text_fields"] + config["metadata_fields"]

        affected_fields = []
        for field in all_indexed_fields:
            if field in schema_changes["added_columns"]:
                affected_fields.append(("added", field))
            elif field in schema_changes["removed_columns"]:
                affected_fields.append(("removed", field))

        needs_reindexing = len(affected_fields) > 0

        result = {
            "needs_reindexing": needs_reindexing,
            "affected_fields": affected_fields,
            "table": table_name,
            "schema_changes": schema_changes,
        }

        if needs_reindexing:
            result["reason"] = f"{len(affected_fields)} indexed field(s) changed"
            logger.warning(
                "reindexing_required",
                table=table_name,
                affected_fields=affected_fields
            )
        else:
            result["reason"] = "No indexed fields affected"

        return result

    async def get_records_to_reindex(
        self,
        db: AsyncSession,
        table_name: str,
        limit: Optional[int] = None
    ) -> List[int]:
        """
        Récupère les IDs des enregistrements à réindexer

        Args:
            db: Session database
            table_name: Table à réindexer
            limit: Limite (pour batch partiel)

        Returns:
            Liste d'IDs
        """
        from sqlalchemy import text

        config = self.INDEXED_TABLES[table_name]
        id_field = config["id_field"]
        is_indexed_field = config.get("is_indexed_field")

        # Construire requête
        if is_indexed_field:
            # Seulement records avec is_indexed = TRUE
            query = f"SELECT {id_field} FROM {table_name} WHERE {is_indexed_field} = TRUE"
        else:
            # Tous les records actifs
            query = f"SELECT {id_field} FROM {table_name}"

        # Ajouter LIMIT si spécifié
        if limit:
            query += f" LIMIT {limit}"

        result = await db.execute(text(query))
        ids = [row[0] for row in result.fetchall()]

        logger.info(
            "records_to_reindex_retrieved",
            table=table_name,
            count=len(ids),
            limited=limit is not None
        )

        return ids

    async def reindex_professionnels_batch(
        self,
        db: AsyncSession,
        ids: List[int]
    ) -> Dict[str, Any]:
        """
        Réindexe un batch de professionnels

        Args:
            db: Session database
            ids: Liste d'IDs à réindexer

        Returns:
            Dict avec success, reindexed_count, errors
        """
        from app.models.professionnel import Professionnel

        reindexed_count = 0
        errors = []

        # Charger les records
        stmt = select(Professionnel).where(Professionnel.id.in_(ids))
        result = await db.execute(stmt)
        professionnels = result.scalars().all()

        for prof in professionnels:
            try:
                # Construire texte pour fulltext search
                text_parts = [
                    prof.name or "",
                    prof.company_name or "",
                    prof.description or "",
                ]
                text = " ".join(filter(None, text_parts))

                # Construire metadata (pour filtres)
                metadata = {
                    "category": prof.category,
                    "city": prof.city,
                    "rating": float(prof.rating) if prof.rating else None,
                    "siret": prof.siret,
                    "statut": prof.statut,
                    "table": "professionnels",
                }

                # Ajouter toutes les colonnes disponibles dynamiquement
                # (pour supporter nouvelles colonnes sans changer le code)
                all_columns = self.schema_service.get_table_columns("professionnels")
                for col_info in all_columns:
                    col_name = col_info["name"]
                    if col_name not in ["id", "name", "company_name", "description", "hashed_password"]:
                        value = getattr(prof, col_name, None)
                        if value is not None:
                            # Convertir types complexes en string pour Qdrant
                            if isinstance(value, (list, dict)):
                                metadata[col_name] = str(value)
                            else:
                                metadata[col_name] = value

                # Indexer dans Qdrant
                await self.rag_service.index_document(
                    document_id=prof.id,
                    text=text,
                    metadata=metadata
                )

                reindexed_count += 1

            except Exception as e:
                logger.error(
                    "professionnel_reindex_failed",
                    professionnel_id=prof.id,
                    error=str(e)
                )
                errors.append({
                    "id": prof.id,
                    "error": str(e)
                })

        return {
            "success": len(errors) == 0,
            "reindexed_count": reindexed_count,
            "errors": errors,
            "total_requested": len(ids)
        }

    async def reindex_documents_batch(
        self,
        db: AsyncSession,
        ids: List[int]
    ) -> Dict[str, Any]:
        """
        Réindexe un batch de documents

        Args:
            db: Session database
            ids: Liste d'IDs à réindexer

        Returns:
            Dict avec success, reindexed_count, errors
        """
        from app.models.document import Document

        reindexed_count = 0
        errors = []

        # Charger les records
        stmt = select(Document).where(Document.id.in_(ids))
        result = await db.execute(stmt)
        documents = result.scalars().all()

        for doc in documents:
            try:
                # Construire texte
                text_parts = [
                    doc.extracted_text or "",
                    doc.filename or "",
                ]
                text = " ".join(filter(None, text_parts))

                # Construire metadata
                metadata = {
                    "document_type": doc.document_type,
                    "mime_type": doc.mime_type,
                    "file_type": doc.file_type,
                    "table": "documents",
                }

                # Ajouter colonnes dynamiques
                all_columns = self.schema_service.get_table_columns("documents")
                for col_info in all_columns:
                    col_name = col_info["name"]
                    if col_name not in ["id", "extracted_text", "filename"]:
                        value = getattr(doc, col_name, None)
                        if value is not None:
                            if isinstance(value, (list, dict)):
                                metadata[col_name] = str(value)
                            else:
                                metadata[col_name] = value

                # Indexer
                await self.rag_service.index_document(
                    document_id=doc.id,
                    text=text,
                    metadata=metadata
                )

                reindexed_count += 1

            except Exception as e:
                logger.error(
                    "document_reindex_failed",
                    document_id=doc.id,
                    error=str(e)
                )
                errors.append({
                    "id": doc.id,
                    "error": str(e)
                })

        return {
            "success": len(errors) == 0,
            "reindexed_count": reindexed_count,
            "errors": errors,
            "total_requested": len(ids)
        }

    async def reindex_coproprietes_batch(
        self,
        db: AsyncSession,
        ids: List[int]
    ) -> Dict[str, Any]:
        """
        Réindexe un batch de copropriétés

        Args:
            db: Session database
            ids: Liste d'IDs à réindexer

        Returns:
            Dict avec success, reindexed_count, errors
        """
        from app.models.copropriete import Copropriete

        reindexed_count = 0
        errors = []

        # Charger les records
        stmt = select(Copropriete).where(Copropriete.id.in_(ids))
        result = await db.execute(stmt)
        coproprietes = result.scalars().all()

        for copro in coproprietes:
            try:
                # Construire texte
                text_parts = [
                    copro.nom or "",
                    copro.adresse or "",
                    copro.ville or "",
                ]
                text = " ".join(filter(None, text_parts))

                # Construire metadata
                metadata = {
                    "ville": copro.ville,
                    "code_postal": copro.code_postal,
                    "type_copropriete": copro.type_copropriete,
                    "table": "coproprietes",
                }

                # Ajouter colonnes dynamiques
                all_columns = self.schema_service.get_table_columns("coproprietes")
                for col_info in all_columns:
                    col_name = col_info["name"]
                    if col_name not in ["id", "nom", "adresse"]:
                        value = getattr(copro, col_name, None)
                        if value is not None:
                            if isinstance(value, (list, dict)):
                                metadata[col_name] = str(value)
                            else:
                                metadata[col_name] = value

                # Indexer
                await self.rag_service.index_document(
                    document_id=copro.id,
                    text=text,
                    metadata=metadata
                )

                reindexed_count += 1

            except Exception as e:
                logger.error(
                    "copropriete_reindex_failed",
                    copropriete_id=copro.id,
                    error=str(e)
                )
                errors.append({
                    "id": copro.id,
                    "error": str(e)
                })

        return {
            "success": len(errors) == 0,
            "reindexed_count": reindexed_count,
            "errors": errors,
            "total_requested": len(ids)
        }

    async def reindex_table(
        self,
        db: AsyncSession,
        table_name: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_records: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Réindexe TOUS les enregistrements d'une table (ou jusqu'à max_records)

        Args:
            db: Session database
            table_name: Table à réindexer
            batch_size: Taille des batchs
            max_records: Limite max de records (None = tous)

        Returns:
            Dict avec:
                - success: bool
                - total_reindexed: int
                - batches_processed: int
                - errors: List[Dict]
                - duration_ms: int
        """
        import time

        if table_name not in self.INDEXED_TABLES:
            return {
                "success": False,
                "error": f"Table '{table_name}' not configured for indexing",
                "table": table_name,
            }

        start_time = time.time()

        logger.info(
            "reindexing_started",
            table=table_name,
            batch_size=batch_size,
            max_records=max_records
        )

        # Récupérer tous les IDs
        ids = await self.get_records_to_reindex(db, table_name, limit=max_records)

        if not ids:
            logger.warning("no_records_to_reindex", table=table_name)
            return {
                "success": True,
                "total_reindexed": 0,
                "batches_processed": 0,
                "errors": [],
                "duration_ms": int((time.time() - start_time) * 1000),
                "message": "No records to reindex"
            }

        # Sélectionner méthode de réindexation selon la table
        if table_name == "professionnels":
            reindex_batch_func = self.reindex_professionnels_batch
        elif table_name == "documents":
            reindex_batch_func = self.reindex_documents_batch
        elif table_name == "coproprietes":
            reindex_batch_func = self.reindex_coproprietes_batch
        else:
            return {
                "success": False,
                "error": f"No reindexing function for table '{table_name}'",
                "table": table_name,
            }

        # Réindexer par batch
        total_reindexed = 0
        all_errors = []
        batches_processed = 0

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]

            logger.info(
                "processing_batch",
                table=table_name,
                batch=batches_processed + 1,
                batch_size=len(batch_ids),
                total_batches=(len(ids) + batch_size - 1) // batch_size
            )

            batch_result = await reindex_batch_func(db, batch_ids)

            total_reindexed += batch_result["reindexed_count"]
            all_errors.extend(batch_result.get("errors", []))
            batches_processed += 1

            logger.info(
                "batch_completed",
                table=table_name,
                batch=batches_processed,
                reindexed=batch_result["reindexed_count"],
                errors=len(batch_result.get("errors", []))
            )

        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "success": len(all_errors) == 0,
            "total_reindexed": total_reindexed,
            "batches_processed": batches_processed,
            "errors": all_errors,
            "duration_ms": duration_ms,
            "table": table_name,
        }

        logger.info(
            "reindexing_completed",
            **result
        )

        return result

    def get_indexed_tables_list(self) -> List[str]:
        """
        Retourne la liste des tables indexées dans RAG

        Returns:
            Liste des noms de tables
        """
        return list(self.INDEXED_TABLES.keys())

    def get_table_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Retourne la configuration d'indexation d'une table

        Args:
            table_name: Nom de la table

        Returns:
            Config ou None si table non indexée
        """
        return self.INDEXED_TABLES.get(table_name)


# ============================================================================
# Singleton Pattern
# ============================================================================

_reindexing_service_instance: Optional[RAGReindexingService] = None


def get_reindexing_service() -> RAGReindexingService:
    """
    Récupère l'instance singleton du RAGReindexingService

    Returns:
        Instance singleton
    """
    global _reindexing_service_instance
    if _reindexing_service_instance is None:
        _reindexing_service_instance = RAGReindexingService()
    return _reindexing_service_instance
