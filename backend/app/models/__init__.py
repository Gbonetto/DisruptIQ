"""
Database Models
"""

from app.models.user import User
from app.models.email import Email
from app.models.professionnel import Professionnel, Vendor  # Vendor est un alias
from app.models.document import Document
from app.models.copropriete import Copropriete
from app.models.coproprietaire import Coproprietaire
from app.models.professionnel_copropriete import ProfessionnelCopropriete
from app.models.conversation import Conversation
from app.models.message import Message

__all__ = [
    "User",
    "Email",
    "Professionnel",
    "Vendor",  # Alias pour compatibilité
    "Document",
    "Copropriete",
    "Coproprietaire",
    "ProfessionnelCopropriete",
    "Conversation",
    "Message",
]
