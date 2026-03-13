"""
Migration: Mise à jour des tables de succession selon spécifications TDD

Ajout de la table dossiers et mise à jour des modèles succession
avec FK dossier_id, valeurs en centimes (BigInteger), enums ajustés.

Revision ID: 002_dossiers_succession_tdd
Revises: 001_succession_tables
Create Date: 2025-03-12 23:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers
revision: str = '002_dossiers_succession_tdd'
down_revision: Union[str, None] = '001_succession_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Mise à jour vers spécifications TDD exactes."""

    # === 1. Création table dossiers === #
    op.create_table(
        'dossiers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Identification
        sa.Column('numero', sa.String(50), nullable=False, unique=True),
        sa.Column('type_dossier', sa.String(50), nullable=False, default='succession'),
        sa.Column('description', sa.Text, nullable=True),
    )

    # === 2. Recréation des ENUMs selon spécifications exactes === #

    # Statut traitement (nouveau)
    op.execute("""
        CREATE TYPE statut_traitement AS ENUM (
            'analyse_auto', 'en_cours', 'terminé'
        )
    """)

    # Type actif selon spécifications (ajout compte_bancaire, assurance_vie, vehicule)
    op.execute("DROP TYPE IF EXISTS type_actif CASCADE")
    op.execute("""
        CREATE TYPE type_actif AS ENUM (
            'immobilier', 'compte_bancaire', 'assurance_vie', 'vehicule', 'mobilier', 'autre'
        )
    """)

    # Lien parenté selon spécifications (suppression neveu_niece)
    op.execute("DROP TYPE IF EXISTS lien_parente CASCADE")
    op.execute("""
        CREATE TYPE lien_parente AS ENUM (
            'conjoint', 'enfant', 'petit_enfant', 'parent', 'frere_soeur', 'autre'
        )
    """)

    # === 3. Recréation table successions avec spécifications TDD === #

    # Sauvegarder les données existantes si nécessaire
    op.execute("DROP TABLE IF EXISTS successions CASCADE")

    op.create_table(
        'successions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # FK vers dossiers (spécification exacte)
        sa.Column('dossier_id', UUID(as_uuid=True), sa.ForeignKey('dossiers.id', ondelete='CASCADE'), nullable=False),

        # Informations défunt (dates obligatoires selon tests)
        sa.Column('defunt_nom', sa.String(100), nullable=False),
        sa.Column('defunt_prenom', sa.String(100), nullable=False),
        sa.Column('defunt_date_naissance', sa.Date, nullable=False),
        sa.Column('defunt_date_deces', sa.Date, nullable=False),
        sa.Column('regime_matrimonial', sa.String(50), nullable=True),
        sa.Column('nb_enfants', sa.Integer, nullable=False, default=0),

        # Statut selon spécifications
        sa.Column('statut_traitement', sa.Enum('analyse_auto', 'en_cours', 'terminé', name='statut_traitement'),
                 nullable=False, default='analyse_auto'),
    )

    # === 4. Recréation table heritiers === #
    op.create_table(
        'heritiers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Référence succession
        sa.Column('succession_id', UUID(as_uuid=True), sa.ForeignKey('successions.id', ondelete='CASCADE'), nullable=False),

        # Identité
        sa.Column('nom', sa.String(100), nullable=False),
        sa.Column('prenom', sa.String(100), nullable=False),

        # Lien et part selon spécifications
        sa.Column('lien_parente', sa.Enum('conjoint', 'enfant', 'petit_enfant', 'parent', 'frere_soeur', 'autre', name='lien_parente'), nullable=False),
        sa.Column('part_theorique', sa.Numeric(5, 4), nullable=True),  # Nullable selon tests

        # Coordonnées
        sa.Column('adresse', sa.Text, nullable=True),
    )

    # === 5. Recréation table actifs_successoraux avec BigInteger === #
    op.create_table(
        'actifs_successoraux',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Référence succession
        sa.Column('succession_id', UUID(as_uuid=True), sa.ForeignKey('successions.id', ondelete='CASCADE'), nullable=False),

        # Type et description
        sa.Column('type_actif', sa.Enum('immobilier', 'compte_bancaire', 'assurance_vie', 'vehicule', 'mobilier', 'autre', name='type_actif'), nullable=False),
        sa.Column('description', sa.Text, nullable=False),

        # Valeur EN CENTIMES (spécification critique)
        sa.Column('valeur_estimee', sa.BigInteger, nullable=False),

        # Compléments selon spécifications
        sa.Column('etablissement', sa.String(100), nullable=True),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('date_evaluation', sa.Date, nullable=True),
    )

    # === 6. Recréation table passifs_successoraux avec BigInteger === #
    op.create_table(
        'passifs_successoraux',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Référence succession
        sa.Column('succession_id', UUID(as_uuid=True), sa.ForeignKey('successions.id', ondelete='CASCADE'), nullable=False),

        # Type et description (String selon spécifications, pas enum)
        sa.Column('type_passif', sa.String(100), nullable=False),

        # Montant EN CENTIMES (spécification critique)
        sa.Column('montant', sa.BigInteger, nullable=False),

        # Créancier
        sa.Column('creancier', sa.String(100), nullable=True),
    )

    # === 7. Index critiques pour performance === #

    # Dossiers
    op.create_index('idx_dossiers_numero', 'dossiers', ['numero'])

    # Successions
    op.create_index('idx_successions_dossier_id', 'successions', ['dossier_id'])
    op.create_index('idx_successions_defunt', 'successions', ['defunt_nom', 'defunt_prenom'])
    op.create_index('idx_successions_statut', 'successions', ['statut_traitement'])

    # Héritiers
    op.create_index('idx_heritiers_succession_id', 'heritiers', ['succession_id'])
    op.create_index('idx_heritiers_lien', 'heritiers', ['lien_parente'])

    # Actifs
    op.create_index('idx_actifs_succession_id', 'actifs_successoraux', ['succession_id'])
    op.create_index('idx_actifs_type', 'actifs_successoraux', ['type_actif'])

    # Passifs
    op.create_index('idx_passifs_succession_id', 'passifs_successoraux', ['succession_id'])

    # === 8. Contraintes métier critiques === #

    # Quote-part valide
    op.create_check_constraint(
        'check_quote_part_valid',
        'heritiers',
        'part_theorique IS NULL OR (part_theorique >= 0 AND part_theorique <= 1)'
    )

    # Valeurs positives (en centimes)
    op.create_check_constraint(
        'check_valeur_positive',
        'actifs_successoraux',
        'valeur_estimee > 0'
    )

    op.create_check_constraint(
        'check_montant_positive',
        'passifs_successoraux',
        'montant > 0'
    )


def downgrade() -> None:
    """Retour à l'état précédent."""

    # Suppression des nouvelles tables
    op.drop_table('passifs_successoraux')
    op.drop_table('actifs_successoraux')
    op.drop_table('heritiers')
    op.drop_table('successions')
    op.drop_table('dossiers')

    # Suppression des nouveaux types
    op.execute("DROP TYPE IF EXISTS statut_traitement")
    op.execute("DROP TYPE IF EXISTS type_actif CASCADE")
    op.execute("DROP TYPE IF EXISTS lien_parente CASCADE")

    # Note: Recréer les anciennes tables si nécessaire
    # selon la migration 001_succession_tables