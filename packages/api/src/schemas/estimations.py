"""
Schémas Pydantic pour l'estimation immobilière DVF.
Conformes aux conventions FastAPI : Create ≠ Response ≠ Update.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================
# SCHÉMAS POUR /estimations/stats
# ============================================================

class EstimationStatsResponse(BaseModel):
    """Réponse des statistiques d'estimation."""
    code_postal: str = Field(description="Code postal analysé")
    type_bien: str = Field(description="Type de bien analysé")
    prix_m2_median: Decimal = Field(description="Prix médian au m² (€)")
    prix_m2_moyen: Decimal = Field(description="Prix moyen au m² (€)")
    prix_m2_min: Decimal = Field(description="Prix minimum au m² (€)")
    prix_m2_max: Decimal = Field(description="Prix maximum au m² (€)")
    nb_transactions: int = Field(description="Nombre de transactions analysées")
    tendance_3mois: Decimal = Field(description="Évolution sur 3 mois (%)")
    tendance_12mois: Decimal = Field(description="Évolution sur 12 mois (%)")
    commune: str = Field(description="Nom de la commune principale")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# SCHÉMAS POUR /estimations/analyse
# ============================================================

class EstimationAnalyseRequest(BaseModel):
    """Demande d'analyse d'estimation avec IA."""
    adresse: str = Field(
        ...,
        description="Adresse complète du bien",
        min_length=10,
        max_length=200
    )
    type_bien: Literal["Appartement", "Maison", "Local industriel. commercial ou assimilé"] = Field(
        ...,
        description="Type de bien immobilier"
    )
    surface_m2: int = Field(
        ...,
        description="Surface habitable en m²",
        gt=10,
        le=2000
    )
    nb_pieces: Optional[int] = Field(
        default=None,
        description="Nombre de pièces principales",
        ge=1,
        le=20
    )
    etage: Optional[int] = Field(
        default=None,
        description="Étage du bien",
        ge=0,
        le=50
    )
    annee_construction: Optional[int] = Field(
        default=None,
        description="Année de construction",
        ge=1800,
        le=2025
    )
    dossier_id: Optional[str] = Field(
        default=None,
        description="ID du dossier notarial associé"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class FourchettePrix(BaseModel):
    """Fourchette d'estimation de prix."""
    min: Decimal = Field(description="Prix minimum estimé (€)")
    median: Decimal = Field(description="Prix médian estimé (€)")
    max: Decimal = Field(description="Prix maximum estimé (€)")


class TransactionComparable(BaseModel):
    """Transaction comparable utilisée pour l'estimation."""
    id: str = Field(description="Identifiant de la transaction")
    prix_vente: Decimal = Field(description="Prix de vente (€)")
    surface_m2: Decimal = Field(description="Surface (m²)")
    prix_m2: Decimal = Field(description="Prix au m² (€)")
    nb_pieces: Optional[int] = Field(description="Nombre de pièces")
    date_vente: date = Field(description="Date de la vente")
    commune: str = Field(description="Commune")
    code_postal: str = Field(description="Code postal")
    distance_km: Decimal = Field(description="Distance par rapport au bien analysé (km)")
    score_similarite: Decimal = Field(description="Score de similarité (0-1)", ge=0, le=1)

    model_config = ConfigDict(from_attributes=True)


class EstimationAnalyseResponse(BaseModel):
    """Réponse d'analyse d'estimation avec IA."""
    fourchette: FourchettePrix = Field(description="Fourchette de prix estimée")
    prix_m2_estime: Decimal = Field(description="Prix estimé au m² (€)")

    comparables: List[Dict[str, Any]] = Field(
        description="Transactions comparables utilisées",
        max_items=20
    )

    facteurs_correction: List[str] = Field(
        description="Facteurs de correction identifiés"
    )

    niveau_confiance: Literal["fort", "moyen", "faible"] = Field(
        description="Niveau de confiance de l'estimation"
    )

    justification: str = Field(
        description="Justification détaillée de l'estimation"
    )

    # Métadonnées
    date_analyse: datetime = Field(description="Date de l'analyse")
    nb_comparables_utilises: int = Field(description="Nombre de comparables trouvés")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# SCHÉMAS POUR /estimations/carte
# ============================================================

class GeometryPoint(BaseModel):
    """Géométrie GeoJSON Point."""
    type: str = Field(default="Point")
    coordinates: List[float] = Field(description="[longitude, latitude]")


class TransactionFeature(BaseModel):
    """Feature GeoJSON d'une transaction."""
    type: str = Field(default="Feature")
    geometry: GeometryPoint
    properties: Dict[str, Any] = Field(description="Propriétés de la transaction")


class EstimationCarteResponse(BaseModel):
    """Réponse GeoJSON pour la carte des transactions."""
    type: str = Field(default="FeatureCollection")
    features: List[TransactionFeature] = Field(description="Transactions géolocalisées")
    metadata: Dict[str, Any] = Field(description="Métadonnées sur les données")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# SCHÉMAS INTERNES
# ============================================================

class AIInteractionLog(BaseModel):
    """Log d'interaction IA pour audit."""
    user_id: str
    endpoint: str
    prompt: str
    response: str
    dossier_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)