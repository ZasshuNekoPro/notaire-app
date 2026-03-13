"""
Service d'extraction automatique des successions par IA.
Upload de documents → extraction structurée → création automatique.
"""
import json
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.succession import (
    Succession, Heritier, ActifSuccessoral, PassifSuccessoral,
    LienParente, TypeActif, TypePassif, StatutSuccession
)
from src.schemas.succession import (
    SuccessionCreate, HeritierCreate, ActifSuccessoralCreate, PassifSuccessoralCreate,
    ExtractionDocumentRequest, ExtractionDocumentResponse
)
from src.services.calcul_succession import mettre_a_jour_calculs_succession


logger = logging.getLogger(__name__)


# === Prompts IA pour extraction === #

PROMPT_EXTRACTION_SUCCESSION = """
Tu es un expert notaire analysant des documents de succession.

Extrais de ces documents les informations suivantes au format JSON strict :

{
  "succession": {
    "defunt_nom": "string",
    "defunt_prenom": "string",
    "defunt_date_naissance": "YYYY-MM-DD ou null",
    "defunt_date_deces": "YYYY-MM-DD ou null",
    "lieu_deces": "string ou null"
  },
  "heritiers": [
    {
      "nom": "string",
      "prenom": "string",
      "lien_parente": "conjoint|enfant|petit_enfant|parent|frere_soeur|neveu_niece|autre",
      "quote_part_legale": 0.5
    }
  ],
  "actifs": [
    {
      "type_actif": "immobilier|financier|mobilier|professionnel|autre",
      "description": "string",
      "valeur_estimee": 350000.00,
      "adresse": "string ou null pour immobilier"
    }
  ],
  "passifs": [
    {
      "type_passif": "credit_immobilier|credit_consommation|dette_fiscale|frais_funeraires|autre",
      "description": "string",
      "montant": 120000.00,
      "creancier": "string ou null"
    }
  ],
  "confiance": {
    "succession": 0.95,
    "heritiers": 0.80,
    "actifs": 0.75,
    "passifs": 0.60,
    "globale": 0.78
  },
  "alertes": [
    "Information manquante : date de naissance du défunt",
    "Valeur estimative pour le bien immobilier"
  ]
}

RÈGLES CRITIQUES :
1. quote_part_legale = somme doit faire exactement 1.0
2. lien_parente doit être un des types exacts listés
3. Toutes les valeurs numériques en decimal sans €
4. Si information manquante → null, pas de chaîne vide
5. confiance entre 0.0 et 1.0 pour chaque section
6. Documenter toute incertitude dans alertes[]

Analyse maintenant ces documents :
"""

PROMPT_ESTIMATION_IMMOBILIER = """
À partir de cette description de bien immobilier :
- Type : {type_bien}
- Description : {description}
- Adresse : {adresse}
- Surface : {surface} m²

Estime la valeur marchande et fournis le JSON :
{
  "valeur_estimee": 350000.00,
  "confiance_estimation": 0.65,
  "methode": "comparaison_marche",
  "facteurs": [
    "Localisation prisée",
    "Surface correcte",
    "État à rénover"
  ],
  "fourchette_basse": 320000.00,
  "fourchette_haute": 380000.00
}

Sois conservateur dans tes estimations.
"""


# === Fonctions utilitaires === #

def valider_quotes_parts(heritiers: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Valide que les quotes-parts font exactement 1.0.

    Returns:
        Tuple (est_valide, liste_erreurs)
    """
    erreurs = []

    if not heritiers:
        erreurs.append("Aucun héritier trouvé")
        return False, erreurs

    total_quotes = sum(Decimal(str(h.get("quote_part_legale", 0))) for h in heritiers)

    if abs(total_quotes - Decimal("1.0")) > Decimal("0.01"):
        erreurs.append(f"Quotes-parts totales = {total_quotes}, attendu = 1.0")
        return False, erreurs

    return True, erreurs


def normaliser_lien_parente(lien_brut: str) -> Optional[LienParente]:
    """
    Normalise un lien de parenté extrait par l'IA.
    """
    mapping = {
        "conjoint": LienParente.CONJOINT,
        "époux": LienParente.CONJOINT,
        "épouse": LienParente.CONJOINT,
        "mari": LienParente.CONJOINT,
        "femme": LienParente.CONJOINT,
        "enfant": LienParente.ENFANT,
        "fils": LienParente.ENFANT,
        "fille": LienParente.ENFANT,
        "petit_enfant": LienParente.PETIT_ENFANT,
        "petit-enfant": LienParente.PETIT_ENFANT,
        "petite_fille": LienParente.PETIT_ENFANT,
        "petit_fils": LienParente.PETIT_ENFANT,
        "parent": LienParente.PARENT,
        "père": LienParente.PARENT,
        "mère": LienParente.PARENT,
        "frere_soeur": LienParente.FRERE_SOEUR,
        "frère": LienParente.FRERE_SOEUR,
        "sœur": LienParente.FRERE_SOEUR,
        "neveu_niece": LienParente.NEVEU_NIECE,
        "neveu": LienParente.NEVEU_NIECE,
        "nièce": LienParente.NEVEU_NIECE,
    }

    lien_lower = lien_brut.lower().strip()
    return mapping.get(lien_lower, LienParente.AUTRE)


def normaliser_type_actif(type_brut: str) -> TypeActif:
    """
    Normalise un type d'actif extrait par l'IA.
    """
    mapping = {
        "immobilier": TypeActif.IMMOBILIER,
        "bien_immobilier": TypeActif.IMMOBILIER,
        "maison": TypeActif.IMMOBILIER,
        "appartement": TypeActif.IMMOBILIER,
        "terrain": TypeActif.IMMOBILIER,
        "financier": TypeActif.FINANCIER,
        "compte": TypeActif.FINANCIER,
        "épargne": TypeActif.FINANCIER,
        "assurance_vie": TypeActif.FINANCIER,
        "livret": TypeActif.FINANCIER,
        "mobilier": TypeActif.MOBILIER,
        "véhicule": TypeActif.MOBILIER,
        "bijoux": TypeActif.MOBILIER,
        "professionnel": TypeActif.PROFESSIONNEL,
        "fonds_commerce": TypeActif.PROFESSIONNEL,
        "parts_sociales": TypeActif.PROFESSIONNEL,
    }

    type_lower = type_brut.lower().strip()
    return mapping.get(type_lower, TypeActif.AUTRE)


def normaliser_type_passif(type_brut: str) -> TypePassif:
    """
    Normalise un type de passif extrait par l'IA.
    """
    mapping = {
        "credit_immobilier": TypePassif.CREDIT_IMMOBILIER,
        "crédit_immobilier": TypePassif.CREDIT_IMMOBILIER,
        "emprunt_immobilier": TypePassif.CREDIT_IMMOBILIER,
        "credit_consommation": TypePassif.CREDIT_CONSOMMATION,
        "crédit_consommation": TypePassif.CREDIT_CONSOMMATION,
        "prêt_personnel": TypePassif.CREDIT_CONSOMMATION,
        "dette_fiscale": TypePassif.DETTE_FISCALE,
        "impots": TypePassif.DETTE_FISCALE,
        "impôts": TypePassif.DETTE_FISCALE,
        "frais_funeraires": TypePassif.FRAIS_FUNERAIRES,
        "frais_funéraires": TypePassif.FRAIS_FUNERAIRES,
        "obsèques": TypePassif.FRAIS_FUNERAIRES,
    }

    type_lower = type_brut.lower().strip()
    return mapping.get(type_lower, TypePassif.AUTRE)


# === Service principal === #

async def extraire_succession_documents(
    request: ExtractionDocumentRequest,
    db: AsyncSession
) -> ExtractionDocumentResponse:
    """
    Extrait une succession à partir de documents uploadés.

    Args:
        request: Requête avec documents et paramètres
        db: Session de base de données

    Returns:
        Réponse avec succession extraite et métadonnées
    """
    try:
        # TODO: Intégration avec ai-core pour l'extraction
        # Pour l'instant, simulation avec des données de test

        logger.info(f"Extraction de {len(request.documents)} documents")

        # === Simulation extraction IA === #
        # En production, ceci appellerait get_ai_provider() du ai-core
        donnees_extraites = await _simuler_extraction_ia(request.documents)

        # === Validation et normalisation === #
        succession_data, confiance, alertes = await _valider_donnees_extraites(donnees_extraites)

        # === Estimation DVF automatique pour l'immobilier === #
        for actif in succession_data.actifs:
            if actif.type_actif == TypeActif.IMMOBILIER and actif.adresse:
                estimation_dvf = await _estimer_bien_dvf(actif)
                # Note: estimation_dvf sera stockée dans actif.estimation_dvf (JSONB)

        # === Création automatique si confiance >= seuil === #
        succession_creee = None
        if request.auto_creation and confiance >= request.seuil_confiance:
            succession_creee = await _creer_succession_auto(succession_data, db)
            alertes.append(f"Succession créée automatiquement (confiance {confiance:.2f})")

        necessite_validation = confiance < request.seuil_confiance or len(alertes) > 2

        return ExtractionDocumentResponse(
            confiance_globale=confiance,
            succession_extraite=succession_data,
            alertes=alertes,
            suggestions=_generer_suggestions(donnees_extraites, confiance),
            necessite_validation=necessite_validation,
            succession_creee=succession_creee
        )

    except Exception as e:
        logger.error(f"Erreur extraction succession: {e}")
        raise


async def _simuler_extraction_ia(documents: List[str]) -> Dict[str, Any]:
    """
    Simule l'extraction IA pour les tests.
    En production, remplacée par l'appel réel à l'IA.
    """
    # Données de simulation réalistes
    return {
        "succession": {
            "defunt_nom": "DUPONT",
            "defunt_prenom": "Pierre",
            "defunt_date_naissance": "1945-03-15",
            "defunt_date_deces": "2025-01-20",
            "lieu_deces": "Paris 15e"
        },
        "heritiers": [
            {
                "nom": "DUPONT",
                "prenom": "Marie",
                "lien_parente": "conjoint",
                "quote_part_legale": 0.5
            },
            {
                "nom": "DUPONT",
                "prenom": "Jean",
                "lien_parente": "enfant",
                "quote_part_legale": 0.25
            },
            {
                "nom": "DUPONT",
                "prenom": "Sophie",
                "lien_parente": "enfant",
                "quote_part_legale": 0.25
            }
        ],
        "actifs": [
            {
                "type_actif": "immobilier",
                "description": "Maison familiale avec jardin",
                "valeur_estimee": 350000.00,
                "adresse": "123 rue de la Paix, 75015 Paris"
            },
            {
                "type_actif": "financier",
                "description": "Compte épargne BNP Paribas",
                "valeur_estimee": 45000.00,
                "adresse": None
            }
        ],
        "passifs": [
            {
                "type_passif": "credit_immobilier",
                "description": "Crédit résidence principale",
                "montant": 120000.00,
                "creancier": "Crédit Agricole"
            }
        ],
        "confiance": {
            "succession": 0.95,
            "heritiers": 0.85,
            "actifs": 0.80,
            "passifs": 0.75,
            "globale": 0.84
        },
        "alertes": [
            "Valeur immobilier estimative, vérification notaire recommandée"
        ]
    }


async def _valider_donnees_extraites(
    donnees: Dict[str, Any]
) -> Tuple[SuccessionCreate, float, List[str]]:
    """
    Valide et normalise les données extraites par l'IA.
    """
    alertes = list(donnees.get("alertes", []))

    # === Validation des quotes-parts === #
    heritiers_bruts = donnees.get("heritiers", [])
    quotes_valides, erreurs_quotes = valider_quotes_parts(heritiers_bruts)
    if not quotes_valides:
        alertes.extend(erreurs_quotes)

    # === Construction des objets Pydantic === #
    succession_base = donnees.get("succession", {})

    heritiers = []
    for h in heritiers_bruts:
        lien_normalise = normaliser_lien_parente(h.get("lien_parente", ""))
        heritier = HeritierCreate(
            nom=h.get("nom", ""),
            prenom=h.get("prenom", ""),
            lien_parente=lien_normalise,
            quote_part_legale=Decimal(str(h.get("quote_part_legale", 0)))
        )
        heritiers.append(heritier)

    actifs = []
    for a in donnees.get("actifs", []):
        type_normalise = normaliser_type_actif(a.get("type_actif", ""))
        actif = ActifSuccessoralCreate(
            type_actif=type_normalise,
            description=a.get("description", ""),
            valeur_estimee=Decimal(str(a.get("valeur_estimee", 0))),
            adresse=a.get("adresse")
        )
        actifs.append(actif)

    passifs = []
    for p in donnees.get("passifs", []):
        type_normalise = normaliser_type_passif(p.get("type_passif", ""))
        passif = PassifSuccessoralCreate(
            type_passif=type_normalise,
            description=p.get("description", ""),
            montant=Decimal(str(p.get("montant", 0))),
            creancier=p.get("creancier")
        )
        passifs.append(passif)

    # === Génération du numéro de dossier === #
    numero_dossier = f"2025-SUC-{uuid4().hex[:8].upper()}"

    succession_create = SuccessionCreate(
        numero_dossier=numero_dossier,
        defunt_nom=succession_base.get("defunt_nom", ""),
        defunt_prenom=succession_base.get("defunt_prenom", ""),
        defunt_date_naissance=succession_base.get("defunt_date_naissance"),
        defunt_date_deces=succession_base.get("defunt_date_deces"),
        lieu_deces=succession_base.get("lieu_deces"),
        heritiers=heritiers,
        actifs=actifs,
        passifs=passifs
    )

    confiance = donnees.get("confiance", {}).get("globale", 0.5)

    return succession_create, confiance, alertes


async def _estimer_bien_dvf(actif: ActifSuccessoralCreate) -> Dict[str, Any]:
    """
    Estime un bien immobilier via l'API DVF.
    En production, ceci appellerait le service d'estimation existant.
    """
    # Simulation d'estimation DVF
    return {
        "valeur_dvf": float(actif.valeur_estimee * Decimal("0.95")),
        "confiance_dvf": 0.75,
        "comparables_trouves": 12,
        "date_estimation": "2025-03-12"
    }


async def _creer_succession_auto(
    succession_data: SuccessionCreate,
    db: AsyncSession
) -> Optional[Dict]:
    """
    Crée automatiquement la succession en base de données.
    """
    try:
        # === Création succession === #
        succession = Succession(
            numero_dossier=succession_data.numero_dossier,
            defunt_nom=succession_data.defunt_nom,
            defunt_prenom=succession_data.defunt_prenom,
            defunt_date_naissance=succession_data.defunt_date_naissance,
            defunt_date_deces=succession_data.defunt_date_deces,
            lieu_deces=succession_data.lieu_deces,
            statut=StatutSuccession.EN_COURS,
            extraction_metadata={"auto_created": True, "date": "2025-03-12"}
        )

        db.add(succession)
        await db.flush()  # Pour récupérer l'ID

        # === Création héritiers === #
        for h_data in succession_data.heritiers:
            heritier = Heritier(
                succession_id=succession.id,
                nom=h_data.nom,
                prenom=h_data.prenom,
                lien_parente=h_data.lien_parente,
                quote_part_legale=h_data.quote_part_legale,
                adresse=h_data.adresse,
                email=h_data.email,
                telephone=h_data.telephone
            )
            db.add(heritier)

        # === Création actifs === #
        for a_data in succession_data.actifs:
            actif = ActifSuccessoral(
                succession_id=succession.id,
                type_actif=a_data.type_actif,
                description=a_data.description,
                valeur_estimee=a_data.valeur_estimee,
                adresse=a_data.adresse,
                surface=a_data.surface
            )
            db.add(actif)

        # === Création passifs === #
        for p_data in succession_data.passifs:
            passif = PassifSuccessoral(
                succession_id=succession.id,
                type_passif=p_data.type_passif,
                description=p_data.description,
                montant=p_data.montant,
                creancier=p_data.creancier,
                date_echeance=p_data.date_echeance
            )
            db.add(passif)

        await db.commit()

        # === Calculs fiscaux automatiques === #
        await mettre_a_jour_calculs_succession(succession.id, db)

        logger.info(f"Succession {succession.numero_dossier} créée automatiquement")

        return {
            "id": succession.id,
            "numero_dossier": succession.numero_dossier,
            "statut": "creee_automatiquement"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Erreur création succession auto: {e}")
        raise


def _generer_suggestions(donnees: Dict[str, Any], confiance: float) -> List[str]:
    """
    Génère des suggestions d'amélioration basées sur l'extraction.
    """
    suggestions = []

    if confiance < 0.8:
        suggestions.append("Vérifier les informations extraites avec les documents originaux")

    if not donnees.get("succession", {}).get("defunt_date_naissance"):
        suggestions.append("Ajouter la date de naissance du défunt si disponible")

    actifs = donnees.get("actifs", [])
    immobiliers = [a for a in actifs if a.get("type_actif") == "immobilier"]

    if immobiliers:
        suggestions.append("Vérifier les estimations immobilières par expertise notariale")

    if len(donnees.get("heritiers", [])) > 3:
        suggestions.append("Succession complexe : validation juridique recommandée")

    return suggestions