"""
ProfessionnelCopropriete - Table de liaison Many-to-Many
Associe les professionnels aux copropriétés avec métadonnées
"""

from sqlalchemy import Column, Integer, ForeignKey, Date, Boolean, DateTime, Numeric, Text, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ProfessionnelCopropriete(Base):
    """
    Table de liaison Many-to-Many entre Professionnels et Copropriétés

    Cette table permet de suivre:
    - Quels professionnels travaillent sur quelles copropriétés
    - L'historique des interventions
    - Les notes/évaluations spécifiques à chaque relation
    """

    __tablename__ = "professionnels_coproprietes"

    # Clés étrangères composites (Primary Key)
    professionnel_id = Column(
        Integer,
        ForeignKey('vendors.id', ondelete='CASCADE'),  # Note: 'vendors' sera renommé 'professionnels' dans migration
        nullable=False,
        index=True
    )
    copropriete_id = Column(
        Integer,
        ForeignKey('coproprietes.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Métadonnées de la relation
    date_debut = Column(Date, default=func.current_date())  # Date de début de collaboration
    date_fin = Column(Date)  # NULL si collaboration toujours active
    est_prestataire_principal = Column(Boolean, default=False)  # Prestataire principal pour cette copro?

    # Historique des interventions
    nombre_interventions = Column(Integer, default=0)
    derniere_intervention = Column(DateTime(timezone=True))
    note_moyenne = Column(Numeric(3, 2))  # Note moyenne pour cette copro spécifiquement (0.00 à 5.00)

    # Notes et commentaires
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations (optionnel - pour requêtes ORM plus faciles)
    # professionnel = relationship("Professionnel")
    # copropriete = relationship("Copropriete")

    # Contrainte de clé primaire composite
    __table_args__ = (
        PrimaryKeyConstraint('professionnel_id', 'copropriete_id'),
    )

    def __repr__(self):
        return f"<ProfessionnelCopropriete prof_id={self.professionnel_id} copro_id={self.copropriete_id}>"

    @property
    def est_actif(self):
        """La relation est-elle toujours active?"""
        return self.date_fin is None
