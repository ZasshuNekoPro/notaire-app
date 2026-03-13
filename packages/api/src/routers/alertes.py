"""
Routes API REST pour la gestion des alertes.
CRUD alertes + analyse impact IA + statistiques temps réel.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from src.database import get_db
from src.models.veille import (
    Alerte, VeilleRule, HistoriqueVeille,
    NiveauImpact, StatutAlerte, TypeSource
)
from src.models.dossiers import Dossier
from src.models.auth import User
from src.schemas.veille import (
    AlerteResponse, AlerteUpdate,
    ListeAlertesResponse, FiltreAlertesRequest,
    AnalyseImpactRequest, AnalyseImpactResponse
)
from src.services.veille_service import VeilleEngine
from src.auth.dependencies import get_current_user, require_role
from src.routers.notifications import diffuser_alerte_websocket, redis_handler


router = APIRouter(prefix="/alertes", tags=["alertes"])
logger = logging.getLogger(__name__)


# === Modèles de réponse spécialisés === #

class AlerteDetailResponse(AlerteResponse):
    """Réponse détaillée d'une alerte avec analyse IA lazy."""
    analyse_impact_ia: Optional[str] = None
    dossiers_details: Optional[List[Dict]] = None
    historique_statuts: Optional[List[Dict]] = None


class AlerteStatsResponse(BaseModel):
    """Statistiques des alertes de l'étude."""
    total_alertes: int
    non_lues: int
    critiques_actives: int
    par_impact: Dict[str, int]
    par_source: Dict[str, int]
    derniere_alerte: Optional[AlerteResponse] = None
    tendance_7j: Dict[str, int]  # Évolution sur 7 jours


class AlerteTestRequest(BaseModel):
    """Requête pour créer une alerte de test (dev uniquement)."""
    titre: str
    contenu: str
    niveau_impact: NiveauImpact
    type_source: TypeSource
    dossier_id: Optional[UUID] = None


# === Routes principales === #

@router.get(
    "/",
    response_model=ListeAlertesResponse,
    summary="Lister les alertes avec filtres"
)
async def lister_alertes(
    lue: Optional[bool] = Query(None, description="Filtrer par statut lu/non lu"),
    dossier_id: Optional[UUID] = Query(None, description="Alertes d'un dossier spécifique"),
    impact: Optional[NiveauImpact] = Query(None, description="Niveau d'impact"),
    source: Optional[TypeSource] = Query(None, description="Type de source"),
    limit: int = Query(20, ge=1, le=100, description="Nombre max de résultats"),
    offset: int = Query(0, ge=0, description="Décalage pour pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Liste toutes les alertes avec filtres avancés.

    **Filtres disponibles** :
    - `lue` : true/false pour alertes lues/non lues
    - `dossier_id` : UUID du dossier concerné
    - `impact` : niveau d'impact (info, faible, moyen, fort, critique)
    - `source` : type de source (dvf, legifrance, bofip)
    - `limit/offset` : pagination

    **Tri** : Par date de création décroissante (plus récentes en premier)
    """
    try:
        # Construction de la requête avec filtres
        query = select(Alerte).options(selectinload(Alerte.veille_rule))

        # Filtres
        if lue is not None:
            # Simulation du statut "lu" via date_traitement
            if lue:
                query = query.where(Alerte.date_traitement.is_not(None))
            else:
                query = query.where(Alerte.date_traitement.is_(None))

        if dossier_id:
            # Recherche dans les dossiers impactés (JSON array)
            query = query.where(Alerte.dossiers_impactes.contains([str(dossier_id)]))

        if impact:
            query = query.where(Alerte.niveau_impact == impact)

        if source:
            query = query.join(VeilleRule).where(VeilleRule.type_source == source)

        # Pagination et tri
        query = query.order_by(desc(Alerte.created_at))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        alertes = list(result.scalars().all())

        # Statistiques pour la réponse
        stats_query = select(
            func.count(Alerte.id).label('total'),
            func.count().filter(Alerte.date_traitement.is_(None)).label('non_lues'),
            func.count().filter(
                and_(
                    Alerte.statut == StatutAlerte.NOUVELLE,
                    Alerte.niveau_impact == NiveauImpact.CRITIQUE
                )
            ).label('critiques')
        )
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()

        # Répartition par niveau d'impact
        niveaux_query = select(
            Alerte.niveau_impact,
            func.count(Alerte.id)
        ).group_by(Alerte.niveau_impact)
        niveaux_result = await db.execute(niveaux_query)
        par_niveau = {niveau.value: count for niveau, count in niveaux_result.all()}

        return ListeAlertesResponse(
            alertes=alertes,
            total=stats.total,
            nouvelles=stats.non_lues,  # Mapping non_lues → nouvelles
            en_cours=0,  # TODO: calculer selon statut
            traitees=stats.total - stats.non_lues,
            par_niveau=par_niveau
        )

    except Exception as e:
        logger.error(f"Erreur liste alertes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des alertes"
        )


@router.get(
    "/{alerte_id}",
    response_model=AlerteDetailResponse,
    summary="Détail d'une alerte avec analyse IA"
)
async def get_alerte_detail(
    alerte_id: UUID,
    inclure_analyse: bool = Query(True, description="Calculer analyse impact IA"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Récupère les détails complets d'une alerte.

    **Analyse IA lazy** : L'analyse d'impact est calculée seulement si `inclure_analyse=true`
    et si elle n'existe pas déjà en base.

    **Informations incluses** :
    - Détail de l'alerte et règle associée
    - Analyse d'impact IA (si demandée)
    - Détails des dossiers impactés
    - Historique des changements de statut
    """
    try:
        # Récupérer l'alerte avec ses relations
        query = select(Alerte).where(Alerte.id == alerte_id)
        query = query.options(selectinload(Alerte.veille_rule))
        result = await db.execute(query)
        alerte = result.scalar_one_or_none()

        if not alerte:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerte {alerte_id} non trouvée"
            )

        # Construire la réponse détaillée
        response_data = alerte.__dict__.copy()

        # Analyse IA lazy
        analyse_ia = None
        if inclure_analyse:
            if alerte.analyse_impact:
                # Analyse déjà en base
                analyse_ia = alerte.analyse_impact
            else:
                # Calculer l'analyse IA
                try:
                    engine = VeilleEngine(db)

                    # Analyser pour le premier dossier impacté
                    if alerte.dossiers_impactes:
                        premier_dossier_id = UUID(alerte.dossiers_impactes[0])
                        dossier_query = select(Dossier).where(Dossier.id == premier_dossier_id)
                        dossier_result = await db.execute(dossier_query)
                        dossier = dossier_result.scalar_one_or_none()

                        if dossier:
                            analyse_ia = await engine.analyser_impact_sur_dossier(alerte, dossier)
                        else:
                            analyse_ia = "Analyse générale : Cette alerte nécessite une attention particulière."
                    else:
                        analyse_ia = "Aucun dossier spécifique impacté. Surveillance générale recommandée."

                    # Sauvegarder l'analyse en base pour cache
                    alerte.analyse_impact = analyse_ia
                    await db.commit()

                except Exception as e:
                    logger.warning(f"Erreur analyse IA alerte {alerte_id}: {e}")
                    analyse_ia = "Erreur lors de l'analyse automatique. Vérification manuelle requise."

        # Détails des dossiers impactés
        dossiers_details = []
        if alerte.dossiers_impactes:
            for dossier_id_str in alerte.dossiers_impactes:
                try:
                    dossier_id = UUID(dossier_id_str)
                    dossier_query = select(Dossier).where(Dossier.id == dossier_id)
                    dossier_result = await db.execute(dossier_query)
                    dossier = dossier_result.scalar_one_or_none()

                    if dossier:
                        dossiers_details.append({
                            "id": str(dossier.id),
                            "numero": dossier.numero,
                            "type_acte": dossier.type_acte,
                            "statut": dossier.statut,
                            "description": dossier.description
                        })
                except ValueError:
                    logger.warning(f"UUID dossier invalide: {dossier_id_str}")

        # Historique des statuts (simulation)
        historique_statuts = [
            {
                "statut": alerte.statut.value,
                "date": alerte.created_at.isoformat() if hasattr(alerte, 'created_at') else "2025-03-13T15:00:00",
                "user": current_user.email,
                "commentaire": "Alerte créée automatiquement"
            }
        ]

        if alerte.date_traitement:
            historique_statuts.append({
                "statut": "traitee",
                "date": alerte.date_traitement.isoformat(),
                "user": current_user.email,
                "commentaire": alerte.commentaire_traitement or "Alerte traitée"
            })

        # Construire la réponse
        return AlerteDetailResponse(
            **response_data,
            analyse_impact_ia=analyse_ia,
            dossiers_details=dossiers_details,
            historique_statuts=historique_statuts
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur détail alerte {alerte_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de l'alerte"
        )


@router.patch(
    "/{alerte_id}/lire",
    response_model=AlerteResponse,
    summary="Marquer une alerte comme lue"
)
async def marquer_alerte_lue(
    alerte_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Marque une alerte comme lue par l'utilisateur actuel.

    **Action** : Met à jour `date_traitement` et `statut` vers `EN_COURS` ou `TRAITEE`.
    **Effet** : L'alerte n'apparaîtra plus dans les alertes non lues.
    """
    try:
        # Récupérer l'alerte
        query = select(Alerte).where(Alerte.id == alerte_id)
        result = await db.execute(query)
        alerte = result.scalar_one_or_none()

        if not alerte:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerte {alerte_id} non trouvée"
            )

        # Marquer comme lue
        alerte.date_traitement = datetime.now()
        alerte.statut = StatutAlerte.EN_COURS
        alerte.assignee_user_id = current_user.id
        alerte.commentaire_traitement = f"Alerte lue par {current_user.email}"

        await db.commit()
        await db.refresh(alerte)

        logger.info(f"Alerte {alerte_id} marquée lue par {current_user.email}")

        return alerte

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur marquer alerte lue {alerte_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du marquage de l'alerte"
        )


@router.post(
    "/test",
    response_model=AlerteResponse,
    summary="Créer une alerte de test (dev uniquement)"
)
async def creer_alerte_test(
    request: AlerteTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """
    Crée une alerte de test pour développement et démo.

    **Restriction** : Accessible uniquement aux administrateurs.
    **Usage** : Tests d'intégration, démo client, validation WebSocket.
    """
    try:
        # Créer une règle de test si nécessaire
        test_rule = VeilleRule(
            nom="Règle de test",
            description="Règle automatique pour alertes de test",
            type_source=request.type_source,
            configuration={"test": True},
            active=True,
            frequence_heures=24
        )
        db.add(test_rule)
        await db.flush()  # Récupérer l'ID

        # Créer l'alerte de test
        alerte_test = Alerte(
            veille_rule_id=test_rule.id,
            titre=f"[TEST] {request.titre}",
            niveau_impact=request.niveau_impact,
            statut=StatutAlerte.NOUVELLE,
            contenu=f"{request.contenu} (Alerte générée pour test)",
            details_techniques={
                "test": True,
                "created_by": current_user.email,
                "timestamp": datetime.now().isoformat()
            },
            dossiers_impactes=[str(request.dossier_id)] if request.dossier_id else None
        )

        db.add(alerte_test)
        await db.commit()
        await db.refresh(alerte_test)

        # Diffuser via WebSocket
        try:
            await diffuser_alerte_websocket(alerte_test)
        except Exception as e:
            logger.warning(f"Erreur diffusion WebSocket alerte test: {e}")

        # Publier sur Redis
        try:
            await redis_handler.publier_alerte(str(alerte_test.id))
        except Exception as e:
            logger.warning(f"Erreur publication Redis alerte test: {e}")

        logger.info(f"Alerte de test créée: {alerte_test.id} par {current_user.email}")

        return alerte_test

    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création alerte test: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de l'alerte de test"
        )


@router.get(
    "/stats",
    response_model=AlerteStatsResponse,
    summary="Statistiques des alertes de l'étude"
)
async def get_alertes_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Statistiques complètes des alertes pour dashboard.

    **Métriques incluses** :
    - Nombre total d'alertes
    - Alertes non lues
    - Alertes critiques actives
    - Répartition par impact et source
    - Dernière alerte créée
    - Tendance sur 7 jours
    """
    try:
        # Statistiques générales
        stats_query = select(
            func.count(Alerte.id).label('total'),
            func.count().filter(Alerte.date_traitement.is_(None)).label('non_lues'),
            func.count().filter(
                and_(
                    Alerte.niveau_impact == NiveauImpact.CRITIQUE,
                    Alerte.statut.in_([StatutAlerte.NOUVELLE, StatutAlerte.EN_COURS])
                )
            ).label('critiques')
        )
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()

        # Répartition par impact
        impact_query = select(
            Alerte.niveau_impact,
            func.count(Alerte.id)
        ).group_by(Alerte.niveau_impact)
        impact_result = await db.execute(impact_query)
        par_impact = {impact.value: count for impact, count in impact_result.all()}

        # Répartition par source (via join avec VeilleRule)
        source_query = select(
            VeilleRule.type_source,
            func.count(Alerte.id)
        ).join(VeilleRule).group_by(VeilleRule.type_source)
        source_result = await db.execute(source_query)
        par_source = {source.value: count for source, count in source_result.all()}

        # Dernière alerte
        derniere_query = select(Alerte).order_by(desc(Alerte.created_at)).limit(1)
        derniere_result = await db.execute(derniere_query)
        derniere_alerte = derniere_result.scalar_one_or_none()

        # Tendance 7 jours (simulation)
        # TODO: Calculer avec vraies dates created_at
        tendance_7j = {
            "2025-03-07": 2,
            "2025-03-08": 1,
            "2025-03-09": 3,
            "2025-03-10": 0,
            "2025-03-11": 4,
            "2025-03-12": 2,
            "2025-03-13": 1
        }

        return AlerteStatsResponse(
            total_alertes=stats.total,
            non_lues=stats.non_lues,
            critiques_actives=stats.critiques,
            par_impact=par_impact,
            par_source=par_source,
            derniere_alerte=derniere_alerte,
            tendance_7j=tendance_7j
        )

    except Exception as e:
        logger.error(f"Erreur stats alertes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du calcul des statistiques"
        )


# === Routes d'analyse avancée === #

@router.post(
    "/analyser-impact",
    response_model=AnalyseImpactResponse,
    summary="Analyser l'impact d'une alerte sur un dossier"
)
async def analyser_impact_alerte(
    request: AnalyseImpactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc"]))
):
    """
    Lance une analyse d'impact détaillée d'une alerte sur un dossier.

    **Analyse IA** : Utilise le moteur de veille pour générer une analyse contextuelle.
    **Recommandations** : Actions suggérées avec délais selon le niveau d'urgence.
    """
    try:
        # Récupérer l'alerte
        alerte_query = select(Alerte).where(Alerte.id == request.alerte_id)
        alerte_query = alerte_query.options(selectinload(Alerte.veille_rule))
        alerte_result = await db.execute(alerte_query)
        alerte = alerte_result.scalar_one_or_none()

        if not alerte:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerte {request.alerte_id} non trouvée"
            )

        # Récupérer le dossier si spécifié
        dossier = None
        if request.dossier_id:
            dossier_query = select(Dossier).where(Dossier.id == request.dossier_id)
            dossier_result = await db.execute(dossier_query)
            dossier = dossier_result.scalar_one_or_none()

            if not dossier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dossier {request.dossier_id} non trouvé"
                )

        # Analyse via moteur de veille
        engine = VeilleEngine(db)

        if dossier:
            analyse = await engine.analyser_impact_sur_dossier(alerte, dossier)
        else:
            analyse = f"Alerte {alerte.niveau_impact.value} nécessitant une attention " \
                     f"selon le type de source {alerte.veille_rule.type_source.value}."

        # Générer les recommandations
        actions_recommandees = []
        delai_jours = None

        if alerte.niveau_impact == NiveauImpact.CRITIQUE:
            actions_recommandees = [
                "Vérification immédiate par le notaire titulaire",
                "Mise à jour des procédures internes affectées",
                "Information urgente des clients concernés",
                "Documentation de l'impact dans les dossiers"
            ]
            delai_jours = 1

        elif alerte.niveau_impact == NiveauImpact.FORT:
            actions_recommandees = [
                "Révision approfondie des dossiers concernés",
                "Consultation juridique si nécessaire",
                "Mise à jour des modèles d'actes"
            ]
            delai_jours = 3

        elif alerte.niveau_impact == NiveauImpact.MOYEN:
            actions_recommandees = [
                "Surveillance renforcée des évolutions",
                "Planifier vérification lors du prochain dossier",
                "Veille jurisprudentielle complémentaire"
            ]
            delai_jours = 15

        else:
            actions_recommandees = [
                "Information de l'équipe lors de la réunion",
                "Mise à jour de la documentation interne"
            ]
            delai_jours = 30

        return AnalyseImpactResponse(
            alerte_id=request.alerte_id,
            dossier_id=request.dossier_id,
            analyse_impact=analyse,
            niveau_urgence=alerte.niveau_impact,
            actions_recommandees=actions_recommandees,
            delai_action_jours=delai_jours
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur analyse impact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'analyse d'impact"
        )