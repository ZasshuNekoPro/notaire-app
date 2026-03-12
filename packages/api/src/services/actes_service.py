#!/usr/bin/env python3
"""
Service pour l'analyse et la rédaction d'actes notariaux
"""
import json
import logging
from typing import Dict, Any, List, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ai_core.src.rag import get_notaire_rag
from packages.ai_core.src.providers import get_ai_provider
from ..schemas.actes import (
    TypeActe,
    StyleRedaction,
    AnalyserActeRequest,
    AnalyseActeResponse,
    RedigerActeRequest,
    RelireActeRequest,
    RelectureActeResponse,
    CorrectionActe,
    RisqueJuridique
)

logger = logging.getLogger(__name__)


# Configuration des clauses obligatoires par type d'acte
CLAUSES_OBLIGATOIRES = {
    TypeActe.VENTE: [
        "Identification des parties",
        "Description du bien",
        "Prix et modalités de paiement",
        "Origine de propriété",
        "Diagnostics immobiliers",
        "Servitudes et charges",
        "État hypothécaire",
        "Conditions suspensives"
    ],
    TypeActe.SUCCESSION: [
        "État civil du défunt",
        "Date et lieu de décès",
        "Régime matrimonial",
        "Inventaire des biens",
        "Identification des héritiers",
        "Calcul des droits de succession",
        "Partage des biens",
        "Quittances fiscales"
    ],
    TypeActe.DONATION: [
        "Identification donateur/donataire",
        "Description des biens donnés",
        "Conditions de la donation",
        "Réserve d'usufruit éventuelle",
        "Calcul des droits",
        "Acceptation du donataire"
    ]
}


async def analyser_acte(request: AnalyserActeRequest, db: AsyncSession) -> AnalyseActeResponse:
    """
    Analyse un acte et suggère les améliorations

    Args:
        request: Requête d'analyse
        db: Session base de données

    Returns:
        Analyse structurée de l'acte
    """
    try:
        # Vérifier le type d'acte supporté
        if request.type_acte not in CLAUSES_OBLIGATOIRES:
            raise ValueError(f"Type d'acte {request.type_acte} non supporté")

        # Obtenir les clauses obligatoires pour ce type d'acte
        clauses_requises = CLAUSES_OBLIGATOIRES[request.type_acte]

        # Analyser les éléments fournis vs clauses obligatoires
        clauses_manquantes = await _identifier_clauses_manquantes(
            request.type_acte,
            request.elements,
            clauses_requises
        )

        # Rechercher les articles de loi applicables via RAG
        articles_loi = await _rechercher_articles_applicables(
            request.type_acte,
            request.elements
        )

        # Générer les points d'attention spécifiques
        points_attention = await _generer_points_attention(
            request.type_acte,
            request.elements
        )

        # Suggérer les annexes requises
        annexes_requises = _generer_annexes_requises(
            request.type_acte,
            request.elements
        )

        # Structure suggérée pour l'acte
        structure_suggeree = _generer_structure_acte(request.type_acte)

        return AnalyseActeResponse(
            structure_suggeree=structure_suggeree,
            clauses_manquantes=clauses_manquantes,
            points_attention=points_attention,
            annexes_requises=annexes_requises,
            articles_loi=articles_loi
        )

    except Exception as e:
        logger.error(f"Erreur lors de l'analyse d'acte: {str(e)}")
        raise


async def _identifier_clauses_manquantes(
    type_acte: TypeActe,
    elements: Dict[str, Any],
    clauses_requises: List[str]
) -> List[str]:
    """Identifie les clauses manquantes"""
    manquantes = []

    if type_acte == TypeActe.VENTE:
        if "prix" not in elements or not elements.get("prix"):
            manquantes.append("Prix de vente non spécifié")
        if "bien" not in elements:
            manquantes.append("Description du bien manquante")
        if "diagnostics" not in elements:
            manquantes.append("Diagnostics immobiliers obligatoires")
        if "origine" not in elements:
            manquantes.append("Origine de propriété à préciser")

    elif type_acte == TypeActe.SUCCESSION:
        if "defunt" not in elements:
            manquantes.append("Identification du défunt incomplète")
        if "heritiers" not in elements:
            manquantes.append("Liste des héritiers manquante")
        if "actif" not in elements:
            manquantes.append("Inventaire de l'actif successoral")

    elif type_acte == TypeActe.DONATION:
        if "donateur" not in elements:
            manquantes.append("Identification du donateur")
        if "donataire" not in elements:
            manquantes.append("Identification du donataire")
        if "bien_donne" not in elements:
            manquantes.append("Description des biens donnés")

    return manquantes


async def _rechercher_articles_applicables(
    type_acte: TypeActe,
    elements: Dict[str, Any]
) -> List[str]:
    """Recherche les articles de loi via RAG"""
    try:
        rag = get_notaire_rag()

        # Construire une requête selon le type d'acte
        if type_acte == TypeActe.VENTE:
            query = "vente immobilière obligations vendeur articles code civil"
        elif type_acte == TypeActe.SUCCESSION:
            query = "succession héritiers partage droits articles code civil"
        elif type_acte == TypeActe.DONATION:
            query = "donation entre vifs conditions articles code civil"
        else:
            query = f"acte {type_acte} articles applicables"

        # Effectuer la recherche
        chunks = await rag.search(query, source_type="loi", k=3)

        # Extraire les sources
        articles = [chunk.source for chunk in chunks if chunk.similarity > 0.7]

        return articles[:5]  # Limiter à 5 articles les plus pertinents

    except Exception as e:
        logger.error(f"Erreur recherche articles: {str(e)}")
        return []


async def _generer_points_attention(
    type_acte: TypeActe,
    elements: Dict[str, Any]
) -> List[str]:
    """Génère des points d'attention spécifiques"""
    points = []

    if type_acte == TypeActe.VENTE:
        if elements.get("financement") == "credit":
            points.append("Vente avec crédit : prévoir conditions suspensives")
        if elements.get("bien", {}).get("type") == "ancien":
            points.append("Bien ancien : diagnostics renforcés requis")

    elif type_acte == TypeActe.SUCCESSION:
        if len(elements.get("heritiers", [])) > 3:
            points.append("Succession complexe : envisager indivision temporaire")
        if elements.get("actif", {}).get("total", 0) > 1000000:
            points.append("Patrimoine important : optimisation fiscale recommandée")

    return points


def _generer_annexes_requises(
    type_acte: TypeActe,
    elements: Dict[str, Any]
) -> List[str]:
    """Génère la liste des annexes requises"""
    annexes = []

    if type_acte == TypeActe.VENTE:
        annexes.extend([
            "Titre de propriété",
            "Diagnostics immobiliers",
            "Règlement de copropriété",
            "État hypothécaire"
        ])

    elif type_acte == TypeActe.SUCCESSION:
        annexes.extend([
            "Acte de décès",
            "Livret de famille",
            "Dernières déclarations fiscales",
            "Relevés bancaires"
        ])

    return annexes


def _generer_structure_acte(type_acte: TypeActe) -> List[str]:
    """Génère la structure recommandée pour l'acte"""
    if type_acte == TypeActe.VENTE:
        return [
            "En-tête notarial",
            "Comparution des parties",
            "Objet de la vente",
            "Description du bien",
            "Prix et modalités",
            "Origine de propriété",
            "Charges et servitudes",
            "Conditions suspensives",
            "Remise des clés",
            "Publications et formalités"
        ]
    elif type_acte == TypeActe.SUCCESSION:
        return [
            "Décès et ouverture de succession",
            "Qualité des héritiers",
            "Inventaire des biens",
            "Évaluation patrimoine",
            "Calcul droits succession",
            "Partage des biens",
            "Lots attribués",
            "Soultes éventuelles"
        ]
    else:
        return ["Structure standard", "À définir selon l'acte"]


async def rediger_acte_stream(
    request: RedigerActeRequest,
    user_id: str
) -> AsyncIterator[str]:
    """
    Rédige un acte en streaming

    Args:
        request: Requête de rédaction
        user_id: ID utilisateur

    Yields:
        Chunks de texte de l'acte
    """
    try:
        # Construire le prompt de rédaction
        prompt = _construire_prompt_redaction(request)

        # Obtenir le provider IA
        ai_provider = get_ai_provider()

        # Messages pour l'IA
        messages = [{"role": "user", "content": prompt}]
        system_prompt = f"""Tu es un notaire expert. Rédige un acte {request.type_acte} en style {request.style}.
        Utilise un français juridique précis et inclus tous les éléments obligatoires.
        Marque les zones à compléter par [À COMPLÉTER : description]."""

        # Stream de génération
        async for chunk in ai_provider.stream(messages, system_prompt=system_prompt):
            # Formater en SSE
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

    except Exception as e:
        logger.error(f"Erreur lors de la rédaction: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def _construire_prompt_redaction(request: RedigerActeRequest) -> str:
    """Construit le prompt de rédaction selon le type d'acte"""
    elements_json = json.dumps(request.elements, indent=2)

    base_prompt = f"""
Rédige un acte notarial de type {request.type_acte} en style {request.style}.

Éléments fournis :
{elements_json}

Instructions :
- Respecte la structure juridique française
- Inclus toutes les mentions obligatoires
- Utilise un style {'formel et traditionnel' if request.style == 'formel' else 'clair et accessible'}
- Marque les zones nécessitant complétion : [À COMPLÉTER : description]
"""

    return base_prompt


async def relire_acte(request: RelireActeRequest, db: AsyncSession) -> RelectureActeResponse:
    """
    Effectue une relecture critique d'un acte

    Args:
        request: Requête de relecture
        db: Session base de données

    Returns:
        Analyse critique complète
    """
    try:
        # Analyser le contenu via IA
        ai_provider = get_ai_provider()

        prompt = f"""
Analyse ce {request.type_acte} et fournis une évaluation critique complète.

Contenu de l'acte :
{request.contenu_acte}

Fournis ta réponse en JSON avec cette structure exacte :
{{
    "score_completude": <nombre entre 0 et 100>,
    "corrections": [
        {{"type": "grammaire|juridique|forme", "message": "description", "ligne": <numéro>, "suggestion": "texte corrigé"}}
    ],
    "risques_juridiques": [
        {{"niveau": "faible|moyen|élevé", "description": "...", "consequence": "...", "solution": "..."}}
    ],
    "clauses_manquantes": ["liste des clauses importantes manquantes"]
}}
"""

        messages = [{"role": "user", "content": prompt}]
        system_prompt = "Tu es un notaire expert en relecture d'actes. Fournis uniquement du JSON valide."

        response = await ai_provider.complete(messages, system_prompt=system_prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Parser la réponse JSON
        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback si JSON invalide
            analysis = {
                "score_completude": 50,
                "corrections": [],
                "risques_juridiques": [],
                "clauses_manquantes": ["Analyse automatique indisponible"]
            }

        # Construire la réponse structurée
        corrections = [
            CorrectionActe(
                ligne=corr.get("ligne"),
                type=corr.get("type", "juridique"),
                message=corr.get("message", ""),
                suggestion=corr.get("suggestion")
            ) for corr in analysis.get("corrections", [])
        ]

        risques = [
            RisqueJuridique(
                niveau=risque.get("niveau", "moyen"),
                description=risque.get("description", ""),
                consequence=risque.get("consequence", ""),
                solution=risque.get("solution")
            ) for risque in analysis.get("risques_juridiques", [])
        ]

        return RelectureActeResponse(
            score_completude=analysis.get("score_completude", 50),
            corrections=corrections,
            risques_juridiques=risques,
            clauses_manquantes=analysis.get("clauses_manquantes", [])
        )

    except Exception as e:
        logger.error(f"Erreur lors de la relecture: {str(e)}")
        raise