"""
Professionnel Model (anciennement Vendor)
Représente les prestataires/professionnels (plombiers, électriciens, etc.)
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Professionnel(Base):
    """
    Modèle Professionnel - Prestataires et fournisseurs de services

    Représente les professionnels du bâtiment et prestataires de services
    travaillant pour les copropriétés (plombiers, électriciens, jardiniers, etc.)
    """

    __tablename__ = "professionnels"  # Anciennement "vendors" - renommé via migration SQL

    id = Column(Integer, primary_key=True, index=True)

    # Informations de base
    name = Column(String, nullable=False)
    company_name = Column(String)
    email = Column(String, nullable=False, unique=True, index=True)
    phone = Column(String)

    # NOUVEAUX CHAMPS
    siret = Column(String(14))  # Numéro SIRET (14 caractères)
    description = Column(Text)  # Description des services
    statut = Column(String(20), default='active', index=True)  # active, inactive, blacklisted

    # Détails métier
    category = Column(String, index=True)  # "plombier", "électricien", "peintre", etc.
    specialties = Column(JSON, default=list)  # Liste des spécialités

    # Localisation
    address = Column(Text)
    city = Column(String, index=True)
    postal_code = Column(String)

    # Performance et historique
    rating = Column(Float, default=0.0)  # Note sur 5
    total_jobs = Column(Integer, default=0)  # Nombre total d'interventions
    last_contacted = Column(DateTime(timezone=True))
    notes = Column(Text)

    # Indexation RAG (synchronisation Qdrant)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)
    last_indexed_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations (many-to-many avec Coproprietes via table de liaison)
    # Sera ajouté après création du modèle ProfessionnelCopropriete
    # coproprietes = relationship("Copropriete", secondary="professionnels_coproprietes", back_populates="professionnels")

    def __repr__(self):
        return f"<Professionnel {self.name} - {self.category} ({self.statut})>"


# Alias pour compatibilité avec le code existant
# Permet de faire la migration en douceur
Vendor = Professionnel
