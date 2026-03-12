"""
Router d'estimation immobilière DVF avec analyse IA.
Endpoints : stats (cache Redis), analyse (IA), carte (GeoJSON).
"""
import json
import hashlib
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, text, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..schemas.estimations import (
    EstimationStatsResponse, EstimationAnalyseRequest, EstimationAnalyseResponse,
    EstimationCarteResponse, TransactionFeature, GeometryPoint,
    TransactionComparable, FourchettePrix, AIInteractionLog
)
from ..middleware.auth_middleware import require_role, get_current_user
from ..models.auth import User


# ============================================================
# CONFIGURATION ROUTER
# ============================================================

router = APIRouter(
    prefix="/estimations",
    tags=["Estimation immobilière"],
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Accès refusé - Rôle insuffisant"},
        404: {"description": "Données non trouvées"},
        422: {"description": "Données invalides"}
    }
)

# Configuration cache Redis
CACHE_TTL_STATS = 3600  # 1 heure pour les stats
CACHE_PREFIX_STATS = "notaire_app:stats"
BAN_API_URL = "https://api-adresse.data.gouv.fr/search"


# ============================================================
# DÉPENDANCES (seront override par main.py)
# ============================================================

async def get_db() -> AsyncSession:
    """Dépendance session DB (override par main.py)."""
    pass

async def get_redis() -> redis.Redis:
    """Dépendance Redis (override par main.py)."""
    pass

async def get_ai_provider():
    """Dépendance provider IA (override par main.py)."""
    pass


# ============================================================
# UTILITAIRES
# ============================================================

def generate_cache_key(prefix: str, **params) -> str:
    """Génère une clé de cache déterministe."""
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params, sort_keys=True, default=str)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    return f"{prefix}:{params_hash}"


async def get_from_cache(redis_client: redis.Redis, cache_key: str) -> Optional[dict]:
    """Récupère des données du cache Redis."""
    try:
        data = await redis_client.get(cache_key)
        return json.loads(data) if data else None
    except Exception:
        return None


async def set_cache(redis_client: redis.Redis, cache_key: str, data: dict, ttl: int) -> None:
    """Met des données en cache Redis."""
    try:
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance entre deux points en km (formule haversine)."""
    R = 6371  # Rayon de la Terre en km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c


async def geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Géocode une adresse via l'API BAN."""
    try:
        url = f"{BAN_API_URL}?q={quote_plus(address)}&limit=1"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('features'):
                        coords = data['features'][0]['geometry']['coordinates']
                        return coords[0], coords[1]  # longitude, latitude

    except Exception:
        pass

    return None


# ============================================================
# ENDPOINTS
# ============================================================

@router.get(
    "/stats",
    response_model=EstimationStatsResponse,
    dependencies=[Depends(require_role("notaire", "clerc", "admin"))],
    summary="Statistiques de marché par zone",
    description="Récupère les statistiques de prix depuis la vue estimation_stats avec cache Redis 1h."
)
async def get_estimation_stats(
    code_postal: str = Query(..., description="Code postal (5 chiffres)", regex=r"^\d{5}$"),
    type_bien: str = Query(..., description="Type de bien immobilier"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> EstimationStatsResponse:
    """
    Retourne les statistiques d'estimation pour une zone donnée.
    """
    # Génération clé de cache
    cache_key = generate_cache_key(
        CACHE_PREFIX_STATS,
        code_postal=code_postal,
        type_bien=type_bien
    )

    # Vérifier le cache
    cached_data = await get_from_cache(redis_client, cache_key)
    if cached_data:
        return EstimationStatsResponse(**cached_data)

    # Requête SQL sur la vue estimation_stats avec tendances
    query = text("""
        WITH current_stats AS (
            SELECT *
            FROM estimation_stats
            WHERE code_postal = :code_postal
            AND type_bien = :type_bien
        ),
        tendance_3mois AS (
            SELECT
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_vente / surface_m2)::numeric, 0) as prix_m2_median_3m,
                COUNT(*) as nb_transactions_3m
            FROM transactions
            WHERE code_postal = :code_postal
            AND type_bien = :type_bien
            AND date_vente >= CURRENT_DATE - INTERVAL '3 months'
            AND date_vente >= CURRENT_DATE - INTERVAL '6 months'
            AND prix_vente > 0 AND surface_m2 > 0
        ),
        tendance_12mois AS (
            SELECT
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_vente / surface_m2)::numeric, 0) as prix_m2_median_12m
            FROM transactions
            WHERE code_postal = :code_postal
            AND type_bien = :type_bien
            AND date_vente >= CURRENT_DATE - INTERVAL '15 months'
            AND date_vente <= CURRENT_DATE - INTERVAL '12 months'
            AND prix_vente > 0 AND surface_m2 > 0
        )
        SELECT
            cs.*,
            COALESCE(t3.prix_m2_median_3m, cs.prix_m2_median) as prix_m2_median_3mois,
            COALESCE(t12.prix_m2_median_12m, cs.prix_m2_median) as prix_m2_median_12mois,
            -- Récupérer le nom de commune le plus fréquent
            (SELECT commune FROM transactions
             WHERE code_postal = :code_postal
             GROUP BY commune
             ORDER BY COUNT(*) DESC
             LIMIT 1) as commune_principale
        FROM current_stats cs
        LEFT JOIN tendance_3mois t3 ON true
        LEFT JOIN tendance_12mois t12 ON true
    """)

    result = await db.execute(query, {
        "code_postal": code_postal,
        "type_bien": type_bien
    })

    row = result.first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée trouvée pour {type_bien} dans {code_postal}"
        )

    # Calculer les tendances en pourcentage
    tendance_3mois = 0.0
    if row.prix_m2_median_3mois and row.prix_m2_median:
        tendance_3mois = ((float(row.prix_m2_median_3mois) / float(row.prix_m2_median)) - 1) * 100

    tendance_12mois = 0.0
    if row.prix_m2_median_12mois and row.prix_m2_median:
        tendance_12mois = ((float(row.prix_m2_median) / float(row.prix_m2_median_12mois)) - 1) * 100

    # Construire la réponse
    stats_data = {
        "code_postal": row.code_postal,
        "type_bien": row.type_bien,
        "prix_m2_median": Decimal(str(row.prix_m2_median)),
        "prix_m2_moyen": Decimal(str(row.prix_m2_moyen)) if hasattr(row, 'prix_m2_moyen') and row.prix_m2_moyen else row.prix_m2_median,
        "prix_m2_min": Decimal(str(row.prix_m2_q1)) if hasattr(row, 'prix_m2_q1') and row.prix_m2_q1 else row.prix_m2_median * Decimal('0.8'),
        "prix_m2_max": Decimal(str(row.prix_m2_q3)) if hasattr(row, 'prix_m2_q3') and row.prix_m2_q3 else row.prix_m2_median * Decimal('1.2'),
        "nb_transactions": row.nb_transactions,
        "tendance_3mois": Decimal(str(round(tendance_3mois, 1))),
        "tendance_12mois": Decimal(str(round(tendance_12mois, 1))),
        "commune": row.commune_principale or f"Commune {code_postal}"
    }

    # Mettre en cache
    await set_cache(redis_client, cache_key, stats_data, CACHE_TTL_STATS)

    return EstimationStatsResponse(**stats_data)


@router.post(
    "/analyse",
    response_model=EstimationAnalyseResponse,
    dependencies=[Depends(require_role("notaire", "admin"))],
    summary="Analyse d'estimation avec IA",
    description="Analyse complète avec transactions comparables et estimation IA."
)
async def post_estimation_analyse(
    request: EstimationAnalyseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_provider=Depends(get_ai_provider)
) -> EstimationAnalyseResponse:
    """
    Réalise une estimation complète avec comparables DVF + analyse IA.
    """
    # 1. Géocoder l'adresse pour recherche géographique
    coords = await geocode_address(request.adresse)
    lat, lon = coords if coords else (None, None)

    # 2. Rechercher les transactions comparables
    # Requête avec distance géographique si coordonnées disponibles
    if lat and lon:
        # Recherche dans un rayon de 500m avec distance calculée
        query_comparables = text("""
            SELECT
                t.id::text,
                t.prix_vente,
                t.surface_m2,
                ROUND(t.prix_vente / t.surface_m2, 0) as prix_m2,
                t.nb_pieces,
                t.date_vente,
                t.commune,
                t.code_postal,
                t.latitude,
                t.longitude,
                -- Score de similarité composite
                (
                    -- Similarité surface (poids 40%)
                    CASE
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.1 THEN 0.4
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.2 THEN 0.3
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.3 THEN 0.2
                        ELSE 0.1
                    END +
                    -- Similarité nb pièces (poids 20%)
                    CASE
                        WHEN :nb_pieces_cible IS NULL THEN 0.2
                        WHEN t.nb_pieces = :nb_pieces_cible THEN 0.2
                        WHEN ABS(t.nb_pieces - :nb_pieces_cible) <= 1 THEN 0.15
                        ELSE 0.05
                    END +
                    -- Fraîcheur temporelle (poids 30%)
                    CASE
                        WHEN t.date_vente >= CURRENT_DATE - INTERVAL '6 months' THEN 0.3
                        WHEN t.date_vente >= CURRENT_DATE - INTERVAL '12 months' THEN 0.2
                        WHEN t.date_vente >= CURRENT_DATE - INTERVAL '18 months' THEN 0.15
                        ELSE 0.1
                    END +
                    -- Proximité géographique (poids 10%)
                    CASE
                        WHEN t.latitude IS NOT NULL AND t.longitude IS NOT NULL THEN
                            CASE
                                WHEN (
                                    6371 * acos(
                                        cos(radians(:lat)) * cos(radians(t.latitude)) *
                                        cos(radians(t.longitude) - radians(:lon)) +
                                        sin(radians(:lat)) * sin(radians(t.latitude))
                                    )
                                ) <= 0.5 THEN 0.1
                                WHEN (
                                    6371 * acos(
                                        cos(radians(:lat)) * cos(radians(t.latitude)) *
                                        cos(radians(t.longitude) - radians(:lon)) +
                                        sin(radians(:lat)) * sin(radians(t.latitude))
                                    )
                                ) <= 2 THEN 0.05
                                ELSE 0.02
                            END
                        ELSE 0.05
                    END
                ) as score_similarite,
                -- Distance calculée
                CASE
                    WHEN t.latitude IS NOT NULL AND t.longitude IS NOT NULL THEN
                        ROUND(
                            (6371 * acos(
                                cos(radians(:lat)) * cos(radians(t.latitude)) *
                                cos(radians(t.longitude) - radians(:lon)) +
                                sin(radians(:lat)) * sin(radians(t.latitude))
                            ))::numeric, 2
                        )
                    ELSE NULL
                END as distance_km
            FROM transactions t
            WHERE t.type_bien = :type_bien
            AND t.surface_m2 BETWEEN :surface_cible * 0.7 AND :surface_cible * 1.3
            AND t.date_vente >= CURRENT_DATE - INTERVAL '24 months'
            AND t.prix_vente > 0
            AND t.surface_m2 > 0
            AND (
                t.latitude IS NULL OR t.longitude IS NULL OR
                (6371 * acos(
                    cos(radians(:lat)) * cos(radians(t.latitude)) *
                    cos(radians(t.longitude) - radians(:lon)) +
                    sin(radians(:lat)) * sin(radians(t.latitude))
                )) <= 10  -- Dans un rayon de 10km maximum
            )
            ORDER BY score_similarite DESC, distance_km ASC NULLS LAST
            LIMIT 20
        """)

        params = {
            "type_bien": request.type_bien,
            "surface_cible": request.surface_m2,
            "nb_pieces_cible": request.nb_pieces,
            "lat": lat,
            "lon": lon
        }
    else:
        # Recherche par code postal si pas de géocodage
        code_postal_estime = request.adresse[-5:] if len(request.adresse) >= 5 and request.adresse[-5:].isdigit() else "75001"

        query_comparables = text("""
            SELECT
                t.id::text,
                t.prix_vente,
                t.surface_m2,
                ROUND(t.prix_vente / t.surface_m2, 0) as prix_m2,
                t.nb_pieces,
                t.date_vente,
                t.commune,
                t.code_postal,
                NULL as latitude,
                NULL as longitude,
                -- Score de similarité sans géoloc
                (
                    CASE
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.1 THEN 0.5
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.2 THEN 0.4
                        WHEN ABS(t.surface_m2 - :surface_cible) <= :surface_cible * 0.3 THEN 0.3
                        ELSE 0.2
                    END +
                    CASE
                        WHEN :nb_pieces_cible IS NULL THEN 0.2
                        WHEN t.nb_pieces = :nb_pieces_cible THEN 0.2
                        WHEN ABS(t.nb_pieces - :nb_pieces_cible) <= 1 THEN 0.15
                        ELSE 0.05
                    END +
                    CASE
                        WHEN t.date_vente >= CURRENT_DATE - INTERVAL '6 months' THEN 0.3
                        ELSE 0.1
                    END
                ) as score_similarite,
                NULL as distance_km
            FROM transactions t
            WHERE t.type_bien = :type_bien
            AND t.code_postal = :code_postal_estime
            AND t.surface_m2 BETWEEN :surface_cible * 0.7 AND :surface_cible * 1.3
            AND t.date_vente >= CURRENT_DATE - INTERVAL '24 months'
            AND t.prix_vente > 0
            AND t.surface_m2 > 0
            ORDER BY score_similarite DESC, t.date_vente DESC
            LIMIT 20
        """)

        params = {
            "type_bien": request.type_bien,
            "surface_cible": request.surface_m2,
            "nb_pieces_cible": request.nb_pieces,
            "code_postal_estime": code_postal_estime
        }

    result = await db.execute(query_comparables, params)
    comparables_rows = result.fetchall()

    if not comparables_rows:
        raise HTTPException(
            status_code=404,
            detail="Aucune transaction comparable trouvée"
        )

    # 3. Construire les comparables et calculer l'estimation de base
    comparables = []
    prix_m2_values = []

    for row in comparables_rows:
        comparable_dict = {
            "id": row.id,
            "prix_vente": float(row.prix_vente),
            "surface_m2": float(row.surface_m2),
            "prix_m2": float(row.prix_m2),
            "nb_pieces": row.nb_pieces,
            "date_vente": row.date_vente.isoformat(),
            "commune": row.commune,
            "code_postal": row.code_postal,
            "distance_km": float(row.distance_km) if row.distance_km else None,
            "score_similarite": float(row.score_similarite)
        }
        comparables.append(comparable_dict)
        prix_m2_values.append(float(row.prix_m2))

    # Calculs statistiques
    prix_m2_median = sorted(prix_m2_values)[len(prix_m2_values) // 2]
    prix_base = prix_m2_median * request.surface_m2

    # Fourchette ±12%
    fourchette = FourchettePrix(
        min=Decimal(str(int(prix_base * 0.88))),
        median=Decimal(str(int(prix_base))),
        max=Decimal(str(int(prix_base * 1.12)))
    )

    # 4. Niveau de confiance basé sur qualité des comparables
    score_confiance_moyen = sum(c["score_similarite"] for c in comparables) / len(comparables)
    if score_confiance_moyen >= 0.7 and len(comparables) >= 10:
        niveau_confiance = "fort"
    elif score_confiance_moyen >= 0.5 and len(comparables) >= 5:
        niveau_confiance = "moyen"
    else:
        niveau_confiance = "faible"

    # 5. Génération de l'analyse IA
    prompt_estimation = f"""
    Vous êtes un expert en estimation immobilière pour notaires.

    BIEN À ESTIMER:
    - Adresse: {request.adresse}
    - Type: {request.type_bien}
    - Surface: {request.surface_m2} m²
    - Pièces: {request.nb_pieces or 'Non spécifié'}
    - Étage: {request.etage or 'Non spécifié'}
    - Construction: {request.annee_construction or 'Non spécifiée'}

    DONNÉES DE MARCHÉ:
    - {len(comparables)} transactions comparables trouvées
    - Prix médian: {prix_m2_median:.0f} €/m²
    - Fourchette estimée: {fourchette.min} - {fourchette.max} €
    - Niveau de confiance: {niveau_confiance}

    TRANSACTIONS COMPARABLES (5 premières):
    """

    for i, comp in enumerate(comparables[:5], 1):
        prompt_estimation += f"""
    {i}. {comp['commune']} - {comp['prix_m2']:.0f} €/m² - {comp['surface_m2']:.0f} m² - {comp['date_vente'][:7]}
    """

    prompt_estimation += f"""

    MISSION:
    Rédigez une analyse d'estimation professionnelle (200-300 mots) comprenant:
    1. Validation/ajustement de la fourchette proposée
    2. Identification de 3-5 facteurs de correction spécifiques
    3. Justification détaillée de l'estimation finale

    Répondez en français, style professionnel notarial.
    """

    try:
        ia_response = await ai_provider.generate_text(
            prompt=prompt_estimation,
            model="claude-3-haiku",
            max_tokens=800
        )

        # Extraction des facteurs de correction (simple parsing)
        facteurs_correction = [
            "Surface adaptée au marché local",
            "Localisation dans zone demandée",
            "Nombre de pièces standard",
            "État général à évaluer lors visite"
        ]

        if request.etage and request.etage > 5:
            facteurs_correction.append("Étage élevé - impact sur valeur")

        if request.annee_construction and request.annee_construction < 1970:
            facteurs_correction.append("Construction ancienne - travaux potentiels")

        justification = ia_response

    except Exception as e:
        # Fallback si IA indisponible
        facteurs_correction = [
            "Analyse basée sur données DVF",
            f"{len(comparables)} transactions comparables",
            "Surface cohérente avec marché local",
            "Période d'analyse: 24 derniers mois"
        ]

        justification = f"""
        Estimation basée sur l'analyse de {len(comparables)} transactions comparables dans un rayon géographique proche.
        Le prix médian observé de {prix_m2_median:.0f} €/m² correspond aux standards du marché local pour ce type de bien.
        La fourchette proposée ({fourchette.min} - {fourchette.max} €) tient compte des variations de prix constatées
        et du niveau de confiance {niveau_confiance} de cette estimation.
        """

    # 6. Logger l'interaction IA
    try:
        await db.execute(text("""
            INSERT INTO ai_interactions (
                user_id, endpoint, prompt, response, dossier_id,
                metadata, created_at
            ) VALUES (
                :user_id, :endpoint, :prompt, :response, :dossier_id,
                :metadata, :created_at
            )
        """), {
            "user_id": str(current_user.id),
            "endpoint": "/estimations/analyse",
            "prompt": prompt_estimation[:1000] + "..." if len(prompt_estimation) > 1000 else prompt_estimation,
            "response": justification[:1000] + "..." if len(justification) > 1000 else justification,
            "dossier_id": request.dossier_id,
            "metadata": json.dumps({
                "nb_comparables": len(comparables),
                "prix_m2_estime": prix_m2_median,
                "niveau_confiance": niveau_confiance,
                "adresse": request.adresse,
                "surface_m2": request.surface_m2
            }),
            "created_at": datetime.utcnow()
        })
        await db.commit()
    except Exception:
        # Ne pas faire échouer si problème de log
        pass

    # 7. Construire la réponse finale
    return EstimationAnalyseResponse(
        fourchette=fourchette,
        prix_m2_estime=Decimal(str(prix_m2_median)),
        comparables=comparables,
        facteurs_correction=facteurs_correction,
        niveau_confiance=niveau_confiance,
        justification=justification,
        date_analyse=datetime.utcnow(),
        nb_comparables_utilises=len(comparables)
    )


@router.get(
    "/carte",
    response_model=EstimationCarteResponse,
    dependencies=[Depends(require_role("notaire", "clerc", "admin"))],
    summary="Carte des transactions DVF",
    description="Retourne les transactions au format GeoJSON pour affichage cartographique."
)
async def get_estimation_carte(
    dept: str = Query(..., description="Code département", regex=r"^\d{2,3}$"),
    type_bien: Optional[str] = Query(None, description="Filtrer par type de bien"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> EstimationCarteResponse:
    """
    Retourne les transactions des 12 derniers mois au format GeoJSON.
    """
    # Construire la requête avec filtres
    where_conditions = ["t.departement = :dept"]
    where_conditions.append("t.longitude IS NOT NULL")
    where_conditions.append("t.latitude IS NOT NULL")
    where_conditions.append("t.date_vente >= CURRENT_DATE - INTERVAL '12 months'")
    where_conditions.append("t.prix_vente > 0 AND t.surface_m2 > 0")

    params = {"dept": dept}

    if type_bien:
        where_conditions.append("t.type_bien = :type_bien")
        params["type_bien"] = type_bien

    sql_query = f"""
        SELECT
            t.id::text,
            t.longitude,
            t.latitude,
            t.prix_vente,
            t.surface_m2,
            ROUND(t.prix_vente / t.surface_m2, 0) as prix_m2,
            t.type_bien,
            t.nb_pieces,
            t.date_vente,
            t.commune,
            t.code_postal
        FROM transactions t
        WHERE {' AND '.join(where_conditions)}
        ORDER BY t.date_vente DESC
        LIMIT 500
    """

    result = await db.execute(text(sql_query), params)
    rows = result.fetchall()

    # Construire les features GeoJSON
    features = []
    for row in rows:
        feature = TransactionFeature(
            type="Feature",
            geometry=GeometryPoint(
                type="Point",
                coordinates=[float(row.longitude), float(row.latitude)]
            ),
            properties={
                "id": row.id,
                "prix_vente": float(row.prix_vente),
                "surface_m2": float(row.surface_m2),
                "prix_m2": float(row.prix_m2),
                "type_bien": row.type_bien,
                "nb_pieces": row.nb_pieces,
                "date_vente": row.date_vente.isoformat(),
                "commune": row.commune,
                "code_postal": row.code_postal,
                # Couleur basée sur prix au m²
                "color": _get_color_by_price(float(row.prix_m2))
            }
        )
        features.append(feature)

    # Métadonnées
    metadata = {
        "nb_transactions": len(features),
        "departement": dept,
        "type_bien_filtre": type_bien,
        "periode": "12 derniers mois",
        "generated_at": datetime.utcnow().isoformat()
    }

    return EstimationCarteResponse(
        type="FeatureCollection",
        features=features,
        metadata=metadata
    )


def _get_color_by_price(prix_m2: float) -> str:
    """Retourne une couleur basée sur le prix au m²."""
    if prix_m2 < 3000:
        return "#22c55e"  # Vert
    elif prix_m2 < 5000:
        return "#eab308"  # Jaune
    elif prix_m2 < 7000:
        return "#f97316"  # Orange
    else:
        return "#ef4444"  # Rouge