"""
Schémas Pydantic pour le système de veille automatique.
Validation des requêtes et réponses API veille.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.models.veille import TypeSource, NiveauImpact, StatutAlerte


# === Schémas de base === #

class VeilleRuleBase(BaseModel):
    """Schéma de base pour une règle de veille."""
    nom: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    type_source: TypeSource
    configuration: Dict[str, Any] = Field(default_factory=dict)
    code_postal: Optional[str] = Field(None, max_length=10)
    articles_codes: Optional[List[str]] = Field(None, max_items=50)
    active: bool = Field(True)
    frequence_heures: int = Field(24, ge=1, le=8760)  # 1h à 1 an
    dossier_id: Optional[UUID] = None


class AlerteBase(BaseModel):
    """Schéma de base pour une alerte."""
    titre: str = Field(..., min_length=1, max_length=255)
    niveau_impact: NiveauImpact
    statut: StatutAlerte = StatutAlerte.NOUVELLE
    contenu: str = Field(..., min_length=10)
    details_techniques: Optional[Dict[str, Any]] = None
    analyse_impact: Optional[str] = None
    url_source: Optional[str] = Field(None, max_length=500)
    assignee_user_id: Optional[UUID] = None
    commentaire_traitement: Optional[str] = None
    dossiers_impactes: Optional[List[UUID]] = None


# === Schémas Create === #

class VeilleRuleCreate(VeilleRuleBase):
    """Schéma de création d'une règle de veille."""
    pass


class AlerteCreate(AlerteBase):
    """Schéma de création d'une alerte."""
    veille_rule_id: UUID


# === Schémas Response === #

class VeilleRuleResponse(VeilleRuleBase):
    """Schéma de réponse pour une règle de veille."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    derniere_verification: Optional[datetime] = None

    # Statistiques calculées
    total_alertes: Optional[int] = None
    alertes_actives: Optional[int] = None


class AlerteResponse(AlerteBase):
    """Schéma de réponse pour une alerte."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    veille_rule_id: UUID
    created_at: datetime
    updated_at: datetime
    date_traitement: Optional[datetime] = None

    # Relation avec la règle
    veille_rule: Optional[VeilleRuleResponse] = None


class HistoriqueVeilleResponse(BaseModel):
    """Schéma de réponse pour l'historique de veille."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    veille_rule_id: UUID
    date_verification: datetime
    duree_ms: int
    succes: bool
    elements_verifies: int
    alertes_creees: int
    erreur: Optional[str] = None


# === Schémas Update === #

class VeilleRuleUpdate(BaseModel):
    """Schéma de mise à jour d'une règle de veille."""
    nom: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    configuration: Optional[Dict[str, Any]] = None
    code_postal: Optional[str] = Field(None, max_length=10)
    articles_codes: Optional[List[str]] = Field(None, max_items=50)
    active: Optional[bool] = None
    frequence_heures: Optional[int] = Field(None, ge=1, le=8760)
    dossier_id: Optional[UUID] = None


class AlerteUpdate(BaseModel):
    """Schéma de mise à jour d'une alerte."""
    statut: Optional[StatutAlerte] = None
    analyse_impact: Optional[str] = None
    assignee_user_id: Optional[UUID] = None
    commentaire_traitement: Optional[str] = None


# === Schémas spécialisés === #

class CreerRegleDVFRequest(BaseModel):
    """Requête pour créer une règle de veille DVF."""
    nom: str = Field(..., min_length=1)
    code_postal: str = Field(..., min_length=5, max_length=5)
    seuil_variation_pct: float = Field(5.0, ge=1.0, le=50.0)
    periode_comparaison_jours: int = Field(30, ge=7, le=365)
    dossier_id: Optional[UUID] = None


class CreerRegleLegifraneeRequest(BaseModel):
    """Requête pour créer une règle de veille Légifrance."""
    nom: str = Field(..., min_length=1)
    articles_codes: List[str] = Field(..., min_items=1, max_items=20)
    codes_surveilles: List[str] = Field(
        default=["Code civil", "CGI"],
        description="Codes légaux à surveiller"
    )


class CreerRegleBOFIPRequest(BaseModel):
    """Requête pour créer une règle de veille BOFIP."""
    nom: str = Field(..., min_length=1)
    pages_surveillees: List[str] = Field(..., min_items=1, max_items=10)
    surveillance_baremes: bool = Field(True)


class ExecutionJobRequest(BaseModel):
    """Requête pour l'exécution manuelle d'un job."""
    job_id: str = Field(..., description="ID du job à exécuter")
    force: bool = Field(False, description="Forcer l'exécution même si récente")


class RapportVeilleRequest(BaseModel):
    """Requête pour générer un rapport de veille."""
    periode_debut: date = Field(..., description="Date de début du rapport")
    periode_fin: date = Field(..., description="Date de fin du rapport")
    sources: Optional[List[TypeSource]] = Field(None, description="Sources à inclure")
    niveaux_impact: Optional[List[NiveauImpact]] = Field(None, description="Niveaux à inclure")
    dossier_id: Optional[UUID] = Field(None, description="Rapport pour un dossier spécifique")


class StatutSchedulerResponse(BaseModel):
    """Réponse pour le statut du scheduler."""
    actif: bool
    jobs_configures: int
    derniere_execution: Optional[datetime] = None
    prochaine_execution: Optional[datetime] = None
    jobs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RapportVeilleResponse(BaseModel):
    """Réponse pour un rapport de veille."""
    periode_debut: date
    periode_fin: date
    total_alertes: int
    alertes_par_source: Dict[str, int]
    alertes_par_niveau: Dict[str, int]
    dossiers_impactes: int
    temps_response_moyen_ms: int

    # Détails des alertes
    alertes_critiques: List[AlerteResponse] = Field(default_factory=list)
    alertes_recentes: List[AlerteResponse] = Field(default_factory=list)

    # Statistiques
    regles_actives: int
    verifications_reussies_pct: float

    # Recommandations
    recommandations: List[str] = Field(default_factory=list)


class AnalyseImpactRequest(BaseModel):
    """Requête pour analyser l'impact d'une alerte."""
    alerte_id: UUID
    dossier_id: Optional[UUID] = None
    inclure_recommandations: bool = Field(True)


class AnalyseImpactResponse(BaseModel):
    """Réponse pour l'analyse d'impact."""
    alerte_id: UUID
    dossier_id: Optional[UUID] = None
    analyse_impact: str
    niveau_urgence: NiveauImpact
    actions_recommandees: List[str] = Field(default_factory=list)
    delai_action_jours: Optional[int] = None


# === Schémas de liste === #

class ListeVeilleRulesResponse(BaseModel):
    """Réponse pour la liste des règles de veille."""
    regles: List[VeilleRuleResponse]
    total: int
    actives: int
    inactives: int
    par_source: Dict[str, int] = Field(default_factory=dict)


class ListeAlertesResponse(BaseModel):
    """Réponse pour la liste des alertes."""
    alertes: List[AlerteResponse]
    total: int
    nouvelles: int
    en_cours: int
    traitees: int
    par_niveau: Dict[str, int] = Field(default_factory=dict)


class FiltreAlertesRequest(BaseModel):
    """Filtres pour la recherche d'alertes."""
    niveau_impact: Optional[NiveauImpact] = None
    statut: Optional[StatutAlerte] = None
    type_source: Optional[TypeSource] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    dossier_id: Optional[UUID] = None
    assignee_user_id: Optional[UUID] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class FiltreRulesRequest(BaseModel):
    """Filtres pour la recherche de règles."""
    type_source: Optional[TypeSource] = None
    active: Optional[bool] = None
    code_postal: Optional[str] = None
    dossier_id: Optional[UUID] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)