"""
Schémas Pydantic pour les successions.
Séparation Create/Response/Update selon conventions notaire-app.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.models.succession import (
    StatutSuccession, LienParente, TypeActif, TypePassif
)


# === Schémas de base === #

class HeritierBase(BaseModel):
    """Schéma de base pour un héritier."""
    nom: str = Field(..., max_length=100)
    prenom: str = Field(..., max_length=100)
    date_naissance: Optional[date] = None
    lien_parente: LienParente
    quote_part_legale: Decimal = Field(..., ge=0, le=1)
    adresse: Optional[str] = None
    email: Optional[str] = Field(None, max_length=255)
    telephone: Optional[str] = Field(None, max_length=20)


class ActifSuccessoralBase(BaseModel):
    """Schéma de base pour un actif successoral."""
    type_actif: TypeActif
    description: str
    valeur_estimee: Decimal = Field(..., ge=0)
    date_estimation: Optional[date] = None
    adresse: Optional[str] = None  # Pour immobilier
    surface: Optional[Decimal] = Field(None, ge=0)  # Pour immobilier


class PassifSuccessoralBase(BaseModel):
    """Schéma de base pour un passif successoral."""
    type_passif: TypePassif
    description: str
    montant: Decimal = Field(..., ge=0)
    creancier: Optional[str] = Field(None, max_length=255)
    date_echeance: Optional[date] = None


class SuccessionBase(BaseModel):
    """Schéma de base pour une succession."""
    numero_dossier: str = Field(..., max_length=50)
    defunt_nom: str = Field(..., max_length=100)
    defunt_prenom: str = Field(..., max_length=100)
    defunt_date_naissance: Optional[date] = None
    defunt_date_deces: Optional[date] = None
    lieu_deces: Optional[str] = Field(None, max_length=255)
    statut: StatutSuccession = StatutSuccession.EN_COURS


# === Schémas Create === #

class HeritierCreate(HeritierBase):
    """Schéma de création d'un héritier."""
    pass


class ActifSuccessoralCreate(ActifSuccessoralBase):
    """Schéma de création d'un actif."""
    pass


class PassifSuccessoralCreate(PassifSuccessoralBase):
    """Schéma de création d'un passif."""
    pass


class SuccessionCreate(SuccessionBase):
    """Schéma de création d'une succession complète."""
    heritiers: List[HeritierCreate] = Field(default_factory=list)
    actifs: List[ActifSuccessoralCreate] = Field(default_factory=list)
    passifs: List[PassifSuccessoralCreate] = Field(default_factory=list)


# === Schémas Response === #

class HeritierResponse(HeritierBase):
    """Schéma de réponse pour un héritier avec calculs."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    succession_id: UUID
    created_at: datetime
    updated_at: datetime

    # Calculs fiscaux
    part_heritee: Optional[Decimal] = None
    abattement_applicable: Optional[Decimal] = None
    base_taxable: Optional[Decimal] = None
    droits_succession: Optional[Decimal] = None


class ActifSuccessoralResponse(ActifSuccessoralBase):
    """Schéma de réponse pour un actif."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    succession_id: UUID
    created_at: datetime
    updated_at: datetime
    estimation_dvf: Optional[Dict[str, Any]] = None


class PassifSuccessoralResponse(PassifSuccessoralBase):
    """Schéma de réponse pour un passif."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    succession_id: UUID
    created_at: datetime
    updated_at: datetime


class SuccessionResponse(SuccessionBase):
    """Schéma de réponse pour une succession complète."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime

    # Totaux calculés
    total_actifs: Optional[Decimal] = None
    total_passifs: Optional[Decimal] = None
    actif_net: Optional[Decimal] = None

    # Métadonnées d'extraction IA
    extraction_metadata: Optional[Dict[str, Any]] = None

    # Relations
    heritiers: List[HeritierResponse] = Field(default_factory=list)
    actifs: List[ActifSuccessoralResponse] = Field(default_factory=list)
    passifs: List[PassifSuccessoralResponse] = Field(default_factory=list)


# === Schémas Update === #

class HeritierUpdate(BaseModel):
    """Schéma de mise à jour d'un héritier."""
    nom: Optional[str] = Field(None, max_length=100)
    prenom: Optional[str] = Field(None, max_length=100)
    date_naissance: Optional[date] = None
    lien_parente: Optional[LienParente] = None
    quote_part_legale: Optional[Decimal] = Field(None, ge=0, le=1)
    adresse: Optional[str] = None
    email: Optional[str] = Field(None, max_length=255)
    telephone: Optional[str] = Field(None, max_length=20)


class ActifSuccessoralUpdate(BaseModel):
    """Schéma de mise à jour d'un actif."""
    type_actif: Optional[TypeActif] = None
    description: Optional[str] = None
    valeur_estimee: Optional[Decimal] = Field(None, ge=0)
    date_estimation: Optional[date] = None
    adresse: Optional[str] = None
    surface: Optional[Decimal] = Field(None, ge=0)


class PassifSuccessoralUpdate(BaseModel):
    """Schéma de mise à jour d'un passif."""
    type_passif: Optional[TypePassif] = None
    description: Optional[str] = None
    montant: Optional[Decimal] = Field(None, ge=0)
    creancier: Optional[str] = Field(None, max_length=255)
    date_echeance: Optional[date] = None


class SuccessionUpdate(BaseModel):
    """Schéma de mise à jour d'une succession."""
    numero_dossier: Optional[str] = Field(None, max_length=50)
    defunt_nom: Optional[str] = Field(None, max_length=100)
    defunt_prenom: Optional[str] = Field(None, max_length=100)
    defunt_date_naissance: Optional[date] = None
    defunt_date_deces: Optional[date] = None
    lieu_deces: Optional[str] = Field(None, max_length=255)
    statut: Optional[StatutSuccession] = None


# === Schémas spécialisés === #

class CalculSuccessionHeritier(BaseModel):
    """Résultat du calcul pour un héritier."""
    heritier_id: UUID
    nom: str
    prenom: str
    lien_parente: LienParente
    quote_part_legale: Decimal
    part_heritee: Decimal
    abattement: Decimal
    base_taxable: Decimal
    taux_applicable: Decimal
    droits_succession: Decimal


class RapportSuccession(BaseModel):
    """Rapport complet de calcul succession."""
    succession_id: UUID
    numero_dossier: str
    defunt_nom: str
    defunt_prenom: str

    # Totaux patrimoniaux
    total_actifs: Decimal
    total_passifs: Decimal
    actif_net_total: Decimal

    # Calculs par héritier
    heritiers: List[CalculSuccessionHeritier]

    # Totaux fiscaux
    total_droits_succession: Decimal

    # Métadonnées
    date_calcul: datetime
    bareme_utilise: str = "2025"


class ExtractionDocumentRequest(BaseModel):
    """Requête d'extraction automatique de documents."""
    documents: List[str] = Field(..., description="Chemins ou URLs des documents")
    seuil_confiance: float = Field(0.7, ge=0.1, le=1.0, description="Seuil de confiance minimum")
    auto_creation: bool = Field(True, description="Créer automatiquement si confiance >= seuil")


class ExtractionDocumentResponse(BaseModel):
    """Réponse de l'extraction automatique."""
    confiance_globale: float
    succession_extraite: SuccessionCreate
    alertes: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    necessite_validation: bool

    # Si auto_creation=True et confiance >= seuil
    succession_creee: Optional[SuccessionResponse] = None