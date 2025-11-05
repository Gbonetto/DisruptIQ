"""
Invoice Models - Factures OCR

Tables pour gérer les factures extraites par OCR:
- FactureGlobal: En-tête facture
- FactureDetail: Lignes de détail
"""

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Boolean,
    DECIMAL, CheckConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class FactureStatut(str, enum.Enum):
    """Statut d'une facture"""
    A_VALIDER = "a_valider"
    VALIDEE = "validee"
    PAYEE = "payee"
    ANNULEE = "annulee"


class ExtractionMethod(str, enum.Enum):
    """Méthode d'extraction de la facture"""
    OCR = "ocr"
    MANUAL = "manual"
    IMPORT = "import"


class FactureGlobal(Base):
    """
    Facture globale (en-tête).

    Contient les informations principales de la facture:
    - Numéro, dates, montants
    - Liens fournisseur, copropriété, document source
    - Métadonnées OCR (confiance, needs_review)
    - Statut et validation

    Relations:
    - 1:N avec FactureDetail (lignes)
    - N:1 avec Professionnel (fournisseur)
    - N:1 avec Copropriete
    - N:1 avec Document (source OCR)
    - N:1 avec User (validation)
    """

    __tablename__ = "factures_global"

    # Identification
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(100), nullable=False, index=True)
    date_facture = Column(Date, nullable=False, index=True)
    date_echeance = Column(Date, nullable=True)

    # Relations (FK)
    fournisseur_id = Column(
        Integer,
        ForeignKey("professionnels.id", ondelete="SET NULL"),
        index=True
    )
    copropriete_id = Column(
        Integer,
        ForeignKey("coproprietes.id", ondelete="SET NULL"),
        index=True
    )
    doc_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True
    )

    # Montants
    montant_ht = Column(DECIMAL(12, 2), nullable=False)
    montant_tva = Column(DECIMAL(12, 2), nullable=False)
    montant_ttc = Column(DECIMAL(12, 2), nullable=False)
    devise = Column(String(3), default="EUR")

    # Catégorie et statut
    categorie = Column(String(100), index=True)
    statut = Column(String(50), default=FactureStatut.A_VALIDER.value, index=True)
    mode_paiement = Column(String(50))

    # Extraction OCR
    extraction_method = Column(String(50), default=ExtractionMethod.OCR.value)
    ocr_confidence = Column(DECIMAL(4, 3))  # 0.000-1.000
    needs_review = Column(Boolean, default=False, index=True)

    # Validation
    validated_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL")
    )
    validated_at = Column(DateTime(timezone=True))

    # Paiement
    date_paiement = Column(Date)
    reference_paiement = Column(String(100))

    # Notes
    notes = Column(Text)

    # Métadonnées (renamed from 'metadata' to avoid SQLAlchemy reserved keyword)
    metadata_json = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    details = relationship(
        "FactureDetail",
        back_populates="facture",
        cascade="all, delete-orphan"
    )
    fournisseur = relationship("Professionnel", foreign_keys=[fournisseur_id])
    copropriete = relationship("Copropriete", foreign_keys=[copropriete_id])
    document = relationship("Document", foreign_keys=[doc_id])

    # Contraintes
    __table_args__ = (
        CheckConstraint(
            "montant_ttc = montant_ht + montant_tva",
            name="check_montants_coherence"
        ),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="check_ocr_confidence"
        ),
        # Note: UniqueConstraint handled by unique index in migration
    )

    def __repr__(self):
        return (
            f"<FactureGlobal {self.id} "
            f"num={self.numero} "
            f"date={self.date_facture} "
            f"montant={self.montant_ttc}€>"
        )

    @property
    def is_payee(self) -> bool:
        """Vérifie si la facture est payée"""
        return self.statut == FactureStatut.PAYEE.value or self.date_paiement is not None

    @property
    def taux_tva_moyen(self) -> float:
        """Calcule le taux de TVA moyen"""
        if self.montant_ht == 0:
            return 0.0
        return float((self.montant_tva / self.montant_ht) * 100)

    @property
    def nb_lignes(self) -> int:
        """Compte le nombre de lignes de détail"""
        return len(self.details)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour API"""
        return {
            "id": self.id,
            "numero": self.numero,
            "date_facture": self.date_facture.isoformat() if self.date_facture else None,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "fournisseur_id": self.fournisseur_id,
            "copropriete_id": self.copropriete_id,
            "doc_id": self.doc_id,
            "montant_ht": float(self.montant_ht),
            "montant_tva": float(self.montant_tva),
            "montant_ttc": float(self.montant_ttc),
            "devise": self.devise,
            "categorie": self.categorie,
            "statut": self.statut,
            "mode_paiement": self.mode_paiement,
            "extraction_method": self.extraction_method,
            "ocr_confidence": float(self.ocr_confidence) if self.ocr_confidence else None,
            "needs_review": self.needs_review,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "date_paiement": self.date_paiement.isoformat() if self.date_paiement else None,
            "reference_paiement": self.reference_paiement,
            "notes": self.notes,
            "metadata": self.metadata,
            "nb_lignes": self.nb_lignes,
            "is_payee": self.is_payee,
            "taux_tva_moyen": self.taux_tva_moyen,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FactureDetail(Base):
    """
    Ligne de détail d'une facture.

    Contient les informations d'une ligne:
    - Article, description
    - Quantité, unité
    - Prix unitaire, montants HT/TTC
    - Codes analytiques

    Relations:
    - N:1 avec FactureGlobal
    """

    __tablename__ = "factures_details"

    # Identification
    id = Column(Integer, primary_key=True, index=True)
    facture_id = Column(
        Integer,
        ForeignKey("factures_global.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Ligne
    ligne_numero = Column(Integer, nullable=False)

    # Article/Prestation
    article = Column(String(500), nullable=False, index=True)
    description = Column(Text)

    # Quantités
    quantite = Column(DECIMAL(12, 3), nullable=False, default=1)
    unite = Column(String(50), default="pce")

    # Prix
    prix_unitaire_ht = Column(DECIMAL(12, 2), nullable=False)
    taux_tva = Column(DECIMAL(5, 2), nullable=False)  # Pourcentage
    montant_ht = Column(DECIMAL(12, 2), nullable=False)
    montant_tva = Column(DECIMAL(12, 2), nullable=False)
    montant_ttc = Column(DECIMAL(12, 2), nullable=False)

    # Analytique
    centre_cout = Column(String(100), index=True)
    code_analytique = Column(String(100))
    compte_comptable = Column(String(50))

    # Métadonnées (renamed from 'metadata' to avoid SQLAlchemy reserved keyword)
    metadata_json = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    facture = relationship("FactureGlobal", back_populates="details")

    # Contraintes
    __table_args__ = (
        CheckConstraint(
            "montant_ht = quantite * prix_unitaire_ht",
            name="check_montant_ht_calcul"
        ),
        CheckConstraint(
            "ABS(montant_tva - (montant_ht * taux_tva / 100)) < 0.01",
            name="check_montant_tva_calcul"
        ),
        # Note: UniqueConstraint handled by unique index in migration
    )

    def __repr__(self):
        return (
            f"<FactureDetail {self.id} "
            f"facture_id={self.facture_id} "
            f"ligne={self.ligne_numero} "
            f"article={self.article[:30]}...>"
        )

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour API"""
        return {
            "id": self.id,
            "facture_id": self.facture_id,
            "ligne_numero": self.ligne_numero,
            "article": self.article,
            "description": self.description,
            "quantite": float(self.quantite),
            "unite": self.unite,
            "prix_unitaire_ht": float(self.prix_unitaire_ht),
            "taux_tva": float(self.taux_tva),
            "montant_ht": float(self.montant_ht),
            "montant_tva": float(self.montant_tva),
            "montant_ttc": float(self.montant_ttc),
            "centre_cout": self.centre_cout,
            "code_analytique": self.code_analytique,
            "compte_comptable": self.compte_comptable,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
