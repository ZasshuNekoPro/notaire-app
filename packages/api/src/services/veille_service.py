"""
Service de veille automatique pour le domaine notarial.
Surveillance DVF, Légifrance, BOFIP avec notifications intelligentes.
"""
import logging
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.veille import (
    VeilleRule, Alerte, HistoriqueVeille,
    TypeSource, NiveauImpact, StatutAlerte
)
from src.models.dossiers import Dossier
from src.database import get_db


logger = logging.getLogger(__name__)


class VeilleEngine:
    """
    Moteur de veille automatique pour détecter les changements
    impactants les dossiers notariaux.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.client = httpx.AsyncClient()

    async def verifier_variations_dvf(self, code_postal: str) -> List[Alerte]:
        """
        Comparer prix_m2_median sur 30j vs 60j.
        Si variation > 5% : créer Alerte impact='fort'.
        Trouver tous les dossiers avec biens dans ce code_postal.

        Args:
            code_postal: Code postal à surveiller

        Returns:
            Liste des alertes créées
        """
        alertes_creees = []

        try:
            logger.info(f"Vérification variations DVF pour {code_postal}")

            # TODO: Intégration avec le service DVF existant
            # Pour l'instant, simulation avec données de test
            variation_pct = await self._simuler_variation_dvf(code_postal)

            # Seuil de déclenchement : 5%
            if abs(variation_pct) > 5:
                # Rechercher les dossiers potentiellement impactés
                dossiers_impactes = await self._trouver_dossiers_par_code_postal(code_postal)

                # Niveau d'impact selon l'amplitude
                if abs(variation_pct) > 10:
                    niveau = NiveauImpact.FORT
                elif abs(variation_pct) > 8:
                    niveau = NiveauImpact.MOYEN
                else:
                    niveau = NiveauImpact.FAIBLE

                # Récupérer la règle de veille DVF pour ce code postal
                veille_rule = await self._get_veille_rule_dvf(code_postal)
                if not veille_rule:
                    logger.warning(f"Aucune règle DVF pour {code_postal}")
                    return alertes_creees

                # Créer l'alerte
                alerte = Alerte(
                    veille_rule_id=veille_rule.id,
                    titre=f"Variation DVF importante {code_postal}",
                    niveau_impact=niveau,
                    contenu=f"Variation de {variation_pct:+.1f}% des prix immobiliers "
                           f"sur 30 jours dans {code_postal}. "
                           f"{len(dossiers_impactes)} dossier(s) potentiellement impacté(s).",
                    details_techniques={
                        "code_postal": code_postal,
                        "variation_pct": variation_pct,
                        "periode": "30j vs 60j",
                        "dossiers_count": len(dossiers_impactes)
                    },
                    dossiers_impactes=[str(d.id) for d in dossiers_impactes],
                    url_source=f"https://app.dvf.etalab.gouv.fr/?code_postal={code_postal}"
                )

                self.db.add(alerte)
                alertes_creees.append(alerte)

                logger.info(f"Alerte DVF créée: {variation_pct:+.1f}% à {code_postal}")

        except Exception as e:
            logger.error(f"Erreur vérification DVF {code_postal}: {e}")

        return alertes_creees

    async def verifier_legifrance(self) -> List[Alerte]:
        """
        Articles surveillés : 720-892 Code civil, 777-800 CGI.
        Comparer version stockée vs API Légifrance.
        Si différence : créer Alerte impact='critique'.

        Returns:
            Liste des alertes créées
        """
        alertes_creees = []

        try:
            logger.info("Vérification changements Légifrance")

            # Articles critiques pour le notariat
            articles_surveilles = [
                ("Code civil", "720"),    # Ouverture succession
                ("Code civil", "892"),    # Fin successions
                ("CGI", "777"),          # Droits de succession
                ("CGI", "800"),          # Exonérations
                ("Code civil", "1100"),  # Donations
            ]

            for code_source, numero_article in articles_surveilles:
                changement_detecte = await self._verifier_article_legifrance(
                    code_source, numero_article
                )

                if changement_detecte:
                    # Récupérer la règle de veille Légifrance
                    veille_rule = await self._get_veille_rule_legifrance()
                    if not veille_rule:
                        continue

                    # Créer alerte critique
                    alerte = Alerte(
                        veille_rule_id=veille_rule.id,
                        titre=f"Modification {code_source} art. {numero_article}",
                        niveau_impact=NiveauImpact.CRITIQUE,
                        contenu=f"L'article {numero_article} du {code_source} "
                               f"a été modifié. Vérification juridique recommandée "
                               f"pour tous les dossiers en cours.",
                        details_techniques={
                            "code_source": code_source,
                            "article": numero_article,
                            "date_detection": datetime.now().isoformat(),
                            "type_changement": "modification_texte"
                        },
                        url_source=f"https://www.legifrance.gouv.fr/codes/article_lc/{code_source.lower().replace(' ', '_')}/{numero_article}"
                    )

                    self.db.add(alerte)
                    alertes_creees.append(alerte)

                    logger.warning(f"Alerte Légifrance: {code_source} art. {numero_article}")

        except Exception as e:
            logger.error(f"Erreur vérification Légifrance: {e}")

        return alertes_creees

    async def verifier_bofip(self) -> List[Alerte]:
        """
        Surveiller pages barèmes succession.
        Détecter changements de taux ou abattements.
        Alerte impact='critique' si modification.

        Returns:
            Liste des alertes créées
        """
        alertes_creees = []

        try:
            logger.info("Vérification changements BOFIP")

            # Pages BOFIP critiques pour les successions
            pages_surveillees = [
                "ENR-Mutations-10-20-20",  # Barèmes droits succession
                "ENR-Mutations-10-40-10",  # Abattements succession
                "ENR-Mutations-10-40-20",  # Exonérations conjoint
            ]

            for page_bofip in pages_surveillees:
                changement_detecte = await self._verifier_page_bofip(page_bofip)

                if changement_detecte:
                    veille_rule = await self._get_veille_rule_bofip()
                    if not veille_rule:
                        continue

                    alerte = Alerte(
                        veille_rule_id=veille_rule.id,
                        titre=f"Modification BOFIP {page_bofip}",
                        niveau_impact=NiveauImpact.CRITIQUE,
                        contenu=f"La page BOFIP {page_bofip} a été modifiée. "
                               f"Possible changement de barèmes ou abattements successoraux. "
                               f"Vérification urgente requise.",
                        details_techniques={
                            "page_bofip": page_bofip,
                            "date_detection": datetime.now().isoformat(),
                            "type_surveillance": "bareme_succession"
                        },
                        url_source=f"https://bofip.impots.gouv.fr/bofip/{page_bofip}"
                    )

                    self.db.add(alerte)
                    alertes_creees.append(alerte)

                    logger.critical(f"Alerte BOFIP critique: {page_bofip}")

        except Exception as e:
            logger.error(f"Erreur vérification BOFIP: {e}")

        return alertes_creees

    async def analyser_impact_sur_dossier(
        self,
        alerte: Alerte,
        dossier: Dossier
    ) -> str:
        """
        Prompt LLM : "Cette modification [alerte.contenu] impacte
        le dossier [résumé dossier] de la façon suivante..."
        Retourne explication en 2-3 phrases.

        Args:
            alerte: Alerte à analyser
            dossier: Dossier potentiellement impacté

        Returns:
            Analyse d'impact en langage naturel
        """
        try:
            # TODO: Intégration avec ai-core pour analyse IA
            # Pour l'instant, simulation avec logique métier

            resume_dossier = f"Dossier {dossier.numero} ({dossier.type_acte})"

            if alerte.veille_rule.type_source == TypeSource.DVF:
                return f"Cette variation immobilière peut impacter l'estimation " \
                       f"des biens du {resume_dossier}. Une réévaluation des " \
                       f"prix de référence est recommandée."

            elif alerte.veille_rule.type_source == TypeSource.LEGIFRANCE:
                return f"Cette modification légale peut affecter les dispositions " \
                       f"juridiques du {resume_dossier}. Une révision par le " \
                       f"notaire est nécessaire pour vérifier la conformité."

            elif alerte.veille_rule.type_source == TypeSource.BOFIP:
                return f"Ce changement fiscal peut modifier les calculs de droits " \
                       f"pour le {resume_dossier}. Un recalcul des obligations " \
                       f"fiscales est requis."

            else:
                return f"Cette alerte nécessite une analyse spécifique pour " \
                       f"déterminer l'impact sur le {resume_dossier}."

        except Exception as e:
            logger.error(f"Erreur analyse impact: {e}")
            return "Erreur lors de l'analyse d'impact. Vérification manuelle requise."

    async def executer_verification_complete(self) -> Dict[str, Any]:
        """
        Execute toutes les vérifications de veille activées.

        Returns:
            Rapport d'exécution avec statistiques
        """
        debut = datetime.now()
        rapport = {
            "debut": debut.isoformat(),
            "sources_verifiees": [],
            "alertes_creees": 0,
            "erreurs": [],
            "duree_ms": 0
        }

        try:
            # Récupérer toutes les règles de veille activées
            query = select(VeilleRule).where(VeilleRule.active == True)
            result = await self.db.execute(query)
            regles_actives = result.scalars().all()

            logger.info(f"Exécution veille: {len(regles_actives)} règles actives")

            for regle in regles_actives:
                try:
                    alertes = []

                    if regle.type_source == TypeSource.DVF:
                        code_postal = regle.configuration.get("code_postal")
                        if code_postal:
                            alertes = await self.verifier_variations_dvf(code_postal)

                    elif regle.type_source == TypeSource.LEGIFRANCE:
                        alertes = await self.verifier_legifrance()

                    elif regle.type_source == TypeSource.BOFIP:
                        alertes = await self.verifier_bofip()

                    # Mettre à jour la règle
                    regle.derniere_verification = datetime.now()

                    # Enregistrer l'historique
                    historique = HistoriqueVeille(
                        veille_rule_id=regle.id,
                        date_verification=datetime.now(),
                        duree_ms=100,  # Simulation
                        succes=True,
                        elements_verifies=1,
                        alertes_creees=len(alertes)
                    )
                    self.db.add(historique)

                    rapport["alertes_creees"] += len(alertes)
                    rapport["sources_verifiees"].append(regle.type_source.value)

                except Exception as e:
                    logger.error(f"Erreur règle {regle.id}: {e}")
                    rapport["erreurs"].append(f"Règle {regle.nom}: {e}")

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur exécution veille: {e}")
            rapport["erreurs"].append(f"Erreur globale: {e}")

        finally:
            fin = datetime.now()
            rapport["fin"] = fin.isoformat()
            rapport["duree_ms"] = int((fin - debut).total_seconds() * 1000)

        return rapport

    # === Méthodes privées === #

    async def _simuler_variation_dvf(self, code_postal: str) -> float:
        """Simule une variation DVF pour les tests."""
        # Simulation de données DVF
        variations_simulees = {
            "75001": +6.2,  # Augmentation forte
            "75015": +3.1,  # Augmentation faible
            "93200": -2.8,  # Baisse faible
            "92100": +12.5, # Augmentation très forte
        }
        return variations_simulees.get(code_postal, +1.2)

    async def _trouver_dossiers_par_code_postal(self, code_postal: str) -> List[Dossier]:
        """Trouve les dossiers avec biens dans un code postal."""
        # TODO: Requête complexe sur actifs immobiliers
        # Pour l'instant, retour simulation
        query = select(Dossier).limit(3)  # Simulation
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _verifier_article_legifrance(self, code: str, article: str) -> bool:
        """Vérifie si un article Légifrance a changé."""
        # Simulation de détection de changement
        return False  # Pas de changement pour la démo

    async def _verifier_page_bofip(self, page: str) -> bool:
        """Vérifie si une page BOFIP a changé."""
        # Simulation de détection de changement
        return False  # Pas de changement pour la démo

    async def _get_veille_rule_dvf(self, code_postal: str) -> Optional[VeilleRule]:
        """Récupère la règle DVF pour un code postal."""
        query = select(VeilleRule).where(
            and_(
                VeilleRule.type_source == TypeSource.DVF,
                VeilleRule.code_postal == code_postal,
                VeilleRule.active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_veille_rule_legifrance(self) -> Optional[VeilleRule]:
        """Récupère la règle Légifrance active."""
        query = select(VeilleRule).where(
            and_(
                VeilleRule.type_source == TypeSource.LEGIFRANCE,
                VeilleRule.active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_veille_rule_bofip(self) -> Optional[VeilleRule]:
        """Récupère la règle BOFIP active."""
        query = select(VeilleRule).where(
            and_(
                VeilleRule.type_source == TypeSource.BOFIP,
                VeilleRule.active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


# === Factory et utilitaires === #

async def creer_veille_engine() -> VeilleEngine:
    """Factory pour créer une instance du moteur de veille."""
    async with get_db() as db:
        return VeilleEngine(db)


async def creer_regle_veille_dvf(
    nom: str,
    code_postal: str,
    db: AsyncSession,
    dossier_id: Optional[UUID] = None
) -> VeilleRule:
    """
    Crée une règle de veille DVF pour un code postal.

    Args:
        nom: Nom de la règle
        code_postal: Code postal à surveiller
        db: Session DB
        dossier_id: Dossier spécifique (optionnel)

    Returns:
        Règle créée
    """
    regle = VeilleRule(
        nom=nom,
        description=f"Surveillance variations immobilières {code_postal}",
        type_source=TypeSource.DVF,
        configuration={
            "code_postal": code_postal,
            "seuil_variation_pct": 5.0,
            "periode_comparaison_jours": 30
        },
        code_postal=code_postal,
        active=True,
        frequence_heures=168,  # Une fois par semaine
        dossier_id=dossier_id
    )

    db.add(regle)
    await db.flush()
    return regle


async def creer_regle_veille_legifrance(
    nom: str,
    articles_codes: List[str],
    db: AsyncSession
) -> VeilleRule:
    """
    Crée une règle de veille Légifrance.

    Args:
        nom: Nom de la règle
        articles_codes: Articles à surveiller
        db: Session DB

    Returns:
        Règle créée
    """
    regle = VeilleRule(
        nom=nom,
        description=f"Surveillance articles {', '.join(articles_codes)}",
        type_source=TypeSource.LEGIFRANCE,
        configuration={
            "articles_surveilles": articles_codes,
            "verification_quotidienne": True
        },
        articles_codes=articles_codes,
        active=True,
        frequence_heures=24  # Tous les jours
    )

    db.add(regle)
    await db.flush()
    return regle