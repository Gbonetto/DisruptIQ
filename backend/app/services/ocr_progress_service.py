"""
OCR Progress Service
Tracks OCR processing progress for real-time updates via WebSocket
"""

import structlog
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
from fastapi import WebSocket

logger = structlog.get_logger()


class OCRStatus(str, Enum):
    """OCR processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class OCRProgressService:
    """
    Service for tracking OCR progress and sending real-time updates

    TODO: Implement full progress tracking with:
    - WebSocket broadcasting
    - Progress persistence (Redis)
    - Cost estimation
    - Time estimation
    """

    def __init__(self):
        self._progress: Dict[str, Dict[str, Any]] = {}
        self._websockets: Dict[str, list] = {}
        logger.info("ocr_progress_service_initialized")

    def start_progress(
        self,
        task_id: str,
        filename: str,
        estimated_cost: float = 0.0
    ) -> None:
        """Start tracking progress for a task"""
        self._progress[task_id] = {
            "task_id": task_id,
            "filename": filename,
            "status": OCRStatus.PENDING,
            "progress": 0,
            "estimated_cost": estimated_cost,
            "started_at": datetime.now().isoformat(),
            "message": "Démarrage du traitement OCR..."
        }
        logger.info("ocr_progress_started", task_id=task_id, filename=filename)

    async def update_progress(
        self,
        task_id: str,
        progress: int,
        message: str,
        status: Optional[OCRStatus] = None
    ) -> None:
        """Update progress for a task"""
        if task_id not in self._progress:
            logger.warning("task_not_found", task_id=task_id)
            return

        self._progress[task_id]["progress"] = progress
        self._progress[task_id]["message"] = message

        if status:
            self._progress[task_id]["status"] = status

        if status == OCRStatus.COMPLETED:
            self._progress[task_id]["completed_at"] = datetime.now().isoformat()

        logger.info(
            "ocr_progress_updated",
            task_id=task_id,
            progress=progress,
            status=status
        )

        # TODO: Broadcast to WebSocket clients
        # await self._broadcast_progress(task_id)

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a task"""
        return self._progress.get(task_id)

    def register_websocket(self, task_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection for progress updates"""
        if task_id not in self._websockets:
            self._websockets[task_id] = []
        self._websockets[task_id].append(websocket)
        logger.info("websocket_registered", task_id=task_id)

    def unregister_websocket(self, task_id: str, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection"""
        if task_id in self._websockets:
            try:
                self._websockets[task_id].remove(websocket)
                logger.info("websocket_unregistered", task_id=task_id)
            except ValueError:
                pass

    async def _broadcast_progress(self, task_id: str) -> None:
        """Broadcast progress to all registered WebSocket clients (TODO)"""
        # TODO: Implement WebSocket broadcasting
        pass


# Singleton instance
ocr_progress_service = OCRProgressService()
