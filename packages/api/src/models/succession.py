"""
Modèles de données pour la gestion des successions.
Conformes aux spécifications TDD et conventions notaire-app
"""
from datetime import date
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4
import enum

from sqlalchemy import (
    String, Date, Text, Numeric, BigInteger, Integer,
    ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel
from pydantic import BaseModel as PydanticBaseModel, Field


class StatutSuccession(str, enum.Enum):
    """Statuts de succession."""
    EN_COURS = "en_cours"
    DECLARATIONS_DEPOSEES = "declarations_deposees"
    DROITS_PAYES = "droits_payes"
    CLOTUREE = "cloturee"


class StatutTraitement(str, enum.Enum):
    """Statuts de traitement de la succession."""
    ANALYSE_AUTO = "analyse_auto"
    EN_COURS = "en_cours"
    TERMINE = "terminé"


class LienParente(str, enum.Enum):
    """Types de liens de parenté pour les héritiers (selon spécifications)."""
    CONJOINT = "conjoint"
    ENFANT = "enfant"
    PETIT_ENFANT = "petit_enfant"
    PARENT = "parent"
    FRERE_SOEUR = "frere_soeur"
    NEVEU_NIECE = "neveu_niece"
    AUTRE = "autre"


class TypeActif(str, enum.Enum):
    """Types d'actifs successoraux (selon spécifications)."""
    IMMOBILIER = "immobilier"
    FINANCIER = "financier"
    MOBILIER = "mobilier"
    PROFESSIONNEL = "professionnel"
    AUTRE = "autre"


class TypePassif(str, enum.Enum):
    """Types de passifs successoraux."""
    CREDIT_IMMOBILIER = "credit_immobilier"
    CREDIT_CONSOMMATION = "credit_consommation"
    DETTE_FISCALE = "dette_fiscale"
    FRAIS_FUNERAIRES = "frais_funeraires"
    AUTRE = "autre"


# =============================================================================
# MODÈLES SQLAlchemy
# =============================================================================

class Succession(BaseModel, Base):
    """
    Modèle principal d'une succession.
    Conforme aux spécifications: FK dossier_id, timestamps automatiques.
    """
    __tablename__ = "successions"

    # FK vers le dossier (selon spécifications)
    dossier_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('dossiers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Référence vers le dossier notarial"
    )

    # Informations du défunt
    defunt_nom: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    defunt_prenom: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    defunt_date_naissance: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    defunt_date_deces: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    regime_matrimonial: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    nb_enfants: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # Statut de traitement
    statut_traitement: Mapped[StatutTraitement] = mapped_column(
        SQLEnum(StatutTraitement, name="statut_traitement"),
        default=StatutTraitement.ANALYSE_AUTO,
        nullable=False,
        index=True
    )

    # Relations avec cascade delete
    dossier: Mapped["Dossier"] = relationship(
        "Dossier",
        back_populates="successions"
    )

    heritiers: Mapped[List["Heritier"]] = relationship(
        "Heritier",
        back_populates="succession",
        cascade="all, delete-orphan"
    )

    actifs: Mapped[List["ActifSuccessoral"]] = relationship(
        "ActifSuccessoral",
        back_populates="succession",
        cascade="all, delete-orphan"
    )

    passifs: Mapped[List["PassifSuccessoral"]] = relationship(
        "PassifSuccessoral",
        back_populates="succession",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Succession {self.defunt_nom} {self.defunt_prenom}>"

class Heritier(BaseModel, Base):
    """
    Héritier dans une succession.
    Avec enum lien_parente selon spécifications.
    """
    __tablename__ = "heritiers"

    # Référence à la succession
    succession_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('successions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Identité
    nom: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    prenom: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Lien de parenté (enum selon spécifications)
    lien_parente: Mapped[LienParente] = mapped_column(
        SQLEnum(LienParente, name="lien_parente"),
        nullable=False,
        index=True
    )

    # Part théorique (0.5000 = 50%)
    part_theorique: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Part théorique (ex: 0.5000 = 50%)"
    )

    # Adresse
    adresse: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relation
    succession: Mapped["Succession"] = relationship(
        "Succession",
        back_populates="heritiers"
    )

    def __repr__(self) -> str:
        return f"<Heritier {self.nom} {self.prenom} - {self.lien_parente}>"


class ActifSuccessoral(BaseModel, Base):
    """
    Actif faisant partie de la succession.
    Valeurs monétaires en centimes d'euros (BigInteger).
    """
    __tablename__ = "actifs_successoraux"

    # Référence à la succession
    succession_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('successions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Type d'actif (enum selon spécifications)
    type_actif: Mapped[TypeActif] = mapped_column(
        SQLEnum(TypeActif, name="type_actif"),
        nullable=False,
        index=True
    )

    # Description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Valeur en centimes d'euros (BigInteger selon spécifications)
    valeur_estimee: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Valeur estimée en centimes d'euros"
    )

    # Informations complémentaires
    etablissement: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    date_evaluation: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )

    # Relation
    succession: Mapped["Succession"] = relationship(
        "Succession",
        back_populates="actifs"
    )

    def __repr__(self) -> str:
        valeur_euros = self.valeur_estimee / 100
        return f"<ActifSuccessoral {self.type_actif} - {valeur_euros}€>"


class PassifSuccessoral(BaseModel, Base):
    """
    Passif (dette) de la succession.
    Montant en centimes d'euros (BigInteger).
    """
    __tablename__ = "passifs_successoraux"

    # Référence à la succession
    succession_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('successions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Type de passif
    type_passif: Mapped[TypePassif] = mapped_column(
        SQLEnum(TypePassif, name="type_passif"),
        nullable=False,
        index=True
    )

    # Montant en centimes d'euros (BigInteger selon spécifications)
    montant: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant en centimes d'euros"
    )

    # Créancier
    creancier: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Relation
    succession: Mapped["Succession"] = relationship(
        "Succession",
        back_populates="passifs"
    )

    def __repr__(self) -> str:
        montant_euros = self.montant / 100
        return f"<PassifSuccessoral {self.type_passif} - {montant_euros}€>"


# =============================================================================
# SCHÉMAS PYDANTIC V2
# =============================================================================

class SuccessionCreate(PydanticBaseModel):
    """Schéma pour créer une succession."""
    dossier_id: UUID
    defunt_nom: str = Field(..., min_length=1, max_length=100)
    defunt_prenom: str = Field(..., min_length=1, max_length=100)
    defunt_date_naissance: date
    defunt_date_deces: date
    regime_matrimonial: Optional[str] = Field(None, max_length=50)
    nb_enfants: int = Field(0, ge=0)


class HeritierCreate(PydanticBaseModel):
    """Schéma pour créer un héritier."""
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    lien_parente: LienParente
    part_theorique: Optional[Decimal] = Field(None, ge=0, le=1)
    adresse: Optional[str] = None


class ActifCreate(PydanticBaseModel):
    """Schéma pour créer un actif successoral."""
    type_actif: TypeActif
    description: str = Field(..., min_length=1)
    valeur_estimee: int = Field(..., gt=0, description="Valeur en centimes d'euros")
    etablissement: Optional[str] = Field(None, max_length=100)
    reference: Optional[str] = Field(None, max_length=100)
    date_evaluation: Optional[date] = None


class PassifCreate(PydanticBaseModel):
    """Schéma pour créer un passif successoral."""
    type_passif: str = Field(..., min_length=1, max_length=100)
    montant: int = Field(..., gt=0, description="Montant en centimes d'euros")
    creancier: Optional[str] = Field(None, max_length=100)


class HeritierDetail(PydanticBaseModel):
    """Héritier avec calculs fiscaux."""
    id: UUID
    nom: str
    prenom: str
    lien_parente: LienParente
    part_theorique: Optional[Decimal]
    adresse: Optional[str]

    class Config:
        from_attributes = True


class ActifDetail(PydanticBaseModel):
    """Actif successoral complet."""
    id: UUID
    type_actif: TypeActif
    description: str
    valeur_estimee: int
    etablissement: Optional[str]
    reference: Optional[str]
    date_evaluation: Optional[date]

    class Config:
        from_attributes = True


class PassifDetail(PydanticBaseModel):
    """Passif successoral complet."""
    id: UUID
    type_passif: str
    montant: int
    creancier: Optional[str]

    class Config:
        from_attributes = True


class SuccessionDetail(PydanticBaseModel):
    """Succession complète avec héritiers et actifs."""
    id: UUID
    dossier_id: UUID
    defunt_nom: str
    defunt_prenom: str
    defunt_date_naissance: date
    defunt_date_deces: date
    regime_matrimonial: Optional[str]
    nb_enfants: int
    statut_traitement: StatutTraitement

    # Relations
    heritiers: List[HeritierDetail]
    actifs: List[ActifDetail]
    passifs: List[PassifDetail]

    class Config:
        from_attributes = True


class CalculSuccessionResult(PydanticBaseModel):
    """Résultat du calcul de succession."""
    succession_id: UUID
    actif_net_total: Decimal
    total_droits_succession: Decimal

    heritiers: List[dict] = Field(
        description="Liste des calculs par héritier"
    )

    class Config:
        from_attributes = True