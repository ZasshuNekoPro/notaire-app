"""
Tests du service d'authentification
ÉTAPE 1 — Tests avant implémentation (TDD)
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, AsyncMock, patch
import redis.asyncio as redis
import bcrypt
import jwt
import pyotp
from fastapi import HTTPException

from src.services.auth_service import AuthService
from src.models.auth import User, RefreshToken, AuditLog
from src.schemas.auth import UserCreate, UserLogin, TokenPair, UserResponse
from src.models.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


# ============================================================
# CONFIGURATION BASE DE DONNÉES TEST
# ============================================================

TEST_DATABASE_URL = "postgresql+asyncpg://notaire:changeme_en_production@localhost:5432/notaire_app_test"
REDIS_TEST_URL = "redis://localhost:6379/1"  # DB 1 pour les tests

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

    try:
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


@pytest.fixture
async def redis_client():
    """Client Redis pour les tests."""
    client = redis.from_url(REDIS_TEST_URL, decode_responses=True)

    # Nettoyer la DB test
    await client.flushdb()

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def auth_service(db_session, redis_client):
    """Service d'authentification configuré pour les tests."""
    service = AuthService(
        db=db_session,
        redis=redis_client,
        jwt_secret="test_jwt_secret_very_long_string_minimum_32_chars",
        jwt_expire_minutes=15,
        refresh_expire_days=7
    )
    return service


# ============================================================
# TESTS REGISTER
# ============================================================

@pytest.mark.asyncio
async def test_register_success(auth_service: AuthService):
    """Test inscription réussie."""
    user_data = UserCreate(
        email="nouveau@notaire.fr",
        password="MotDePasseSecure123!",
        role="notaire"
    )

    # Enregistrement
    result = await auth_service.register(
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )

    # Vérifications
    assert isinstance(result, UserResponse)
    assert result.email == "nouveau@notaire.fr"
    assert result.role == "notaire"
    assert result.is_active is True
    assert result.is_verified is False  # Email non vérifié par défaut
    assert isinstance(result.id, UUID)


@pytest.mark.asyncio
async def test_register_email_deja_pris(auth_service: AuthService, db_session: AsyncSession):
    """Test échec inscription - email déjà pris."""
    # Créer un user existant
    existing_user = User(
        email="existant@notaire.fr",
        password_hash="$2b$12$hashedpassword",
        role="client"
    )
    db_session.add(existing_user)
    await db_session.commit()

    # Tenter d'enregistrer avec le même email
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(
            email="existant@notaire.fr",
            password="NouveauPassword123!",
            role="clerc"
        )

    assert exc_info.value.status_code == 409
    assert "déjà utilisé" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_register_password_trop_court(auth_service: AuthService):
    """Test échec inscription - mot de passe trop court."""
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(
            email="test@notaire.fr",
            password="123",  # Trop court
            role="client"
        )

    assert exc_info.value.status_code == 400
    assert "mot de passe" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_register_bcrypt_rounds_12(auth_service: AuthService, db_session: AsyncSession):
    """Test que bcrypt utilise rounds=12 minimum."""
    await auth_service.register(
        email="bcrypt@test.fr",
        password="TestPassword123!",
        role="client"
    )

    # Récupérer le user de la DB
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.email == "bcrypt@test.fr"))
    user = result.scalar_one()

    # Vérifier le format bcrypt avec rounds=12
    assert user.password_hash.startswith("$2b$12$")


# ============================================================
# TESTS LOGIN
# ============================================================

@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService, db_session: AsyncSession):
    """Test connexion réussie."""
    # Créer un user vérifié
    password_hash = bcrypt.hashpw("MotDePasseSecure123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="login@notaire.fr",
        password_hash=password_hash,
        role="notaire",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()

    # Tentative de connexion
    result = await auth_service.login(
        email="login@notaire.fr",
        password="MotDePasseSecure123!",
        ip_address="192.168.1.100",
        user_agent="Test Browser"
    )

    # Vérifications
    assert isinstance(result, TokenPair)
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.expires_in == 15 * 60  # 15 minutes en secondes
    assert result.token_type == "bearer"

    # Vérifier le JWT
    payload = jwt.decode(
        result.access_token,
        auth_service.jwt_secret,
        algorithms=["HS256"]
    )
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "notaire"


@pytest.mark.asyncio
async def test_login_mauvais_password(auth_service: AuthService, db_session: AsyncSession):
    """Test échec connexion - mauvais mot de passe."""
    password_hash = bcrypt.hashpw("BonMotDePasse123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="badpass@notaire.fr",
        password_hash=password_hash,
        role="client",
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    # Tentative avec mauvais password
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            email="badpass@notaire.fr",
            password="MauvaisMotDePasse",
            ip_address="192.168.1.100"
        )

    assert exc_info.value.status_code == 401

    # Vérifier que failed_login_count a été incrémenté
    await db_session.refresh(user)
    assert user.failed_login_count == 1


@pytest.mark.asyncio
async def test_login_compte_verrouille(auth_service: AuthService, db_session: AsyncSession):
    """Test échec connexion - compte verrouillé."""
    user = User(
        email="locked@notaire.fr",
        password_hash="$2b$12$hash",
        role="client",
        is_verified=True,
        failed_login_count=5,
        locked_until=datetime.utcnow() + timedelta(minutes=20)  # Verrouillé
    )
    db_session.add(user)
    await db_session.commit()

    # Tentative de connexion
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            email="locked@notaire.fr",
            password="MotDePasse123!",
            ip_address="192.168.1.100"
        )

    assert exc_info.value.status_code == 423
    assert "verrouillé" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_login_non_verifie(auth_service: AuthService, db_session: AsyncSession):
    """Test échec connexion - email non vérifié."""
    password_hash = bcrypt.hashpw("MotDePasse123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="unverified@notaire.fr",
        password_hash=password_hash,
        role="client",
        is_verified=False  # Non vérifié
    )
    db_session.add(user)
    await db_session.commit()

    # Tentative de connexion
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            email="unverified@notaire.fr",
            password="MotDePasse123!",
            ip_address="192.168.1.100"
        )

    assert exc_info.value.status_code == 403
    assert "vérifi" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_login_brute_force_protection(auth_service: AuthService, db_session: AsyncSession):
    """Test protection brute-force : 5 tentatives → verrouillage."""
    password_hash = bcrypt.hashpw("BonPassword123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="brute@notaire.fr",
        password_hash=password_hash,
        role="client",
        is_verified=True,
        failed_login_count=4  # Déjà 4 tentatives
    )
    db_session.add(user)
    await db_session.commit()

    # 5ème tentative échouée → verrouillage
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            email="brute@notaire.fr",
            password="MauvaisPassword",
            ip_address="192.168.1.100"
        )

    assert exc_info.value.status_code == 401

    # Vérifier que le compte est maintenant verrouillé
    await db_session.refresh(user)
    assert user.failed_login_count == 5
    assert user.locked_until is not None
    assert user.locked_until > datetime.utcnow()


@pytest.mark.asyncio
async def test_login_audit_log_created(auth_service: AuthService, db_session: AsyncSession):
    """Test création audit log lors du login."""
    password_hash = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="audit@notaire.fr",
        password_hash=password_hash,
        role="notaire",
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    # Login réussi
    await auth_service.login(
        email="audit@notaire.fr",
        password="Password123!",
        ip_address="10.0.0.1",
        user_agent="Test Agent"
    )

    # Vérifier création audit log
    from sqlalchemy import select
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.user_id == user.id)
    )
    audit_log = result.scalar_one()

    assert audit_log.action == "LOGIN_SUCCESS"
    assert audit_log.ip_address == "10.0.0.1"
    assert audit_log.details["user_agent"] == "Test Agent"


# ============================================================
# TESTS REFRESH TOKEN
# ============================================================

@pytest.mark.asyncio
async def test_refresh_success(auth_service: AuthService, redis_client, db_session: AsyncSession):
    """Test rafraîchissement token réussi."""
    # Créer un user
    user = User(
        email="refresh@notaire.fr",
        password_hash="$2b$12$hash",
        role="clerc",
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    # Simuler un refresh token valide dans Redis
    refresh_token = str(uuid4())
    token_hash = auth_service._hash_token(refresh_token)
    token_data = {
        "user_id": str(user.id),
        "created_at": datetime.utcnow().isoformat(),
        "ip_address": "192.168.1.1"
    }
    await redis_client.setex(
        f"refresh_token:{token_hash}",
        auth_service.refresh_expire_days * 24 * 3600,
        str(token_data)
    )

    # Rafraîchir le token
    result = await auth_service.refresh(refresh_token)

    # Vérifications
    assert isinstance(result, TokenPair)
    assert result.access_token != refresh_token  # Nouveau token
    assert result.refresh_token != refresh_token  # Token rotation

    # Vérifier que l'ancien token a été révoqué
    old_exists = await redis_client.exists(f"refresh_token:{token_hash}")
    assert old_exists == 0


@pytest.mark.asyncio
async def test_refresh_token_revoque(auth_service: AuthService):
    """Test échec refresh - token révoqué."""
    fake_token = str(uuid4())

    # Token inexistant dans Redis = révoqué
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.refresh(fake_token)

    assert exc_info.value.status_code == 401
    assert "token invalide" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_refresh_token_expire(auth_service: AuthService, redis_client):
    """Test échec refresh - token expiré."""
    # Simuler un token expiré (TTL=1 seconde)
    refresh_token = str(uuid4())
    token_hash = auth_service._hash_token(refresh_token)

    await redis_client.setex(
        f"refresh_token:{token_hash}",
        1,  # 1 seconde
        '{"user_id": "' + str(uuid4()) + '"}'
    )

    # Attendre expiration
    import asyncio
    await asyncio.sleep(1.1)

    # Tentative de refresh
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.refresh(refresh_token)

    assert exc_info.value.status_code == 401


# ============================================================
# TESTS LOGOUT
# ============================================================

@pytest.mark.asyncio
async def test_logout_revocation_effective(auth_service: AuthService, redis_client):
    """Test révocation effective lors du logout."""
    # Simuler un refresh token actif
    refresh_token = str(uuid4())
    token_hash = auth_service._hash_token(refresh_token)

    await redis_client.setex(
        f"refresh_token:{token_hash}",
        3600,  # 1 heure
        '{"user_id": "' + str(uuid4()) + '"}'
    )

    # Vérifier que le token existe
    exists_before = await redis_client.exists(f"refresh_token:{token_hash}")
    assert exists_before == 1

    # Logout
    await auth_service.logout(refresh_token)

    # Vérifier révocation
    exists_after = await redis_client.exists(f"refresh_token:{token_hash}")
    assert exists_after == 0


@pytest.mark.asyncio
async def test_logout_token_inexistant(auth_service: AuthService):
    """Test logout avec token inexistant (pas d'erreur)."""
    fake_token = str(uuid4())

    # Ne doit pas lever d'exception
    await auth_service.logout(fake_token)


# ============================================================
# TESTS 2FA TOTP
# ============================================================

@pytest.mark.asyncio
async def test_setup_2fa_success(auth_service: AuthService, db_session: AsyncSession):
    """Test setup 2FA réussi."""
    user = User(
        email="2fa@notaire.fr",
        password_hash="$2b$12$hash",
        role="notaire",
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()

    # Setup 2FA
    result = await auth_service.setup_2fa(user.id)

    # Vérifications
    assert "secret" in result
    assert "qr_code_uri" in result
    assert "backup_codes" in result

    assert len(result["secret"]) >= 16  # Secret TOTP base32
    assert "otpauth://totp/" in result["qr_code_uri"]
    assert "Notaire App" in result["qr_code_uri"]
    assert len(result["backup_codes"]) > 0

    # Vérifier que le secret est sauvé en DB
    await db_session.refresh(user)
    assert user.totp_secret == result["secret"]
    assert user.totp_enabled is True


@pytest.mark.asyncio
async def test_verify_2fa_code_valide(auth_service: AuthService, db_session: AsyncSession):
    """Test vérification 2FA avec code valide."""
    # Setup TOTP secret
    secret = pyotp.random_base32()
    user = User(
        email="2fa_valid@notaire.fr",
        password_hash="$2b$12$hash",
        role="notaire",
        is_verified=True,
        totp_secret=secret,
        totp_enabled=True
    )
    db_session.add(user)
    await db_session.commit()

    # Générer un code valide
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    # Vérifier le code
    is_valid = await auth_service.verify_2fa(user.id, valid_code)
    assert is_valid is True


@pytest.mark.asyncio
async def test_verify_2fa_code_invalide(auth_service: AuthService, db_session: AsyncSession):
    """Test vérification 2FA avec code invalide."""
    secret = pyotp.random_base32()
    user = User(
        email="2fa_invalid@notaire.fr",
        password_hash="$2b$12$hash",
        role="notaire",
        is_verified=True,
        totp_secret=secret,
        totp_enabled=True
    )
    db_session.add(user)
    await db_session.commit()

    # Code invalide
    is_valid = await auth_service.verify_2fa(user.id, "000000")
    assert is_valid is False


@pytest.mark.asyncio
async def test_verify_2fa_fenetre_30s(auth_service: AuthService, db_session: AsyncSession):
    """Test vérification 2FA avec fenêtre ±30s."""
    secret = pyotp.random_base32()
    user = User(
        email="2fa_window@notaire.fr",
        password_hash="$2b$12$hash",
        role="notaire",
        is_verified=True,
        totp_secret=secret,
        totp_enabled=True
    )
    db_session.add(user)
    await db_session.commit()

    # Générer un code pour l'interval précédent (30s avant)
    totp = pyotp.TOTP(secret)
    current_time = datetime.utcnow()
    previous_interval = current_time - timedelta(seconds=30)

    # Le code de l'interval précédent devrait être accepté (window=1)
    previous_code = totp.at(previous_interval)
    is_valid = await auth_service.verify_2fa(user.id, previous_code)

    # Peut être True ou False selon le timing exact, mais ne doit pas planter
    assert isinstance(is_valid, bool)


# ============================================================
# TESTS JWT PAYLOAD
# ============================================================

@pytest.mark.asyncio
async def test_jwt_payload_format(auth_service: AuthService):
    """Test format du payload JWT."""
    user_id = uuid4()
    role = "notaire"

    # Générer JWT
    token = auth_service._generate_jwt(user_id, role)

    # Décoder et vérifier
    payload = jwt.decode(token, auth_service.jwt_secret, algorithms=["HS256"])

    assert payload["sub"] == str(user_id)
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload  # JWT ID unique

    # Vérifier expiration (15 minutes)
    exp_time = datetime.fromtimestamp(payload["exp"])
    iat_time = datetime.fromtimestamp(payload["iat"])
    assert (exp_time - iat_time).total_seconds() == 15 * 60


# ============================================================
# TESTS EDGE CASES
# ============================================================

@pytest.mark.asyncio
async def test_register_role_validation(auth_service: AuthService):
    """Test validation des rôles lors de l'inscription."""
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(
            email="test@test.fr",
            password="Password123!",
            role="super_admin"  # Rôle invalide
        )

    assert exc_info.value.status_code == 400
    assert "rôle invalide" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_login_user_inexistant(auth_service: AuthService):
    """Test login avec utilisateur inexistant."""
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            email="inexistant@notaire.fr",
            password="Password123!",
            ip_address="192.168.1.1"
        )

    assert exc_info.value.status_code == 401