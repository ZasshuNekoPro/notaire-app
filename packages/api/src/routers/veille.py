"""
Routes API pour le système de veille automatique.
CRUD complet, gestion scheduler, rapports et analyses d'impact.
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.veille import (
    VeilleRule, Alerte, HistoriqueVeille,
    TypeSource, NiveauImpact, StatutAlerte
)
from src.models.dossiers import Dossier
from src.models.auth import User
from src.schemas.veille import (
    VeilleRuleCreate, VeilleRuleResponse, VeilleRuleUpdate, ListeVeilleRulesResponse,
    AlerteResponse, AlerteUpdate, ListeAlertesResponse,
    CreerRegleDVFRequest, CreerRegleLegifraneeRequest, CreerRegleBOFIPRequest,
    ExecutionJobRequest, RapportVeilleRequest, RapportVeilleResponse,
    StatutSchedulerResponse, AnalyseImpactRequest, AnalyseImpactResponse,
    FiltreAlertesRequest, FiltreRulesRequest
)
from src.services.veille_service import (
    VeilleEngine, creer_regle_veille_dvf, creer_regle_veille_legifrance
)
from src.scheduler import get_scheduler
from src.auth.dependencies import get_current_user, require_role


router = APIRouter(prefix="/veille", tags=["veille"])
logger = logging.getLogger(__name__)


# === Routes règles de veille === #

@router.get(
    "/regles",
    response_model=ListeVeilleRulesResponse,
    summary="Lister les règles de veille"
)
async def lister_regles_veille(
    filtres: FiltreRulesRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Liste toutes les règles de veille configurées avec filtres optionnels.

    - **type_source**: Filtrer par source (DVF, Légifrance, BOFIP)
    - **active**: Règles actives ou inactives
    - **code_postal**: Filtrer par code postal (DVF)
    - **dossier_id**: Règles liées à un dossier spécifique
    """
    try:
        # Construction de la requête avec filtres
        query = select(VeilleRule)

        if filtres.type_source:
            query = query.where(VeilleRule.type_source == filtres.type_source)

        if filtres.active is not None:
            query = query.where(VeilleRule.active == filtres.active)

        if filtres.code_postal:
            query = query.where(VeilleRule.code_postal == filtres.code_postal)

        if filtres.dossier_id:
            query = query.where(VeilleRule.dossier_id == filtres.dossier_id)

        # Pagination
        query = query.offset(filtres.offset).limit(filtres.limit)

        # Exécution avec relations
        query = query.options(selectinload(VeilleRule.alertes))
        result = await db.execute(query)
        regles = list(result.scalars().all())

        # Statistiques générales
        stats_query = select(
            func.count(VeilleRule.id).label('total'),
            func.count().filter(VeilleRule.active == True).label('actives'),
            func.count().filter(VeilleRule.active == False).label('inactives')
        )
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()

        # Répartition par source
        sources_query = select(
            VeilleRule.type_source,
            func.count(VeilleRule.id)
        ).group_by(VeilleRule.type_source)
        sources_result = await db.execute(sources_query)
        par_source = {source: count for source, count in sources_result.all()}

        return ListeVeilleRulesResponse(
            regles=regles,
            total=stats.total,
            actives=stats.actives,
            inactives=stats.inactives,
            par_source=par_source
        )

    except Exception as e:
        logger.error(f"Erreur liste règles veille: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des règles de veille"
        )


@router.post(
    "/regles",
    response_model=VeilleRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une règle de veille générique"
)
async def creer_regle_veille(
    regle_data: VeilleRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Crée une nouvelle règle de veille générique.
    Pour des règles spécialisées, utiliser les endpoints dédiés.
    """
    try:
        regle = VeilleRule(**regle_data.model_dump())
        db.add(regle)
        await db.commit()
        await db.refresh(regle)

        logger.info(f"Règle veille créée: {regle.nom} ({regle.type_source})")

        return regle

    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création règle: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la création de la règle de veille"
        )


@router.post(
    "/regles/dvf",
    response_model=VeilleRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une règle de veille DVF"
)
async def creer_regle_dvf(
    regle_data: CreerRegleDVFRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Crée une règle de veille spécialisée pour les variations DVF.

    - **code_postal**: Code postal à surveiller (5 chiffres)
    - **seuil_variation_pct**: Seuil de déclenchement en % (défaut: 5%)
    - **periode_comparaison_jours**: Période de comparaison (défaut: 30j)
    """
    try:
        regle = await creer_regle_veille_dvf(
            nom=regle_data.nom,
            code_postal=regle_data.code_postal,
            db=db,
            dossier_id=regle_data.dossier_id
        )

        # Personnaliser la configuration
        regle.configuration.update({
            "seuil_variation_pct": regle_data.seuil_variation_pct,
            "periode_comparaison_jours": regle_data.periode_comparaison_jours
        })

        await db.commit()
        await db.refresh(regle)

        logger.info(f"Règle DVF créée: {regle.code_postal} (seuil {regle_data.seuil_variation_pct}%)")

        return regle

    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création règle DVF: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la création de la règle DVF"
        )


@router.post(
    "/regles/legifrance",
    response_model=VeilleRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une règle de veille Légifrance"
)
async def creer_regle_legifrance(
    regle_data: CreerRegleLegifraneeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Crée une règle de veille spécialisée pour Légifrance.

    - **articles_codes**: Liste des articles à surveiller
    - **codes_surveilles**: Codes légaux (défaut: Code civil, CGI)
    """
    try:
        regle = await creer_regle_veille_legifrance(
            nom=regle_data.nom,
            articles_codes=regle_data.articles_codes,
            db=db
        )

        # Ajouter les codes surveillés
        regle.configuration.update({
            "codes_surveilles": regle_data.codes_surveilles,
            "verification_quotidienne": True
        })

        await db.commit()
        await db.refresh(regle)

        logger.info(f"Règle Légifrance créée: {len(regle_data.articles_codes)} articles")

        return regle

    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création règle Légifrance: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la création de la règle Légifrance"
        )


@router.get(
    "/regles/{regle_id}",
    response_model=VeilleRuleResponse,
    summary="Détail d'une règle de veille"
)
async def get_regle_veille(
    regle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Récupère les détails d'une règle de veille avec ses alertes associées.
    """
    try:
        query = select(VeilleRule).where(VeilleRule.id == regle_id)
        query = query.options(selectinload(VeilleRule.alertes))
        result = await db.execute(query)
        regle = result.scalar_one_or_none()

        if not regle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Règle de veille {regle_id} non trouvée"
            )

        return regle

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération règle {regle_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la règle"
        )


@router.put(
    "/regles/{regle_id}",
    response_model=VeilleRuleResponse,
    summary="Modifier une règle de veille"
)
async def modifier_regle_veille(
    regle_id: UUID,
    regle_update: VeilleRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Modifie une règle de veille existante.
    """
    try:
        query = select(VeilleRule).where(VeilleRule.id == regle_id)
        result = await db.execute(query)
        regle = result.scalar_one_or_none()

        if not regle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Règle de veille {regle_id} non trouvée"
            )

        # Mise à jour des champs modifiés
        update_data = regle_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(regle, field, value)

        await db.commit()
        await db.refresh(regle)

        logger.info(f"Règle veille modifiée: {regle.nom}")

        return regle

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur modification règle {regle_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la modification de la règle"
        )


@router.delete(
    "/regles/{regle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une règle de veille"
)
async def supprimer_regle_veille(
    regle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Supprime une règle de veille et toutes ses alertes associées.
    """
    try:
        query = select(VeilleRule).where(VeilleRule.id == regle_id)
        result = await db.execute(query)
        regle = result.scalar_one_or_none()

        if not regle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Règle de veille {regle_id} non trouvée"
            )

        await db.delete(regle)
        await db.commit()

        logger.info(f"Règle veille supprimée: {regle.nom}")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur suppression règle {regle_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la règle"
        )


# === Routes alertes === #

@router.get(
    "/alertes",
    response_model=ListeAlertesResponse,
    summary="Lister les alertes"
)
async def lister_alertes(
    filtres: FiltreAlertesRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Liste toutes les alertes de veille avec filtres avancés.

    - **niveau_impact**: Filtrer par niveau (info, faible, moyen, fort, critique)
    - **statut**: Filtrer par statut (nouvelle, en_cours, traitee, archivee)
    - **type_source**: Filtrer par source (DVF, Légifrance, BOFIP)
    - **date_debut/date_fin**: Période de création des alertes
    """
    try:
        # Construction de la requête avec filtres
        query = select(Alerte).options(selectinload(Alerte.veille_rule))

        if filtres.niveau_impact:
            query = query.where(Alerte.niveau_impact == filtres.niveau_impact)

        if filtres.statut:
            query = query.where(Alerte.statut == filtres.statut)

        if filtres.type_source:
            query = query.join(VeilleRule).where(VeilleRule.type_source == filtres.type_source)

        if filtres.date_debut:
            query = query.where(Alerte.created_at >= filtres.date_debut)

        if filtres.date_fin:
            query = query.where(Alerte.created_at <= filtres.date_fin)

        if filtres.dossier_id:
            # Alertes concernant un dossier spécifique
            query = query.where(Alerte.dossiers_impactes.contains([str(filtres.dossier_id)]))

        if filtres.assignee_user_id:
            query = query.where(Alerte.assignee_user_id == filtres.assignee_user_id)

        # Pagination et tri (plus récentes en premier)
        query = query.order_by(Alerte.created_at.desc())
        query = query.offset(filtres.offset).limit(filtres.limit)

        result = await db.execute(query)
        alertes = list(result.scalars().all())

        # Statistiques
        stats_query = select(
            func.count(Alerte.id).label('total'),
            func.count().filter(Alerte.statut == StatutAlerte.NOUVELLE).label('nouvelles'),
            func.count().filter(Alerte.statut == StatutAlerte.EN_COURS).label('en_cours'),
            func.count().filter(Alerte.statut == StatutAlerte.TRAITEE).label('traitees')
        )
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()

        # Répartition par niveau
        niveaux_query = select(
            Alerte.niveau_impact,
            func.count(Alerte.id)
        ).group_by(Alerte.niveau_impact)
        niveaux_result = await db.execute(niveaux_query)
        par_niveau = {niveau.value: count for niveau, count in niveaux_result.all()}

        return ListeAlertesResponse(
            alertes=alertes,
            total=stats.total,
            nouvelles=stats.nouvelles,
            en_cours=stats.en_cours,
            traitees=stats.traitees,
            par_niveau=par_niveau
        )

    except Exception as e:
        logger.error(f"Erreur liste alertes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des alertes"
        )


@router.get(
    "/alertes/{alerte_id}",
    response_model=AlerteResponse,
    summary="Détail d'une alerte"
)
async def get_alerte(
    alerte_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Récupère les détails d'une alerte spécifique.
    """
    try:
        query = select(Alerte).where(Alerte.id == alerte_id)
        query = query.options(selectinload(Alerte.veille_rule))
        result = await db.execute(query)
        alerte = result.scalar_one_or_none()

        if not alerte:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerte {alerte_id} non trouvée"
            )

        return alerte

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération alerte {alerte_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'alerte"
        )


@router.put(
    "/alertes/{alerte_id}",
    response_model=AlerteResponse,
    summary="Modifier une alerte"
)
async def modifier_alerte(
    alerte_id: UUID,
    alerte_update: AlerteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Modifie une alerte (changement de statut, assignation, commentaire).
    """
    try:
        query = select(Alerte).where(Alerte.id == alerte_id)
        result = await db.execute(query)
        alerte = result.scalar_one_or_none()

        if not alerte:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerte {alerte_id} non trouvée"
            )

        # Mise à jour des champs
        update_data = alerte_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(alerte, field, value)

        # Si changement de statut vers traité, enregistrer la date
        if alerte_update.statut == StatutAlerte.TRAITEE:
            alerte.date_traitement = datetime.now()

        await db.commit()
        await db.refresh(alerte)

        logger.info(f"Alerte {alerte_id} modifiée: statut {alerte.statut}")

        return alerte

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur modification alerte {alerte_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la modification de l'alerte"
        )


# === Routes scheduler === #

@router.get(
    "/scheduler/statut",
    response_model=StatutSchedulerResponse,
    summary="Statut du scheduler de veille"
)
async def statut_scheduler(
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Retourne le statut du scheduler et des jobs de veille.
    """
    try:
        scheduler = get_scheduler()

        if not scheduler:
            return StatutSchedulerResponse(
                actif=False,
                jobs_configures=0
            )

        jobs_info = scheduler.get_statut_jobs()

        # Calculer prochaine exécution globale
        prochaine_execution = None
        if jobs_info and "erreur" not in jobs_info:
            prochaines = [
                datetime.fromisoformat(job_info.get("prochaine_execution"))
                for job_info in jobs_info.values()
                if job_info.get("prochaine_execution")
            ]
            if prochaines:
                prochaine_execution = min(prochaines)

        return StatutSchedulerResponse(
            actif=scheduler.scheduler.running if scheduler else False,
            jobs_configures=len(jobs_info) if jobs_info and "erreur" not in jobs_info else 0,
            prochaine_execution=prochaine_execution,
            jobs=jobs_info if "erreur" not in jobs_info else {}
        )

    except Exception as e:
        logger.error(f"Erreur statut scheduler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du statut scheduler"
        )


@router.post(
    "/scheduler/executer",
    summary="Exécuter manuellement un job de veille"
)
async def executer_job_manuel(
    request: ExecutionJobRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "admin"]))
):
    """
    Exécute manuellement un job de veille spécifique.

    Jobs disponibles:
    - `veille_dvf_hebdo`: Vérification DVF complète
    - `veille_legifrance_quotidien`: Vérification Légifrance
    - `veille_bofip_quotidien`: Vérification BOFIP
    - `rapport_veille_hebdo`: Génération rapport synthèse
    """
    try:
        scheduler = get_scheduler()

        if not scheduler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scheduler de veille non démarré"
            )

        # Exécution manuelle
        resultat = await scheduler.executer_job_manuel(request.job_id)

        if resultat["succes"]:
            logger.info(f"Job {request.job_id} exécuté manuellement par {current_user.email}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Job {request.job_id} exécuté avec succès",
                    "details": resultat
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erreur exécution job: {resultat.get('erreur')}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur exécution manuelle job {request.job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution du job"
        )


# === Routes rapports et analyses === #

@router.post(
    "/analyser-impact",
    response_model=AnalyseImpactResponse,
    summary="Analyser l'impact d'une alerte"
)
async def analyser_impact_alerte(
    request: AnalyseImpactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["notaire", "clerc", "admin"]))
):
    """
    Analyse l'impact d'une alerte sur un dossier spécifique ou l'étude.
    Utilise l'IA pour générer des recommandations contextuelles.
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

        # Analyse d'impact via le moteur de veille
        engine = VeilleEngine(db)

        if dossier:
            analyse = await engine.analyser_impact_sur_dossier(alerte, dossier)
        else:
            # Analyse générale
            analyse = f"Cette alerte {alerte.niveau_impact.value} nécessite " \
                     f"une attention particulière de l'étude notariale."

        # Génération des recommandations
        actions_recommandees = []
        delai_jours = None

        if alerte.niveau_impact == NiveauImpact.CRITIQUE:
            actions_recommandees = [
                "Vérification immédiate par le notaire",
                "Mise à jour des procédures internes",
                "Information des clients concernés"
            ]
            delai_jours = 1

        elif alerte.niveau_impact == NiveauImpact.FORT:
            actions_recommandees = [
                "Révision des dossiers concernés",
                "Consultation juridique si nécessaire"
            ]
            delai_jours = 7

        elif alerte.niveau_impact == NiveauImpact.MOYEN:
            actions_recommandees = [
                "Surveillance renforcée",
                "Planifier vérification"
            ]
            delai_jours = 30

        # Mise à jour de l'alerte avec l'analyse
        alerte.analyse_impact = analyse
        await db.commit()

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
        logger.error(f"Erreur analyse impact alerte {request.alerte_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'analyse d'impact"
        )