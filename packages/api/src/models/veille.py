"""
Modèles de données pour le système de veille automatique.
Surveillance DVF, Légifrance, BOFIP avec notifications intelligentes.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import uuid4
import enum

from sqlalchemy import (
    String, Text, Numeric, Integer, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class TypeSource(str, enum.Enum):
    """Types de sources surveillées pour la veille."""
    DVF = "dvf"
    LEGIFRANCE = "legifrance"
    BOFIP = "bofip"
    JURISPRUDENCE = "jurisprudence"


class NiveauImpact(str, enum.Enum):
    """Niveau d'impact d'une alerte sur les dossiers."""
    INFO = "info"           # Information sans impact direct
    FAIBLE = "faible"       # Nécessite attention
    MOYEN = "moyen"         # Action recommandée
    FORT = "fort"           # Action requise
    CRITIQUE = "critique"   # Action immédiate


class StatutAlerte(str, enum.Enum):
    """Statut de traitement d'une alerte."""
    NOUVELLE = "nouvelle"
    EN_COURS = "en_cours"
    TRAITEE = "traitee"
    ARCHIVEE = "archivee"


# =============================================================================
# MODÈLES SQLAlchemy
# =============================================================================

class VeilleRule(BaseModel, Base):
    """
    Règle de veille configurée par l'étude notariale.
    Définit quoi surveiller et pour quels dossiers.
    """
    __tablename__ = "veille_rules"

    # Identification de la règle
    nom: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nom explicite de la règle de veille"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description détaillée de ce qui est surveillé"
    )

    # Source surveillée
    type_source: Mapped[TypeSource] = mapped_column(
        SQLEnum(TypeSource, name="type_source"),
        nullable=False,
        index=True,
        comment="Type de source à surveiller"
    )

    # Configuration de la surveillance
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Paramètres JSON spécifiques à la source"
    )

    # Filtrage géographique ou thématique
    code_postal: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="Code postal pour filtrage géographique DVF"
    )

    articles_codes: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Liste des articles de code surveillés"
    )

    # Activation et périodicité
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Règle active ou suspendue"
    )

    frequence_heures: Mapped[int] = mapped_column(
        Integer,
        default=24,
        nullable=False,
        comment="Fréquence de vérification en heures"
    )

    derniere_verification: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp de la dernière vérification"
    )

    # Association avec un dossier spécifique (optionnel)
    dossier_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('dossiers.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="Dossier spécifique concerné par cette règle"
    )

    # Relations
    dossier: Mapped[Optional["Dossier"]] = relationship(
        "Dossier",
        back_populates="veille_rules"
    )

    alertes: Mapped[List["Alerte"]] = relationship(
        "Alerte",
        back_populates="veille_rule",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VeilleRule {self.nom} - {self.type_source}>"


class Alerte(BaseModel, Base):
    """
    Alerte générée par le système de veille automatique.
    Notification d'un changement détecté par une règle.
    """
    __tablename__ = "alertes"

    # Référence à la règle de veille
    veille_rule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('veille_rules.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Règle de veille qui a généré cette alerte"
    )

    # Classification de l'alerte
    titre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Titre court et explicite de l'alerte"
    )

    niveau_impact: Mapped[NiveauImpact] = mapped_column(
        SQLEnum(NiveauImpact, name="niveau_impact"),
        nullable=False,
        index=True,
        comment="Niveau d'impact estimé sur les dossiers"
    )

    statut: Mapped[StatutAlerte] = mapped_column(
        SQLEnum(StatutAlerte, name="statut_alerte"),
        default=StatutAlerte.NOUVELLE,
        nullable=False,
        index=True,
        comment="Statut de traitement de l'alerte"
    )

    # Contenu de l'alerte
    contenu: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description détaillée du changement détecté"
    )

    details_techniques: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Détails techniques du changement (JSON)"
    )

    # Analyse d'impact IA
    analyse_impact: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Analyse d'impact générée par IA"
    )

    url_source: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL de la source du changement"
    )

    # Assignation et traitement
    assignee_user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="Utilisateur assigné pour traiter cette alerte"
    )

    date_traitement: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Date de traitement de l'alerte"
    )

    commentaire_traitement: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Commentaire du traitement effectué"
    )

    # Dossiers potentiellement impactés (calculé automatiquement)
    dossiers_impactes: Mapped[Optional[List[UUID]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Liste des IDs de dossiers potentiellement impactés"
    )

    # Relations
    veille_rule: Mapped["VeilleRule"] = relationship(
        "VeilleRule",
        back_populates="alertes"
    )

    assignee: Mapped[Optional["User"]] = relationship(
        "User"
    )

    def __repr__(self) -> str:
        return f"<Alerte {self.titre} - {self.niveau_impact}>"


class HistoriqueVeille(BaseModel, Base):
    """
    Historique des vérifications de veille pour audit et debugging.
    """
    __tablename__ = "historique_veille"

    # Référence à la règle
    veille_rule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('veille_rules.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Résultats de la vérification
    date_verification: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Moment de la vérification"
    )

    duree_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Durée de la vérification en millisecondes"
    )

    succes: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        comment="Vérification réussie ou échouée"
    )

    elements_verifies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre d'éléments vérifiés"
    )

    alertes_creees: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre d'alertes créées lors de cette vérification"
    )

    # Détails techniques
    logs_techniques: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Logs techniques de la vérification"
    )

    erreur: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message d'erreur si vérification échouée"
    )

    # Relations
    veille_rule: Mapped["VeilleRule"] = relationship("VeilleRule")

    def __repr__(self) -> str:
        return f"<HistoriqueVeille {self.date_verification} - {'✓' if self.succes else '✗'}>"