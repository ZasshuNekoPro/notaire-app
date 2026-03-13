"""
Scheduler APScheduler pour les tâches de veille automatique.
Configuration des vérifications périodiques DVF, Légifrance, BOFIP.
"""
import logging
from typing import Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from src.services.veille_service import VeilleEngine, creer_veille_engine
from src.database import get_db


logger = logging.getLogger(__name__)


class VeilleScheduler:
    """
    Gestionnaire des tâches de veille automatique avec APScheduler.
    Exécute les vérifications DVF, Légifrance, BOFIP selon planning.
    """

    def __init__(self):
        # Configuration APScheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 1,
            'misfire_grace_time': 300  # 5 minutes de tolérance
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Europe/Paris'
        )

        self._jobs_configures = False

    async def demarrer(self):
        """
        Démarre le scheduler et configure les tâches de veille.
        """
        try:
            if not self._jobs_configures:
                await self._configurer_jobs_veille()
                self._jobs_configures = True

            self.scheduler.start()
            logger.info("🕰️ Scheduler de veille démarré")

            # Log des prochaines exécutions
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                prochaine = job.next_run_time
                logger.info(f"  • {job.id}: prochaine exécution {prochaine}")

        except Exception as e:
            logger.error(f"Erreur démarrage scheduler veille: {e}")
            raise

    async def arreter(self):
        """
        Arrête le scheduler proprement.
        """
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("🛑 Scheduler de veille arrêté")
        except Exception as e:
            logger.error(f"Erreur arrêt scheduler: {e}")

    async def _configurer_jobs_veille(self):
        """
        Configure toutes les tâches de veille selon le planning requis.
        """
        logger.info("📅 Configuration des tâches de veille...")

        # 1. Vérification DVF : tous les lundis 8h00
        self.scheduler.add_job(
            self._job_verification_dvf,
            trigger=CronTrigger(
                day_of_week='mon',  # Lundi
                hour=8,
                minute=0,
                timezone='Europe/Paris'
            ),
            id='veille_dvf_hebdo',
            name='Vérification DVF hebdomadaire',
            replace_existing=True
        )

        # 2. Vérification Légifrance : tous les jours 7h00
        self.scheduler.add_job(
            self._job_verification_legifrance,
            trigger=CronTrigger(
                hour=7,
                minute=0,
                timezone='Europe/Paris'
            ),
            id='veille_legifrance_quotidien',
            name='Vérification Légifrance quotidienne',
            replace_existing=True
        )

        # 3. Vérification BOFIP : tous les jours 7h15
        self.scheduler.add_job(
            self._job_verification_bofip,
            trigger=CronTrigger(
                hour=7,
                minute=15,
                timezone='Europe/Paris'
            ),
            id='veille_bofip_quotidien',
            name='Vérification BOFIP quotidienne',
            replace_existing=True
        )

        # 4. Rapport de synthèse : tous les vendredi 18h00
        self.scheduler.add_job(
            self._job_rapport_synthese_hebdo,
            trigger=CronTrigger(
                day_of_week='fri',  # Vendredi
                hour=18,
                minute=0,
                timezone='Europe/Paris'
            ),
            id='rapport_veille_hebdo',
            name='Rapport de synthèse hebdomadaire',
            replace_existing=True
        )

        # 5. Nettoyage historique : premier du mois 2h00
        self.scheduler.add_job(
            self._job_nettoyage_historique,
            trigger=CronTrigger(
                day=1,  # Premier du mois
                hour=2,
                minute=0,
                timezone='Europe/Paris'
            ),
            id='nettoyage_historique_mensuel',
            name='Nettoyage historique mensuel',
            replace_existing=True
        )

        logger.info(f"✅ {len(self.scheduler.get_jobs())} tâches de veille configurées")

    async def _job_verification_dvf(self):
        """
        Tâche : Vérification des variations DVF pour tous les codes postaux surveillés.
        Programmée : Tous les lundis 8h00.
        """
        logger.info("🏠 Début vérification DVF hebdomadaire")

        try:
            async with get_db() as db:
                engine = VeilleEngine(db)

                # Récupérer tous les codes postaux surveillés
                codes_postaux = await self._get_codes_postaux_surveilles(db)

                total_alertes = 0
                for code_postal in codes_postaux:
                    try:
                        alertes = await engine.verifier_variations_dvf(code_postal)
                        total_alertes += len(alertes)

                        if alertes:
                            logger.info(f"  📍 {code_postal}: {len(alertes)} alerte(s)")

                    except Exception as e:
                        logger.error(f"Erreur DVF {code_postal}: {e}")

                await db.commit()

                logger.info(f"✅ Vérification DVF terminée: {total_alertes} alertes créées")

        except Exception as e:
            logger.error(f"Erreur job DVF: {e}")

    async def _job_verification_legifrance(self):
        """
        Tâche : Vérification des modifications d'articles Légifrance.
        Programmée : Tous les jours 7h00.
        """
        logger.info("⚖️ Début vérification Légifrance quotidienne")

        try:
            async with get_db() as db:
                engine = VeilleEngine(db)
                alertes = await engine.verifier_legifrance()

                if alertes:
                    logger.warning(f"🚨 {len(alertes)} modification(s) légale(s) détectée(s)")
                    for alerte in alertes:
                        logger.warning(f"  • {alerte.titre}")
                else:
                    logger.info("✅ Aucun changement Légifrance détecté")

                await db.commit()

        except Exception as e:
            logger.error(f"Erreur job Légifrance: {e}")

    async def _job_verification_bofip(self):
        """
        Tâche : Vérification des changements de barèmes BOFIP.
        Programmée : Tous les jours 7h15.
        """
        logger.info("💰 Début vérification BOFIP quotidienne")

        try:
            async with get_db() as db:
                engine = VeilleEngine(db)
                alertes = await engine.verifier_bofip()

                if alertes:
                    logger.critical(f"🚨 {len(alertes)} changement(s) fiscal(aux) détecté(s)")
                    for alerte in alertes:
                        logger.critical(f"  • {alerte.titre}")
                else:
                    logger.info("✅ Aucun changement BOFIP détecté")

                await db.commit()

        except Exception as e:
            logger.error(f"Erreur job BOFIP: {e}")

    async def _job_rapport_synthese_hebdo(self):
        """
        Tâche : Génération du rapport de synthèse hebdomadaire.
        Programmée : Tous les vendredis 18h00.
        """
        logger.info("📊 Génération rapport de synthèse hebdomadaire")

        try:
            async with get_db() as db:
                rapport = await self._generer_rapport_synthese_hebdo(db)
                logger.info(f"✅ Rapport généré: {rapport['alertes_semaine']} alertes cette semaine")

        except Exception as e:
            logger.error(f"Erreur rapport synthèse: {e}")

    async def _job_nettoyage_historique(self):
        """
        Tâche : Nettoyage de l'historique ancien (> 6 mois).
        Programmée : Premier du mois 2h00.
        """
        logger.info("🧹 Nettoyage historique de veille mensuel")

        try:
            async with get_db() as db:
                lignes_supprimees = await self._nettoyer_historique_ancien(db)
                logger.info(f"✅ Nettoyage terminé: {lignes_supprimees} entrées supprimées")

        except Exception as e:
            logger.error(f"Erreur nettoyage historique: {e}")

    async def _get_codes_postaux_surveilles(self, db) -> list[str]:
        """Récupère la liste des codes postaux à surveiller."""
        # TODO: Requête sur les règles DVF actives
        # Simulation pour l'instant
        return ["75001", "75015", "92100", "93200"]

    async def _generer_rapport_synthese_hebdo(self, db) -> dict:
        """Génère un rapport de synthèse des alertes de la semaine."""
        # TODO: Requête sur les alertes de la semaine
        # Simulation du rapport
        return {
            "periode": "2025-03-10 à 2025-03-16",
            "alertes_semaine": 12,
            "alertes_critiques": 2,
            "sources_actives": ["DVF", "Légifrance", "BOFIP"],
            "dossiers_impactes": 8
        }

    async def _nettoyer_historique_ancien(self, db) -> int:
        """Nettoie l'historique de veille > 6 mois."""
        # TODO: DELETE sur HistoriqueVeille avec date < now() - 6 mois
        # Simulation
        return 1543  # Nombre de lignes supprimées

    def get_statut_jobs(self) -> dict:
        """
        Retourne le statut de tous les jobs configurés.

        Returns:
            Dictionnaire avec informations sur chaque job
        """
        jobs_info = {}

        if not self.scheduler.running:
            return {"erreur": "Scheduler non démarré"}

        for job in self.scheduler.get_jobs():
            jobs_info[job.id] = {
                "nom": job.name,
                "prochaine_execution": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "actif": True
            }

        return jobs_info

    async def executer_job_manuel(self, job_id: str) -> dict:
        """
        Exécute manuellement un job de veille.

        Args:
            job_id: Identifiant du job à exécuter

        Returns:
            Résultat de l'exécution
        """
        logger.info(f"🔧 Exécution manuelle du job: {job_id}")

        try:
            if job_id == "veille_dvf_hebdo":
                await self._job_verification_dvf()
            elif job_id == "veille_legifrance_quotidien":
                await self._job_verification_legifrance()
            elif job_id == "veille_bofip_quotidien":
                await self._job_verification_bofip()
            elif job_id == "rapport_veille_hebdo":
                await self._job_rapport_synthese_hebdo()
            else:
                raise ValueError(f"Job inconnu: {job_id}")

            return {
                "succes": True,
                "job_id": job_id,
                "execution_manuelle": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur exécution manuelle {job_id}: {e}")
            return {
                "succes": False,
                "job_id": job_id,
                "erreur": str(e)
            }


# === Instance globale === #

# Scheduler global pour l'application
veille_scheduler: Optional[VeilleScheduler] = None


async def demarrer_scheduler_veille():
    """
    Démarre le scheduler de veille global.
    À appeler au démarrage de l'application FastAPI.
    """
    global veille_scheduler

    try:
        if veille_scheduler is None:
            veille_scheduler = VeilleScheduler()

        await veille_scheduler.demarrer()
        logger.info("🚀 Scheduler de veille initialisé et démarré")

    except Exception as e:
        logger.error(f"Erreur initialisation scheduler veille: {e}")
        raise


async def arreter_scheduler_veille():
    """
    Arrête le scheduler de veille global.
    À appeler à l'arrêt de l'application FastAPI.
    """
    global veille_scheduler

    try:
        if veille_scheduler and veille_scheduler.scheduler.running:
            await veille_scheduler.arreter()
            logger.info("🛑 Scheduler de veille arrêté proprement")

    except Exception as e:
        logger.error(f"Erreur arrêt scheduler veille: {e}")


def get_scheduler() -> Optional[VeilleScheduler]:
    """
    Retourne l'instance du scheduler de veille.

    Returns:
        Scheduler de veille ou None si non initialisé
    """
    return veille_scheduler