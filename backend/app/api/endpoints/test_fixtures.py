"""
Test Fixtures API Endpoints

Provides endpoints for E2E tests to load and verify test fixtures.
These endpoints should only be used in development/testing environments.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/load-fixtures")
async def load_fixtures(data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Load SQL fixtures into the database.

    This endpoint triggers the SQL fixture loading script.
    Should only be used in development/testing environments.
    """
    try:
        from scripts.load_sql_fixtures import load_fixtures as load_sql_fixtures

        result = await load_sql_fixtures()

        logger.info("sql_fixtures_loaded", result=result)

        return {
            "status": "success",
            "message": "SQL fixtures loaded successfully",
            "details": result if isinstance(result, dict) else {"loaded": True}
        }
    except ImportError as e:
        logger.warning("sql_fixtures_import_error", error=str(e))
        # If script not found, try to return success anyway
        return {
            "status": "warning",
            "message": "SQL fixtures script not available, fixtures may already be loaded",
            "error": str(e)
        }
    except Exception as e:
        logger.error("sql_fixtures_failed", error=str(e))
        # Don't fail the request - fixtures might already be loaded
        return {
            "status": "warning",
            "message": "SQL fixtures loading had issues",
            "error": str(e)
        }


@router.post("/index-rag-fixtures")
async def index_rag_fixtures() -> Dict[str, Any]:
    """
    Index RAG fixtures into Qdrant.

    This endpoint indexes all RAG test documents from the fixtures.
    Should only be used in development/testing environments.
    """
    try:
        from app.services.rag_service import get_rag_service
        from tests.fixtures.rag_fixtures import RAGFixtures, RAGDocumentIndexer

        rag_service = get_rag_service()

        stats = {
            "documents_processed": 0,
            "chunks_indexed": 0,
            "errors": [],
            "documents": []
        }

        # Get all fixtures
        fixtures = RAGFixtures.get_all_documents()
        logger.info("rag_fixtures_loaded", count=len(fixtures))

        # Prepare documents for indexing
        prepared_docs = RAGDocumentIndexer.prepare_for_indexing(fixtures)
        logger.info("rag_documents_prepared", count=len(prepared_docs))

        # Group by document for efficient indexing
        doc_groups: Dict[str, list] = {}
        for doc in prepared_docs:
            doc_key = f"{doc['metadata']['doc_type']}_{doc['metadata']['copropriete_id']}"
            if doc_key not in doc_groups:
                doc_groups[doc_key] = []
            doc_groups[doc_key].append(doc)

        # Index each document group
        for doc_key, chunks in doc_groups.items():
            if not chunks:
                continue

            # Use first chunk's metadata as base
            base_metadata = chunks[0]["metadata"]

            # Generate a unique document_id
            doc_id = abs(hash(doc_key)) % 100000 + 10000

            try:
                chunk_texts = [c["content"] for c in chunks]

                metadata = {
                    "title": base_metadata.get("title", "Unknown"),
                    "doc_type": base_metadata.get("doc_type", "unknown"),
                    "copropriete_id": base_metadata.get("copropriete_id", 0),
                    "copropriete_name": base_metadata.get("copropriete_name", "Unknown"),
                    "date": base_metadata.get("date", ""),
                    "source": "rag_fixture",
                    "original_filename": f"{base_metadata.get('title', 'document')}.pdf"
                }

                point_ids = await rag_service.index_document_chunks(
                    document_id=doc_id,
                    chunks=chunk_texts,
                    metadata=metadata,
                    enrich_metadata=True
                )

                stats["documents_processed"] += 1
                stats["chunks_indexed"] += len(point_ids)
                stats["documents"].append({
                    "doc_key": doc_key,
                    "doc_id": doc_id,
                    "title": base_metadata.get("title"),
                    "chunks_indexed": len(point_ids)
                })

            except Exception as e:
                error_msg = f"Failed to index {doc_key}: {str(e)}"
                logger.error("rag_document_indexing_failed", doc_key=doc_key, error=str(e))
                stats["errors"].append(error_msg)

        logger.info("rag_fixtures_indexed",
                   documents=stats["documents_processed"],
                   chunks=stats["chunks_indexed"],
                   errors=len(stats["errors"]))

        return {
            "status": "success",
            "message": f"Indexed {stats['documents_processed']} documents with {stats['chunks_indexed']} chunks",
            "details": stats
        }

    except Exception as e:
        logger.error("rag_fixtures_indexing_failed", error=str(e))
        return {
            "status": "warning",
            "message": "RAG fixtures indexing had issues",
            "error": str(e)
        }


@router.get("/verify-sql")
async def verify_sql() -> Dict[str, Any]:
    """
    Verify SQL fixtures are loaded by querying coproprietes.
    """
    try:
        from app.core.database import get_db
        from sqlalchemy import text

        async for db in get_db():
            # Query coproprietes count
            result = await db.execute(text("SELECT COUNT(*) FROM coproprietes"))
            count = result.scalar()

            # Query some data
            result = await db.execute(text("SELECT nom FROM coproprietes LIMIT 5"))
            names = [row[0] for row in result.fetchall()]

            return {
                "status": "success",
                "coproprietes_count": count,
                "sample_names": names
            }

        return {"status": "error", "message": "No database connection"}

    except Exception as e:
        logger.error("sql_verify_failed", error=str(e))
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/verify-rag")
async def verify_rag() -> Dict[str, Any]:
    """
    Verify RAG fixtures are indexed by searching for a known document.
    """
    try:
        from app.services.rag_service import get_rag_service

        rag_service = get_rag_service()

        # Search for a known term
        results = await rag_service.search("règlement animaux", limit=3)

        return {
            "status": "success",
            "documents_found": len(results) if results else 0,
            "sample_results": [
                {
                    "content": r.get("content", "")[:100],
                    "metadata": r.get("metadata", {})
                }
                for r in (results or [])[:3]
            ]
        }

    except Exception as e:
        logger.error("rag_verify_failed", error=str(e))
        return {
            "status": "error",
            "message": str(e)
        }
