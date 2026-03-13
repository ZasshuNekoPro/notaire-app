"""
create_veille_tables

Revision ID: 003_create_veille_tables
Revises: 002_add_dossiers_and_update_succession
Create Date: 2025-03-13 14:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '003_create_veille_tables'
down_revision = '002_add_dossiers_and_update_succession'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Crée les tables pour le système de veille automatique.
    """
    # Création des ENUMs PostgreSQL
    type_source_enum = postgresql.ENUM(
        'dvf', 'legifrance', 'bofip', 'jurisprudence',
        name='type_source'
    )
    type_source_enum.create(op.get_bind())

    niveau_impact_enum = postgresql.ENUM(
        'info', 'faible', 'moyen', 'fort', 'critique',
        name='niveau_impact'
    )
    niveau_impact_enum.create(op.get_bind())

    statut_alerte_enum = postgresql.ENUM(
        'nouvelle', 'en_cours', 'traitee', 'archivee',
        name='statut_alerte'
    )
    statut_alerte_enum.create(op.get_bind())

    # Table des règles de veille
    op.create_table(
        'veille_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now()),

        # Identification de la règle
        sa.Column('nom', sa.String(255), nullable=False, comment="Nom explicite de la règle de veille"),
        sa.Column('description', sa.Text, nullable=True, comment="Description détaillée de ce qui est surveillé"),

        # Source surveillée
        sa.Column('type_source', type_source_enum, nullable=False, comment="Type de source à surveiller"),

        # Configuration de la surveillance
        sa.Column('configuration', postgresql.JSON, nullable=False, comment="Paramètres JSON spécifiques à la source"),

        # Filtrage géographique ou thématique
        sa.Column('code_postal', sa.String(10), nullable=True, comment="Code postal pour filtrage géographique DVF"),
        sa.Column('articles_codes', postgresql.JSON, nullable=True, comment="Liste des articles de code surveillés"),

        # Activation et périodicité
        sa.Column('active', sa.Boolean, nullable=False, default=True, comment="Règle active ou suspendue"),
        sa.Column('frequence_heures', sa.Integer, nullable=False, default=24, comment="Fréquence de vérification en heures"),
        sa.Column('derniere_verification', sa.DateTime, nullable=True, comment="Timestamp de la dernière vérification"),

        # Association avec un dossier spécifique (optionnel)
        sa.Column('dossier_id', postgresql.UUID(as_uuid=True), nullable=True, comment="Dossier spécifique concerné par cette règle"),

        # Contraintes et index
        sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='SET NULL'),
        sa.Index('ix_veille_rules_type_source', 'type_source'),
        sa.Index('ix_veille_rules_active', 'active'),
        sa.Index('ix_veille_rules_code_postal', 'code_postal'),
        sa.Index('ix_veille_rules_dossier_id', 'dossier_id'),
    )

    # Table des alertes
    op.create_table(
        'alertes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now()),

        # Référence à la règle de veille
        sa.Column('veille_rule_id', postgresql.UUID(as_uuid=True), nullable=False, comment="Règle de veille qui a généré cette alerte"),

        # Classification de l'alerte
        sa.Column('titre', sa.String(255), nullable=False, comment="Titre court et explicite de l'alerte"),
        sa.Column('niveau_impact', niveau_impact_enum, nullable=False, comment="Niveau d'impact estimé sur les dossiers"),
        sa.Column('statut', statut_alerte_enum, nullable=False, default='nouvelle', comment="Statut de traitement de l'alerte"),

        # Contenu de l'alerte
        sa.Column('contenu', sa.Text, nullable=False, comment="Description détaillée du changement détecté"),
        sa.Column('details_techniques', postgresql.JSON, nullable=True, comment="Détails techniques du changement (JSON)"),

        # Analyse d'impact IA
        sa.Column('analyse_impact', sa.Text, nullable=True, comment="Analyse d'impact générée par IA"),
        sa.Column('url_source', sa.String(500), nullable=True, comment="URL de la source du changement"),

        # Assignation et traitement
        sa.Column('assignee_user_id', postgresql.UUID(as_uuid=True), nullable=True, comment="Utilisateur assigné pour traiter cette alerte"),
        sa.Column('date_traitement', sa.DateTime, nullable=True, comment="Date de traitement de l'alerte"),
        sa.Column('commentaire_traitement', sa.Text, nullable=True, comment="Commentaire du traitement effectué"),

        # Dossiers potentiellement impactés
        sa.Column('dossiers_impactes', postgresql.JSON, nullable=True, comment="Liste des IDs de dossiers potentiellement impactés"),

        # Contraintes et index
        sa.ForeignKeyConstraint(['veille_rule_id'], ['veille_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignee_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.Index('ix_alertes_veille_rule_id', 'veille_rule_id'),
        sa.Index('ix_alertes_niveau_impact', 'niveau_impact'),
        sa.Index('ix_alertes_statut', 'statut'),
        sa.Index('ix_alertes_assignee_user_id', 'assignee_user_id'),
        sa.Index('ix_alertes_created_at', 'created_at'),
    )

    # Table de l'historique de veille
    op.create_table(
        'historique_veille',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now()),

        # Référence à la règle
        sa.Column('veille_rule_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Résultats de la vérification
        sa.Column('date_verification', sa.DateTime, nullable=False, comment="Moment de la vérification"),
        sa.Column('duree_ms', sa.Integer, nullable=False, comment="Durée de la vérification en millisecondes"),
        sa.Column('succes', sa.Boolean, nullable=False, comment="Vérification réussie ou échouée"),
        sa.Column('elements_verifies', sa.Integer, nullable=False, default=0, comment="Nombre d'éléments vérifiés"),
        sa.Column('alertes_creees', sa.Integer, nullable=False, default=0, comment="Nombre d'alertes créées lors de cette vérification"),

        # Détails techniques
        sa.Column('logs_techniques', postgresql.JSON, nullable=True, comment="Logs techniques de la vérification"),
        sa.Column('erreur', sa.Text, nullable=True, comment="Message d'erreur si vérification échouée"),

        # Contraintes et index
        sa.ForeignKeyConstraint(['veille_rule_id'], ['veille_rules.id'], ondelete='CASCADE'),
        sa.Index('ix_historique_veille_veille_rule_id', 'veille_rule_id'),
        sa.Index('ix_historique_veille_date_verification', 'date_verification'),
        sa.Index('ix_historique_veille_succes', 'succes'),
    )

    # Ajouter la relation dans la table dossiers si elle n'existe pas déjà
    # (relation inverse pour veille_rules.dossier_id)
    # Note: Cette relation sera gérée au niveau SQLAlchemy, pas de contrainte supplémentaire nécessaire

    print("✅ Tables de veille créées: veille_rules, alertes, historique_veille")


def downgrade() -> None:
    """
    Supprime les tables de veille et les ENUMs associés.
    """
    # Supprimer les tables dans l'ordre inverse
    op.drop_table('historique_veille')
    op.drop_table('alertes')
    op.drop_table('veille_rules')

    # Supprimer les ENUMs PostgreSQL
    statut_alerte_enum = postgresql.ENUM(name='statut_alerte')
    statut_alerte_enum.drop(op.get_bind())

    niveau_impact_enum = postgresql.ENUM(name='niveau_impact')
    niveau_impact_enum.drop(op.get_bind())

    type_source_enum = postgresql.ENUM(name='type_source')
    type_source_enum.drop(op.get_bind())

    print("❌ Tables de veille supprimées")