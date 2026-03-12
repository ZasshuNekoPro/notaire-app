"""
Tests des modèles d'authentification
ÉTAPE 1 — Tests avant implémentation (TDD)
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.models.auth import User, RefreshToken, AuditLog
from src.models.base import Base


# ============================================================
# CONFIGURATION BASE DE DONNÉES TEST
# ============================================================

TEST_DATABASE_URL = "postgresql+asyncpg://notaire:changeme_en_production@localhost:5432/notaire_app_test"

@pytest.fixture(scope="session")
def event_loop():
    """Fixture pour loop asyncio."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Engine de base de données de test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Créer la DB de test si elle n'existe pas
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

        # Créer toutes les tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    except Exception as e:
        pytest.skip(f"Impossible de setup la DB de test: {e}")

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Session de base de données pour chaque test."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ============================================================
# TESTS MODÈLE USER
# ============================================================

@pytest.mark.asyncio
async def test_user_creation_avec_champs_requis(db_session: AsyncSession):
    """Test création User avec tous les champs requis."""
    user = User(
        email="notaire@test.fr",
        password_hash="$2b$12$hashedpassword",
        role="notaire"
    )

    db_session.add(user)
    await db_session.commit()

    # Vérifications
    assert user.id is not None
    assert isinstance(user.id, UUID)
    assert user.email == "notaire@test.fr"
    assert user.password_hash == "$2b$12$hashedpassword"
    assert user.role == "notaire"
    assert user.created_at is not None
    assert user.updated_at is not None
    assert isinstance(user.created_at, datetime)


@pytest.mark.asyncio
async def test_user_unicite_email(db_session: AsyncSession):
    """Test unicité email - IntegrityError si doublon."""
    # Créer premier user
    user1 = User(
        email="doublon@test.fr",
        password_hash="hash1",
        role="client"
    )
    db_session.add(user1)
    await db_session.commit()

    # Tenter de créer un doublon
    user2 = User(
        email="doublon@test.fr",  # même email
        password_hash="hash2",
        role="admin"
    )
    db_session.add(user2)

    # Doit lever IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_valeurs_par_defaut(db_session: AsyncSession):
    """Test valeurs par défaut : is_active=True, is_verified=False, failed_login_count=0."""
    user = User(
        email="defaults@test.fr",
        password_hash="hash",
        role="clerc"
    )

    db_session.add(user)
    await db_session.commit()

    # Vérifier les valeurs par défaut
    assert user.is_active is True
    assert user.is_verified is False
    assert user.failed_login_count == 0
    assert user.totp_enabled is False
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_user_role_enum_valid(db_session: AsyncSession):
    """Test que les rôles valides sont acceptés."""
    roles_valides = ["admin", "notaire", "clerc", "client"]

    for i, role in enumerate(roles_valides):
        user = User(
            email=f"role_{role}@test.fr",
            password_hash="hash",
            role=role
        )
        db_session.add(user)

    await db_session.commit()

    # Tous doivent être créés sans erreur
    result = await db_session.execute(text("SELECT COUNT(*) FROM users"))
    count = result.scalar()
    assert count >= len(roles_valides)


# ============================================================
# TESTS MODÈLE REFRESH_TOKEN
# ============================================================

@pytest.mark.asyncio
async def test_refresh_token_creation(db_session: AsyncSession):
    """Test création RefreshToken avec expires_at futur et revoked=False par défaut."""
    # Créer un user d'abord
    user = User(
        email="token_user@test.fr",
        password_hash="hash",
        role="admin"
    )
    db_session.add(user)
    await db_session.flush()  # Pour récupérer l'ID

    # Créer le refresh token
    expires_at = datetime.utcnow() + timedelta(days=7)
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash="sha256_hash_of_token",
        expires_at=expires_at,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test"
    )

    db_session.add(refresh_token)
    await db_session.commit()

    # Vérifications
    assert refresh_token.id is not None
    assert isinstance(refresh_token.id, UUID)
    assert refresh_token.user_id == user.id
    assert refresh_token.token_hash == "sha256_hash_of_token"
    assert refresh_token.expires_at == expires_at
    assert refresh_token.expires_at > datetime.utcnow()  # Dans le futur
    assert refresh_token.revoked is False  # Défaut
    assert refresh_token.ip_address == "192.168.1.1"
    assert refresh_token.user_agent == "Mozilla/5.0 Test"
    assert refresh_token.created_at is not None


@pytest.mark.asyncio
async def test_refresh_token_unicite_hash(db_session: AsyncSession):
    """Test unicité du token_hash."""
    # Créer un user
    user = User(email="hash_test@test.fr", password_hash="hash", role="client")
    db_session.add(user)
    await db_session.flush()

    # Premier token
    token1 = RefreshToken(
        user_id=user.id,
        token_hash="same_hash_123",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(token1)
    await db_session.commit()

    # Tenter un token avec même hash
    token2 = RefreshToken(
        user_id=user.id,
        token_hash="same_hash_123",  # même hash
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(token2)

    # Doit lever IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_refresh_token_cascade_delete(db_session: AsyncSession):
    """Test suppression cascade user -> refresh_tokens."""
    # Créer user avec token
    user = User(email="cascade@test.fr", password_hash="hash", role="notaire")
    db_session.add(user)
    await db_session.flush()

    token = RefreshToken(
        user_id=user.id,
        token_hash="token_to_delete",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(token)
    await db_session.commit()

    token_id = token.id

    # Supprimer le user
    await db_session.delete(user)
    await db_session.commit()

    # Vérifier que le token a été supprimé
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM refresh_tokens WHERE id = :token_id"),
        {"token_id": token_id}
    )
    count = result.scalar()
    assert count == 0


# ============================================================
# TESTS MODÈLE AUDIT_LOG
# ============================================================

@pytest.mark.asyncio
async def test_audit_log_creation_avec_user(db_session: AsyncSession):
    """Test création AuditLog avec user_id et created_at auto-rempli."""
    # Créer user
    user = User(email="audit@test.fr", password_hash="hash", role="admin")
    db_session.add(user)
    await db_session.flush()

    # Créer audit log
    audit = AuditLog(
        user_id=user.id,
        action="LOGIN",
        resource_type="auth",
        resource_id=user.id,
        ip_address="10.0.0.1",
        details={"success": True, "method": "password"}
    )

    db_session.add(audit)
    await db_session.commit()

    # Vérifications
    assert audit.id is not None
    assert isinstance(audit.id, UUID)
    assert audit.user_id == user.id
    assert audit.action == "LOGIN"
    assert audit.resource_type == "auth"
    assert audit.resource_id == user.id
    assert audit.ip_address == "10.0.0.1"
    assert audit.details == {"success": True, "method": "password"}
    assert audit.created_at is not None
    assert isinstance(audit.created_at, datetime)


@pytest.mark.asyncio
async def test_audit_log_sans_user(db_session: AsyncSession):
    """Test création AuditLog sans user_id (action système)."""
    audit = AuditLog(
        user_id=None,  # Action système
        action="SYSTEM_BACKUP",
        resource_type="database",
        ip_address="127.0.0.1",
        details={"tables": ["users", "transactions"]}
    )

    db_session.add(audit)
    await db_session.commit()

    assert audit.user_id is None
    assert audit.action == "SYSTEM_BACKUP"
    assert audit.created_at is not None


@pytest.mark.asyncio
async def test_audit_log_details_jsonb(db_session: AsyncSession):
    """Test que details supporte les objets JSON complexes."""
    details_complex = {
        "action_details": {
            "before": {"role": "client", "is_active": True},
            "after": {"role": "clerc", "is_active": True}
        },
        "metadata": {
            "request_id": str(uuid4()),
            "duration_ms": 234,
            "nested": {"deep": {"value": [1, 2, 3]}}
        }
    }

    audit = AuditLog(
        user_id=None,
        action="USER_UPDATE",
        resource_type="user",
        details=details_complex
    )

    db_session.add(audit)
    await db_session.commit()

    # Relire depuis la DB
    await db_session.refresh(audit)

    assert audit.details == details_complex
    assert audit.details["action_details"]["before"]["role"] == "client"
    assert audit.details["metadata"]["nested"]["deep"]["value"] == [1, 2, 3]


# ============================================================
# TESTS INTÉGRATION CONTRAINTES
# ============================================================

@pytest.mark.asyncio
async def test_user_role_invalide_rejected(db_session: AsyncSession):
    """Test qu'un rôle invalide est rejeté par la contrainte CHECK."""
    user = User(
        email="bad_role@test.fr",
        password_hash="hash",
        role="super_admin"  # Rôle invalide
    )

    db_session.add(user)

    # Doit lever une erreur de contrainte
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_refresh_token_user_id_foreign_key(db_session: AsyncSession):
    """Test contrainte FK user_id vers users."""
    fake_user_id = uuid4()

    token = RefreshToken(
        user_id=fake_user_id,  # User inexistant
        token_hash="orphan_token",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db_session.add(token)

    # Doit lever IntegrityError (FK violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()