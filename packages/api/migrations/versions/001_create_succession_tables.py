"""
Migration: Création des tables de succession

Tables : successions, heritiers, actifs_successoraux, passifs_successoraux
Avec relations, enums et contraintes fiscales.

Revision ID: 001_succession_tables
Revises:
Create Date: 2025-03-12 22:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers
revision: str = '001_succession_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Création des tables de succession."""

    # === Création des types ENUM === #

    # Statut succession
    op.execute("""
        CREATE TYPE statut_succession AS ENUM (
            'en_cours', 'complete', 'suspendue', 'cloturee'
        )
    """)

    # Lien de parenté
    op.execute("""
        CREATE TYPE lien_parente AS ENUM (
            'conjoint', 'enfant', 'petit_enfant', 'parent',
            'frere_soeur', 'neveu_niece', 'autre'
        )
    """)

    # Type d'actif
    op.execute("""
        CREATE TYPE type_actif AS ENUM (
            'immobilier', 'financier', 'mobilier', 'professionnel', 'autre'
        )
    """)

    # Type de passif
    op.execute("""
        CREATE TYPE type_passif AS ENUM (
            'credit_immobilier', 'credit_consommation', 'dette_fiscale',
            'frais_funeraires', 'autre'
        )
    """)

    # === Table successions === #
    op.create_table(
        'successions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Identification du dossier
        sa.Column('numero_dossier', sa.String(50), nullable=False, unique=True),

        # Informations du défunt
        sa.Column('defunt_nom', sa.String(100), nullable=False),
        sa.Column('defunt_prenom', sa.String(100), nullable=False),
        sa.Column('defunt_date_naissance', sa.Date, nullable=True),
        sa.Column('defunt_date_deces', sa.Date, nullable=True),
        sa.Column('lieu_deces', sa.String(255), nullable=True),

        # Statut et suivi
        sa.Column('statut', sa.Enum('en_cours', 'complete', 'suspendue', 'cloturee', name='statut_succession'),
                 nullable=False, default='en_cours'),

        # Totaux calculés
        sa.Column('total_actifs', sa.Numeric(15, 2), nullable=True),
        sa.Column('total_passifs', sa.Numeric(15, 2), nullable=True),
        sa.Column('actif_net', sa.Numeric(15, 2), nullable=True),

        # Métadonnées d'extraction IA
        sa.Column('extraction_metadata', JSONB, nullable=True, default={}),
    )

    # === Table heritiers === #
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
        sa.Column('date_naissance', sa.Date, nullable=True),

        # Lien de parenté et quote-part
        sa.Column('lien_parente', sa.Enum('conjoint', 'enfant', 'petit_enfant', 'parent', 'frere_soeur', 'neveu_niece', 'autre', name='lien_parente'), nullable=False),
        sa.Column('quote_part_legale', sa.Numeric(5, 4), nullable=False),

        # Coordonnées
        sa.Column('adresse', sa.Text, nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('telephone', sa.String(20), nullable=True),

        # Calculs fiscaux
        sa.Column('part_heritee', sa.Numeric(15, 2), nullable=True),
        sa.Column('abattement_applicable', sa.Numeric(15, 2), nullable=True),
        sa.Column('base_taxable', sa.Numeric(15, 2), nullable=True),
        sa.Column('droits_succession', sa.Numeric(15, 2), nullable=True),
    )

    # === Table actifs_successoraux === #
    op.create_table(
        'actifs_successoraux',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Référence succession
        sa.Column('succession_id', UUID(as_uuid=True), sa.ForeignKey('successions.id', ondelete='CASCADE'), nullable=False),

        # Type et description
        sa.Column('type_actif', sa.Enum('immobilier', 'financier', 'mobilier', 'professionnel', 'autre', name='type_actif'), nullable=False),
        sa.Column('description', sa.Text, nullable=False),

        # Valeur
        sa.Column('valeur_estimee', sa.Numeric(15, 2), nullable=False),
        sa.Column('date_estimation', sa.Date, nullable=True),

        # Spécifique immobilier
        sa.Column('adresse', sa.Text, nullable=True),
        sa.Column('surface', sa.Numeric(8, 2), nullable=True),

        # Estimation DVF
        sa.Column('estimation_dvf', JSONB, nullable=True, default={}),
    )

    # === Table passifs_successoraux === #
    op.create_table(
        'passifs_successoraux',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Référence succession
        sa.Column('succession_id', UUID(as_uuid=True), sa.ForeignKey('successions.id', ondelete='CASCADE'), nullable=False),

        # Type et description
        sa.Column('type_passif', sa.Enum('credit_immobilier', 'credit_consommation', 'dette_fiscale', 'frais_funeraires', 'autre', name='type_passif'), nullable=False),
        sa.Column('description', sa.Text, nullable=False),

        # Montant
        sa.Column('montant', sa.Numeric(15, 2), nullable=False),

        # Créancier
        sa.Column('creancier', sa.String(255), nullable=True),
        sa.Column('date_echeance', sa.Date, nullable=True),
    )

    # === Index pour performance === #

    # Successions
    op.create_index('idx_successions_numero', 'successions', ['numero_dossier'])
    op.create_index('idx_successions_defunt', 'successions', ['defunt_nom', 'defunt_prenom'])
    op.create_index('idx_successions_statut', 'successions', ['statut'])
    op.create_index('idx_successions_date_deces', 'successions', ['defunt_date_deces'])

    # Héritiers
    op.create_index('idx_heritiers_succession_id', 'heritiers', ['succession_id'])
    op.create_index('idx_heritiers_lien', 'heritiers', ['lien_parente'])
    op.create_index('idx_heritiers_nom', 'heritiers', ['nom', 'prenom'])

    # Actifs
    op.create_index('idx_actifs_succession_id', 'actifs_successoraux', ['succession_id'])
    op.create_index('idx_actifs_type', 'actifs_successoraux', ['type_actif'])
    op.create_index('idx_actifs_valeur', 'actifs_successoraux', ['valeur_estimee'])

    # Passifs
    op.create_index('idx_passifs_succession_id', 'passifs_successoraux', ['succession_id'])
    op.create_index('idx_passifs_type', 'passifs_successoraux', ['type_passif'])
    op.create_index('idx_passifs_montant', 'passifs_successoraux', ['montant'])

    # === Contraintes métier === #

    # Quote-part valide (entre 0 et 1)
    op.create_check_constraint(
        'check_quote_part_valid',
        'heritiers',
        'quote_part_legale >= 0 AND quote_part_legale <= 1'
    )

    # Valeur actif positive
    op.create_check_constraint(
        'check_valeur_positive',
        'actifs_successoraux',
        'valeur_estimee >= 0'
    )

    # Montant passif positif
    op.create_check_constraint(
        'check_montant_positive',
        'passifs_successoraux',
        'montant >= 0'
    )


def downgrade() -> None:
    """Suppression des tables de succession."""

    # Suppression des tables (cascade automatique des FK)
    op.drop_table('passifs_successoraux')
    op.drop_table('actifs_successoraux')
    op.drop_table('heritiers')
    op.drop_table('successions')

    # Suppression des types ENUM
    op.execute("DROP TYPE IF EXISTS type_passif")
    op.execute("DROP TYPE IF EXISTS type_actif")
    op.execute("DROP TYPE IF EXISTS lien_parente")
    op.execute("DROP TYPE IF EXISTS statut_succession")