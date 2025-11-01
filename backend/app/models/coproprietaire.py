"""
Coproprietaire Model
Représente les copropriétaires/résidents des immeubles gérés
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean, ForeignKey, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Coproprietaire(Base):
    """
    Modèle Copropriétaire - Personnes vivant dans les copropriétés

    Représente un copropriétaire, locataire ou résident d'une copropriété
    avec toutes ses informations de contact et détails du lot
    """

    __tablename__ = "coproprietaires"

    id = Column(Integer, primary_key=True, index=True)

    # Informations personnelles
    nom = Column(String, nullable=False, index=True)
    prenom = Column(String, nullable=False, index=True)
    email = Column(String, index=True)
    telephone = Column(String)
    telephone_mobile = Column(String)

    # Relation avec la copropriété (FK)
    copropriete_id = Column(Integer, ForeignKey('coproprietes.id', ondelete='CASCADE'), nullable=False, index=True)

    # Informations sur le lot
    numero_lot = Column(String, nullable=False, index=True)  # "A12", "Bat B - 304", etc.
    type_lot = Column(String)  # "appartement", "garage", "cave", "parking"
    etage = Column(Integer)
    surface = Column(Numeric(8, 2))  # Surface en m²

    # Statut
    statut = Column(String, default='proprietaire', index=True)  # "proprietaire", "locataire", "usufruitier"
    statut_special = Column(String)  # "président", "syndic", "gardien", "conseil_syndical", etc.
    est_resident = Column(Boolean, default=True)  # Habite-t-il réellement le lot?
    date_acquisition = Column(Date)

    # Quotes-parts copropriété
    tantiemes = Column(Integer)  # Millièmes de copropriété

    # Contact
    adresse_postale = Column(Text)  # Si différente de l'adresse du lot
    preferences_contact = Column(JSON, default={"email": True, "sms": False})

    # Notes
    notes = Column(Text)

    # Indexation RAG (synchronisation Qdrant)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)
    last_indexed_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    # Many-to-one avec Copropriete
    copropriete = relationship("Copropriete", back_populates="coproprietaires")

    # Contrainte d'unicité : un seul copropriétaire par lot
    __table_args__ = (
        UniqueConstraint('copropriete_id', 'numero_lot', name='unique_lot_per_copropriete'),
    )

    def __repr__(self):
        return f"<Coproprietaire {self.prenom} {self.nom} - Lot {self.numero_lot} ({self.statut})>"

    @property
    def nom_complet(self):
        """Retourne le nom complet du copropriétaire"""
        return f"{self.prenom} {self.nom}"
