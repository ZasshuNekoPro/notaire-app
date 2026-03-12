"""
Alembic environment configuration pour notaire-app
Support async SQLAlchemy avec PostgreSQL
"""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
import os
import sys

# Ajouter le src path pour importer les modèles
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import des modèles pour autogenerate
from models.base import Base
from models.auth import User, RefreshToken, AuditLog

# Configuration Alembic
config = context.config

# Interpréter le fichier de config pour Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées SQLAlchemy pour autogenerate
target_metadata = Base.metadata

# Configuration de la base de données
def get_database_url():
    """Récupère l'URL de base de données depuis .env ou config."""
    # Priorité aux variables d'environnement
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]

    # Fallback sur alembic.ini
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """
    Migrations en mode offline.
    Génère le SQL sans connexion base.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Exécute les migrations avec une connexion."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Options avancées pour PostgreSQL
        render_as_batch=False,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Migrations en mode async avec SQLAlchemy 2.0."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = create_async_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Migrations en mode online avec connexion async.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()