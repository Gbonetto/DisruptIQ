"""
Copropriete Model
Représente les copropriétés/immeubles gérés par le syndic
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Copropriete(Base):
    """
    Modèle Copropriété - Immeubles gérés par le syndic

    Représente une copropriété/immeuble avec toutes ses caractéristiques
    (adresse, nombre de lots, équipements, etc.)
    """

    __tablename__ = "coproprietes"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    nom = Column(String, nullable=False)  # "Résidence Les Mimosas"
    adresse = Column(Text, nullable=False)
    ville = Column(String, nullable=False, index=True)
    code_postal = Column(String(10), nullable=False, index=True)

    # Caractéristiques de la copropriété
    nombre_lots = Column(Integer)  # Nombre d'appartements/lots
    nombre_batiments = Column(Integer, default=1)
    annee_construction = Column(Integer)

    # Gestion
    syndic = Column(String, index=True)  # Nom du syndic responsable
    contact_syndic = Column(String)  # Email ou téléphone du syndic
    reference_syndic = Column(String)  # Numéro de dossier/référence

    # Informations complémentaires
    type_copropriete = Column(String)  # "résidentiel", "mixte", "commercial"
    surface_totale = Column(Numeric(10, 2))  # Surface totale en m²
    equipements = Column(JSON, default=list)  # ["ascenseur", "parking", "piscine", "gardien"]

    # Notes et documents
    notes = Column(Text)
    documents_path = Column(String)  # Chemin vers dossier de documents

    # Indexation RAG (synchronisation Qdrant)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)
    last_indexed_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    # One-to-many avec Coproprietaires
    coproprietaires = relationship("Coproprietaire", back_populates="copropriete", cascade="all, delete-orphan")

    # Many-to-many avec Professionnels via table de liaison
    # Sera ajouté après création du modèle ProfessionnelCopropriete
    # professionnels = relationship("Professionnel", secondary="professionnels_coproprietes", back_populates="coproprietes")

    def __repr__(self):
        return f"<Copropriete {self.nom} - {self.ville} ({self.nombre_lots} lots)>"
