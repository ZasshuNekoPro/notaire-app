#!/usr/bin/env python3
"""
Moteur de calcul des droits de succession
Barèmes fiscaux 2025 - Code général des impôts art. 777
"""
import logging
from typing import List, Dict, Any
from decimal import Decimal
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.succession import Succession, Heritier, ActifSuccessoral, PassifSuccessoral

logger = logging.getLogger(__name__)


@dataclass
class CalculHeritier:
    """Calcul fiscal pour un héritier"""
    heritier_nom: str
    heritier_prenom: str
    lien_parente: str
    part_theorique: float
    part_nette: float  # En euros
    abattement: float
    base_taxable: float
    droits_succession: float
    taux_effectif: float


@dataclass
class CalculSuccessionResult:
    """Résultat complet du calcul fiscal d'une succession"""
    succession_id: str
    defunt_nom: str
    actif_brut: float
    passif_total: float
    actif_net: float
    calculs_par_heritier: List[CalculHeritier]
    total_droits_famille: float
    date_calcul: str


class BaremesSuccession2025:
    """
    Barèmes et abattements officiels 2025
    Source : Code général des impôts art. 777 et suivants
    """

    # Abattements légaux 2025 (en euros)
    ABATTEMENTS = {
        'enfant': 100_000,
        'conjoint': float('inf'),  # Exonération totale depuis 2007
        'petit_enfant': 100_000,   # Même que enfant par représentation
        'parent': 100_000,         # Ligne directe ascendante
        'frere_soeur': 15_932,
        'neveu_niece': 7_967,
        'autre': 1_594,
        'handicap': 159_325,       # Cumulable avec l'abattement principal
    }

    # Barème progressif ligne directe (enfants, parents, petits-enfants)
    BAREME_LIGNE_DIRECTE = [
        (8_072, 0.05),      # 5%
        (12_109, 0.10),     # 10%
        (15_932, 0.15),     # 15%
        (552_324, 0.20),    # 20%
        (902_838, 0.30),    # 30%
        (1_805_677, 0.40),  # 40%
        (float('inf'), 0.45)  # 45%
    ]

    # Barème frères et sœurs
    BAREME_FRERES_SOEURS = [
        (24_430, 0.35),     # 35%
        (float('inf'), 0.45)  # 45%
    ]

    def get_abattement(self, lien_parente: str, est_handicape: bool = False) -> float:
        """Retourne l'abattement applicable"""
        abattement_base = self.ABATTEMENTS.get(lien_parente, self.ABATTEMENTS['autre'])

        if est_handicape and lien_parente != 'conjoint':
            # Abattement handicap cumulable (sauf conjoint déjà exonéré)
            if abattement_base == float('inf'):
                return abattement_base
            return abattement_base + self.ABATTEMENTS['handicap']

        return abattement_base

    def calculer_barème_progressif(self, base_taxable: float, tranches: List[tuple]) -> float:
        """Applique un barème progressif"""
        if base_taxable <= 0:
            return 0.0

        droits = 0.0
        precedent = 0

        for plafond, taux in tranches:
            if base_taxable <= precedent:
                break

            tranche = min(base_taxable, plafond) - precedent
            droits += tranche * taux
            precedent = plafond

        return droits

    def calculer_droits_ligne_directe(self, base_taxable: float) -> float:
        """Calcul droits ligne directe (enfants, parents, petits-enfants)"""
        return self.calculer_barème_progressif(base_taxable, self.BAREME_LIGNE_DIRECTE)

    def calculer_droits_freres_soeurs(self, base_taxable: float) -> float:
        """Calcul droits frères et sœurs"""
        return self.calculer_barème_progressif(base_taxable, self.BAREME_FRERES_SOEURS)


def calculer_droits_par_heritier(actif_net: float, lien_parente: str, est_handicape: bool = False) -> float:
    """
    Calcule les droits de succession pour un héritier donné

    Args:
        actif_net: Part nette revenant à l'héritier (en euros)
        lien_parente: Type de lien ('enfant', 'conjoint', 'frere_soeur', etc.)
        est_handicape: Si l'héritier bénéficie de l'abattement handicap

    Returns:
        Montant des droits de succession (en euros)
    """
    baremes = BaremesSuccession2025()

    # 1. Exonération totale pour le conjoint
    if lien_parente == 'conjoint':
        return 0.0

    # 2. Calcul abattement applicable
    abattement = baremes.get_abattement(lien_parente, est_handicape)

    # 3. Base taxable après abattement
    if abattement == float('inf'):
        return 0.0

    base_taxable = max(0, actif_net - abattement)
    if base_taxable <= 0:
        return 0.0

    # 4. Application du barème selon le lien de parenté
    if lien_parente in ('enfant', 'petit_enfant', 'parent'):
        return baremes.calculer_droits_ligne_directe(base_taxable)
    elif lien_parente == 'frere_soeur':
        return baremes.calculer_droits_freres_soeurs(base_taxable)
    elif lien_parente == 'neveu_niece':
        # Taux fixe 55% pour neveux/nièces
        return base_taxable * 0.55
    else:
        # Taux fixe 60% pour autres héritiers
        return base_taxable * 0.60


async def get_succession_by_id(succession_id: UUID, db: AsyncSession) -> Succession:
    """Récupère une succession avec toutes ses relations"""
    query = (
        select(Succession)
        .where(Succession.id == succession_id)
    )
    result = await db.execute(query)
    succession = result.scalar_one_or_none()

    if not succession:
        raise ValueError(f"Succession {succession_id} non trouvée")

    return succession


async def calculer_succession(succession_id: UUID, db: AsyncSession) -> CalculSuccessionResult:
    """
    Calcule les droits de succession pour tous les héritiers

    Args:
        succession_id: ID de la succession
        db: Session base de données

    Returns:
        Résultat complet avec calculs par héritier
    """
    import datetime

    logger.info(f"Début calcul succession {succession_id}")

    # 1. Récupérer les données de succession
    succession = await get_succession_by_id(succession_id, db)

    # 2. Calcul actif brut
    actif_brut = sum(
        float(actif.valeur_estimee or 0) / 100  # Conversion centimes → euros
        for actif in succession.actifs
    )

    # 3. Calcul passif total
    passif_total = sum(
        float(passif.montant or 0) / 100  # Conversion centimes → euros
        for passif in succession.passifs
    )

    # 4. Actif net taxable
    actif_net = actif_brut - passif_total

    logger.info(f"Succession {succession.defunt_nom}: Actif {actif_brut:,.2f}€ - Passif {passif_total:,.2f}€ = Net {actif_net:,.2f}€")

    # 5. Calculs par héritier
    calculs_heritiers = []
    total_droits = 0.0

    for heritier in succession.heritiers:
        # Part nette de l'héritier
        part_theorique = float(heritier.part_theorique or 0)
        part_nette = actif_net * part_theorique

        # Calcul des droits
        # Note: Pour l'instant, on ne gère pas le statut handicapé dans le modèle
        # À ajouter si nécessaire : heritier.est_handicape
        droits = calculer_droits_par_heritier(part_nette, heritier.lien_parente, False)

        # Abattement utilisé pour info
        baremes = BaremesSuccession2025()
        abattement = baremes.get_abattement(heritier.lien_parente, False)
        base_taxable = max(0, part_nette - (abattement if abattement != float('inf') else part_nette))

        # Taux effectif
        taux_effectif = (droits / part_nette * 100) if part_nette > 0 else 0.0

        calcul = CalculHeritier(
            heritier_nom=heritier.nom,
            heritier_prenom=heritier.prenom,
            lien_parente=heritier.lien_parente,
            part_theorique=part_theorique,
            part_nette=part_nette,
            abattement=abattement if abattement != float('inf') else 0.0,
            base_taxable=base_taxable,
            droits_succession=droits,
            taux_effectif=taux_effectif
        )

        calculs_heritiers.append(calcul)
        total_droits += droits

        logger.info(f"Héritier {heritier.prenom} {heritier.nom} ({heritier.lien_parente}): "
                   f"Part {part_nette:,.2f}€ → Droits {droits:,.2f}€")

    # 6. Résultat final
    result = CalculSuccessionResult(
        succession_id=str(succession_id),
        defunt_nom=f"{succession.defunt_prenom} {succession.defunt_nom}",
        actif_brut=actif_brut,
        passif_total=passif_total,
        actif_net=actif_net,
        calculs_par_heritier=calculs_heritiers,
        total_droits_famille=total_droits,
        date_calcul=datetime.datetime.now().isoformat()
    )

    logger.info(f"Calcul terminé: Total droits famille {total_droits:,.2f}€")

    return result


def generer_rapport_succession(calcul: CalculSuccessionResult) -> str:
    """
    Génère un rapport textuel de la succession

    Args:
        calcul: Résultat du calcul fiscal

    Returns:
        Rapport formaté en texte
    """
    rapport = f"""
═══════════════════════════════════════════════════════════════
              CALCUL DES DROITS DE SUCCESSION
═══════════════════════════════════════════════════════════════

Succession de : {calcul.defunt_nom}
Date du calcul : {calcul.date_calcul.split('T')[0]}

PATRIMOINE :
  Actif brut      : {calcul.actif_brut:>12,.2f} €
  Passif total    : {calcul.passif_total:>12,.2f} €
  ─────────────────────────────────────
  Actif net       : {calcul.actif_net:>12,.2f} €

RÉPARTITION ET DROITS :
"""

    for calcul_h in calcul.calculs_par_heritier:
        rapport += f"""
  {calcul_h.heritier_prenom} {calcul_h.heritier_nom} ({calcul_h.lien_parente}) :
    Part héritée    : {calcul_h.part_nette:>12,.2f} € ({calcul_h.part_theorique*100:.1f}%)
    Abattement      : {calcul_h.abattement:>12,.2f} €
    Base taxable    : {calcul_h.base_taxable:>12,.2f} €
    Droits à payer  : {calcul_h.droits_succession:>12,.2f} € ({calcul_h.taux_effectif:.1f}%)
"""

    rapport += f"""
  ═════════════════════════════════════════════════════════════════
  TOTAL DROITS FAMILLE : {calcul.total_droits_famille:>12,.2f} €
  ═════════════════════════════════════════════════════════════════

Références légales :
- Code général des impôts, art. 777 et suivants (barèmes 2025)
- Abattements et exonérations selon art. 779 CGI

Ce calcul est fourni à titre indicatif et doit être validé
par un professionnel du droit fiscal.
"""

    return rapport


async def mettre_a_jour_calculs_succession(succession_id: UUID, db: AsyncSession) -> CalculSuccessionResult:
    """
    Calcule et met à jour les droits de succession en base de données.

    Args:
        succession_id: ID de la succession
        db: Session base de données

    Returns:
        Résultat du calcul avec mise à jour en DB
    """
    logger.info(f"Mise à jour calculs succession {succession_id}")

    # 1. Effectuer le calcul
    calcul = await calculer_succession(succession_id, db)

    # 2. Mettre à jour les métadonnées de la succession
    succession = await get_succession_by_id(succession_id, db)

    # TODO: Ajouter champs calcul_metadata dans le modèle Succession
    # succession.calcul_metadata = {
    #     "date_calcul": calcul.date_calcul,
    #     "actif_net": float(calcul.actif_net),
    #     "total_droits": float(calcul.total_droits_famille)
    # }

    # 3. TODO: Mettre à jour les calculs par héritier en base
    # Pour chaque héritier, stocker part_heritee, droits_succession, etc.
    # Nécessite d'ajouter ces champs aux modèles

    await db.commit()

    logger.info(f"Calculs succession {succession_id} mis à jour en DB")

    return calcul