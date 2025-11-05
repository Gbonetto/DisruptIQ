"""
Session Manager - Gestion des sessions conversationnelles

Gère le cycle de vie des sessions de chat et la rétention du contexte
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import (
    ConversationSession,
    ConversationTurn,
    UserProfile
)
import structlog

logger = structlog.get_logger(__name__)


class SessionManager:
    """
    Gère les sessions conversationnelles et le contexte
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger.bind(service="session_manager")

    async def create_session(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> ConversationSession:
        """
        Crée une nouvelle session de conversation

        Args:
            user_id: ID utilisateur (None pour anonymous)
            session_id: ID de session personnalisé (génère UUID si None)

        Returns:
            ConversationSession créée
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            turns_count=0,
            topics=[],
            intents_distribution={}
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        self.logger.info(
            "session_created",
            session_id=session_id,
            user_id=user_id
        )

        return session

    async def get_session(
        self,
        session_id: str,
        create_if_not_exists: bool = True
    ) -> Optional[ConversationSession]:
        """
        Récupère une session existante

        Args:
            session_id: ID de la session
            create_if_not_exists: Créer si n'existe pas

        Returns:
            ConversationSession ou None
        """
        query = select(ConversationSession).where(
            ConversationSession.session_id == session_id
        )

        result = await self.db.execute(query)
        session = result.scalars().first()

        if not session and create_if_not_exists:
            self.logger.info("session_not_found_creating", session_id=session_id)
            session = await self.create_session(session_id=session_id)

        return session

    async def get_session_history(
        self,
        session_id: str,
        last_n_turns: Optional[int] = 10
    ) -> List[ConversationTurn]:
        """
        Récupère l'historique de conversation d'une session

        Args:
            session_id: ID de la session
            last_n_turns: Nombre de tours à récupérer (défaut: 10, None = tous)

        Returns:
            Liste des ConversationTurn (ordre chronologique)
        """
        session = await self.get_session(session_id, create_if_not_exists=False)
        if not session:
            return []

        query = select(ConversationTurn).where(
            ConversationTurn.session_id == session.id
        ).order_by(desc(ConversationTurn.turn_number))

        # Only apply limit if specified
        if last_n_turns is not None:
            query = query.limit(last_n_turns)

        result = await self.db.execute(query)
        turns = result.scalars().all()

        # Reverse to get chronological order
        return list(reversed(turns))

    async def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        detected_intent: str,
        intent_confidence: float,
        all_intents: Dict[str, float],
        extracted_entities: Dict[str, Any],
        **metadata
    ) -> ConversationTurn:
        """
        Ajoute un tour de conversation à la session

        Args:
            session_id: ID de la session
            user_message: Message utilisateur
            assistant_message: Réponse assistant
            detected_intent: Intent principal détecté
            intent_confidence: Confiance de l'intent
            all_intents: Tous les intents détectés avec scores
            extracted_entities: Entités extraites
            **metadata: Métadonnées additionnelles

        Returns:
            ConversationTurn créé
        """
        session = await self.get_session(session_id)

        # Create turn
        turn = ConversationTurn(
            session_id=session.id,
            turn_number=session.turns_count + 1,
            user_message=user_message,
            user_message_cleaned=metadata.get("user_message_cleaned", user_message),
            detected_intent=detected_intent,
            intent_confidence=intent_confidence,
            all_intents=all_intents,
            sub_intents=metadata.get("sub_intents", []),
            extracted_entities=extracted_entities,
            resolved_entities=metadata.get("resolved_entities", {}),
            assistant_message=assistant_message,
            response_type=metadata.get("response_type", "answer"),
            sources_used=metadata.get("sources_used", []),
            agents_used=metadata.get("agents_used", []),
            execution_plan=metadata.get("execution_plan", {}),
            execution_time_ms=metadata.get("execution_time_ms"),
            orchestrator_mode=metadata.get("orchestrator_mode")
        )

        self.db.add(turn)

        # Update session
        session.turns_count += 1
        session.last_activity_at = datetime.utcnow()

        # Update topics
        if "topic" in metadata and metadata["topic"] not in session.topics:
            session.topics = session.topics + [metadata["topic"]]

        # Update intent distribution
        intents_dist = session.intents_distribution or {}
        intents_dist[detected_intent] = intents_dist.get(detected_intent, 0) + 1
        session.intents_distribution = intents_dist

        # Update current context
        session.current_topic = metadata.get("topic")
        session.current_entities = extracted_entities

        await self.db.commit()
        await self.db.refresh(turn)

        self.logger.info(
            "turn_added",
            session_id=session_id,
            turn_number=turn.turn_number,
            intent=detected_intent
        )

        return turn

    async def update_turn_feedback(
        self,
        turn_id: int,
        satisfied: Optional[bool] = None,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None,
        corrected_intent: Optional[str] = None
    ):
        """
        Met à jour le feedback sur un tour de conversation

        Args:
            turn_id: ID du tour
            satisfied: Utilisateur satisfait ?
            rating: Note 1-5
            feedback_text: Texte de feedback
            corrected_intent: Intent corrigé par l'utilisateur
        """
        query = select(ConversationTurn).where(ConversationTurn.id == turn_id)
        result = await self.db.execute(query)
        turn = result.scalars().first()

        if not turn:
            self.logger.warning("turn_not_found", turn_id=turn_id)
            return

        if satisfied is not None:
            turn.user_satisfied = satisfied
            turn.was_helpful = satisfied

        if rating is not None:
            turn.feedback_rating = rating
            turn.user_satisfied = rating >= 3

        if feedback_text:
            turn.feedback_text = feedback_text

        if corrected_intent:
            turn.corrected_intent = corrected_intent
            turn.was_helpful = False  # Correction means not helpful

        await self.db.commit()

        self.logger.info(
            "turn_feedback_updated",
            turn_id=turn_id,
            satisfied=satisfied,
            rating=rating
        )

    async def end_session(self, session_id: str):
        """
        Termine une session de conversation

        Args:
            session_id: ID de la session
        """
        session = await self.get_session(session_id, create_if_not_exists=False)
        if not session:
            return

        session.ended_at = datetime.utcnow()
        await self.db.commit()

        self.logger.info(
            "session_ended",
            session_id=session_id,
            turns_count=session.turns_count
        )

    async def cleanup_old_sessions(self, days_old: int = 30):
        """
        Nettoie les sessions inactives de plus de X jours

        Args:
            days_old: Âge minimum en jours
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = select(ConversationSession).where(
            and_(
                ConversationSession.last_activity_at < cutoff_date,
                ConversationSession.ended_at.is_not(None)
            )
        )

        result = await self.db.execute(query)
        old_sessions = result.scalars().all()

        for session in old_sessions:
            await self.db.delete(session)

        await self.db.commit()

        self.logger.info(
            "old_sessions_cleaned",
            count=len(old_sessions),
            days_old=days_old
        )

        return len(old_sessions)

    async def get_user_profile(
        self,
        user_id: int,
        create_if_not_exists: bool = True
    ) -> Optional[UserProfile]:
        """
        Récupère le profil d'un utilisateur

        Args:
            user_id: ID utilisateur
            create_if_not_exists: Créer si n'existe pas

        Returns:
            UserProfile ou None
        """
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.db.execute(query)
        profile = result.scalars().first()

        if not profile and create_if_not_exists:
            profile = UserProfile(
                user_id=user_id,
                total_sessions=0,
                total_turns=0,
                avg_satisfaction=0.0
            )
            self.db.add(profile)
            await self.db.commit()
            await self.db.refresh(profile)

            self.logger.info("user_profile_created", user_id=user_id)

        return profile

    async def update_user_profile(
        self,
        user_id: int,
        updates: Dict[str, Any]
    ):
        """
        Met à jour le profil utilisateur

        Args:
            user_id: ID utilisateur
            updates: Dict des champs à mettre à jour
        """
        profile = await self.get_user_profile(user_id)
        if not profile:
            return

        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        profile.updated_at = datetime.utcnow()
        await self.db.commit()

        self.logger.info(
            "user_profile_updated",
            user_id=user_id,
            fields=list(updates.keys())
        )
