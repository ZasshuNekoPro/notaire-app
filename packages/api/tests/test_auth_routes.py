"""
Tests d'intégration pour les routes d'authentification
ÉTAPE 1 — Tests avant implémentation (TDD)
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch
import redis.asyncio as redis
from httpx import AsyncClient
from fastapi.testclient import TestClient
import bcrypt
import jwt

from src.main import app
from src.models.auth import User, RefreshToken, AuditLog
from src.models.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


# ============================================================
# CONFIGURATION TEST
# ============================================================

TEST_DATABASE_URL = "postgresql+asyncpg://notaire:changeme_en_production@localhost:5432/notaire_app_test"
REDIS_TEST_URL = "redis://localhost:6379/1"

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
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        pytest.skip(f"Impossible de setup la DB de test: {e}")

    yield engine

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
    await client.flushdb()

    yield client

    await client.flushdb()
    await client.close()


@pytest.fixture
async def client(db_session, redis_client):
    """Client HTTP de test configuré."""
    # Mock des dépendances
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return redis_client

    app.dependency_overrides = {
        # Ces dépendances seront définies dans main.py
        "get_db": override_get_db,
        "get_redis": override_get_redis
    }

    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides = {}


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Utilisateur de test vérifié."""
    password_hash = bcrypt.hashpw("TestPassword123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="test@notaire.fr",
        password_hash=password_hash,
        role="notaire",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession):
    """Utilisateur admin de test."""
    password_hash = bcrypt.hashpw("AdminPassword123!".encode(), bcrypt.gensalt(rounds=12)).decode()
    user = User(
        email="admin@notaire.fr",
        password_hash=password_hash,
        role="admin",
        is_verified=True,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def jwt_secret():
    """Secret JWT pour les tests."""
    return "test_jwt_secret_minimum_32_characters_long"


@pytest.fixture
async def user_token(test_user, jwt_secret):
    """Token JWT valide pour l'utilisateur de test."""
    payload = {
        "sub": str(test_user.id),
        "role": test_user.role,
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "jti": str(uuid4())
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
async def admin_token(admin_user, jwt_secret):
    """Token JWT valide pour l'admin de test."""
    payload = {
        "sub": str(admin_user.id),
        "role": admin_user.role,
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "jti": str(uuid4())
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


# ============================================================
# TESTS REGISTRATION & LOGIN
# ============================================================

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    """Test flux complet inscription + connexion."""
    # 1. Inscription
    register_data = {
        "email": "nouveau@notaire.fr",
        "password": "MotDePasseSecure123!",
        "role": "notaire"
    }

    register_response = await client.post("/auth/register", json=register_data)
    assert register_response.status_code == 201

    register_result = register_response.json()
    assert register_result["email"] == "nouveau@notaire.fr"
    assert register_result["role"] == "notaire"
    assert register_result["is_active"] is True
    assert register_result["is_verified"] is False  # Pas encore vérifié
    assert "id" in register_result

    # 2. Tentative de connexion avec email non vérifié (doit échouer)
    login_data = {
        "email": "nouveau@notaire.fr",
        "password": "MotDePasseSecure123!"
    }

    login_response = await client.post("/auth/login", json=login_data)
    assert login_response.status_code == 403
    assert "vérifi" in login_response.json()["detail"].lower()

    # 3. Simuler vérification email (en production, via email + token)
    # Ici on modifie directement en DB pour le test
    # Cette partie sera implémentée dans un endpoint séparé

    # 4. Connexion après vérification (sera testée séparément)


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """Test connexion réussie."""
    login_data = {
        "email": "test@notaire.fr",
        "password": "TestPassword123!"
    }

    response = await client.post("/auth/login", json=login_data)
    assert response.status_code == 200

    result = response.json()
    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["expires_in"] == 900  # 15 minutes

    # Vérifier structure du JWT
    import jwt
    payload = jwt.decode(
        result["access_token"],
        "test_jwt_secret_minimum_32_characters_long",  # Secret test
        algorithms=["HS256"]
    )
    assert payload["sub"] == str(test_user.id)
    assert payload["role"] == "notaire"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, test_user):
    """Test échec connexion - identifiants invalides."""
    login_data = {
        "email": "test@notaire.fr",
        "password": "MauvaisMotDePasse"
    }

    response = await client.post("/auth/login", json=login_data)
    assert response.status_code == 401
    assert "invalide" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_account_lockout_after_5_failures(client: AsyncClient, test_user):
    """Test verrouillage compte après 5 tentatives échouées."""
    login_data = {
        "email": "test@notaire.fr",
        "password": "MauvaisMotDePasse"
    }

    # 5 tentatives échouées
    for i in range(5):
        response = await client.post("/auth/login", json=login_data)
        assert response.status_code == 401

    # 6ème tentative - compte verrouillé
    response = await client.post("/auth/login", json=login_data)
    assert response.status_code == 423
    assert "verrouillé" in response.json()["detail"].lower()

    # Même avec le bon mot de passe, compte toujours verrouillé
    correct_login = {
        "email": "test@notaire.fr",
        "password": "TestPassword123!"
    }
    response = await client.post("/auth/login", json=correct_login)
    assert response.status_code == 423


# ============================================================
# TESTS TOKEN REFRESH
# ============================================================

@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient, test_user, redis_client):
    """Test rafraîchissement token réussi."""
    # 1. Login pour obtenir refresh token
    login_response = await client.post("/auth/login", json={
        "email": "test@notaire.fr",
        "password": "TestPassword123!"
    })
    assert login_response.status_code == 200

    tokens = login_response.json()
    old_refresh_token = tokens["refresh_token"]

    # 2. Utiliser refresh token
    refresh_response = await client.post("/auth/refresh", json={
        "refresh_token": old_refresh_token
    })
    assert refresh_response.status_code == 200

    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != old_refresh_token  # Token rotation

    # 3. L'ancien refresh token ne doit plus marcher
    old_refresh_response = await client.post("/auth/refresh", json={
        "refresh_token": old_refresh_token
    })
    assert old_refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """Test refresh avec token invalide."""
    response = await client.post("/auth/refresh", json={
        "refresh_token": "token-invalide"
    })
    assert response.status_code == 401


# ============================================================
# TESTS LOGOUT
# ============================================================

@pytest.mark.asyncio
async def test_logout(client: AsyncClient, user_token):
    """Test déconnexion."""
    # Login pour obtenir refresh token
    login_response = await client.post("/auth/login", json={
        "email": "test@notaire.fr",
        "password": "TestPassword123!"
    })
    refresh_token = login_response.json()["refresh_token"]

    # Logout
    logout_response = await client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert logout_response.status_code == 200

    # Le refresh token ne doit plus marcher
    refresh_response = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_response.status_code == 401


# ============================================================
# TESTS 2FA
# ============================================================

@pytest.mark.asyncio
async def test_2fa_flow_complet(client: AsyncClient, user_token, test_user):
    """Test flux complet 2FA setup + vérification."""
    # 1. Setup 2FA
    setup_response = await client.post(
        "/auth/2fa/setup",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert setup_response.status_code == 200

    setup_data = setup_response.json()
    assert "secret" in setup_data
    assert "qr_code_uri" in setup_data
    assert "backup_codes" in setup_data
    assert "otpauth://totp/" in setup_data["qr_code_uri"]
    assert "Notaire App" in setup_data["qr_code_uri"]

    # 2. Vérifier avec code TOTP valide
    import pyotp
    totp = pyotp.TOTP(setup_data["secret"])
    valid_code = totp.now()

    verify_response = await client.post(
        "/auth/2fa/verify",
        json={"code": valid_code},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True

    # 3. Vérifier avec code invalide
    invalid_verify = await client.post(
        "/auth/2fa/verify",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert invalid_verify.status_code == 200
    assert invalid_verify.json()["valid"] is False


@pytest.mark.asyncio
async def test_2fa_setup_requires_auth(client: AsyncClient):
    """Test que setup 2FA nécessite une authentification."""
    response = await client.post("/auth/2fa/setup")
    assert response.status_code == 401


# ============================================================
# TESTS PROFIL UTILISATEUR
# ============================================================

@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, user_token, test_user):
    """Test récupération du profil utilisateur."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200

    profile = response.json()
    assert profile["id"] == str(test_user.id)
    assert profile["email"] == "test@notaire.fr"
    assert profile["role"] == "notaire"
    assert profile["is_active"] is True
    assert "password_hash" not in profile  # Sécurité


@pytest.mark.asyncio
async def test_get_profile_requires_auth(client: AsyncClient):
    """Test que le profil nécessite une authentification."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


# ============================================================
# TESTS RBAC (Role-Based Access Control)
# ============================================================

@pytest.mark.asyncio
async def test_rbac_forbidden(client: AsyncClient, user_token):
    """Test interdiction RBAC - utilisateur normal accédant aux endpoints admin."""
    # Tentative d'accès à la liste des utilisateurs (admin uniquement)
    response = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert "autorisation" in response.json()["detail"].lower() or "forbidden" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rbac_admin_access(client: AsyncClient, admin_token):
    """Test accès admin aux endpoints restreints."""
    response = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    # Doit réussir (200) ou retourner une liste vide, mais pas 403
    assert response.status_code in [200, 404]  # Pas 403


# ============================================================
# TESTS ENDPOINTS USERS (ADMIN)
# ============================================================

@pytest.mark.asyncio
async def test_list_users_admin_only(client: AsyncClient, admin_token, test_user, admin_user):
    """Test liste des utilisateurs (admin uniquement)."""
    response = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 2  # Au moins test_user et admin_user

    # Vérifier structure
    user = users[0]
    assert "id" in user
    assert "email" in user
    assert "role" in user
    assert "password_hash" not in user


@pytest.mark.asyncio
async def test_list_users_pagination(client: AsyncClient, admin_token):
    """Test pagination de la liste des utilisateurs."""
    response = await client.get(
        "/users?page=1&limit=10",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Structure de pagination attendue
    result = response.json()
    if isinstance(result, dict):
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "limit" in result


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient, admin_token, test_user):
    """Test récupération utilisateur par ID."""
    response = await client.get(
        f"/users/{test_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    user = response.json()
    assert user["id"] == str(test_user.id)
    assert user["email"] == test_user.email
    assert user["role"] == test_user.role


@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, admin_token, test_user):
    """Test modification du rôle utilisateur."""
    update_data = {
        "role": "clerc"
    }

    response = await client.patch(
        f"/users/{test_user.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    updated_user = response.json()
    assert updated_user["role"] == "clerc"


@pytest.mark.asyncio
async def test_get_user_audit_log(client: AsyncClient, admin_token, test_user):
    """Test récupération historique audit utilisateur."""
    response = await client.get(
        f"/users/{test_user.id}/audit",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    audit_logs = response.json()
    assert isinstance(audit_logs, list)
    # Il devrait y avoir au moins un log de création d'utilisateur


# ============================================================
# TESTS JWT VALIDATION
# ============================================================

@pytest.mark.asyncio
async def test_invalid_jwt_token(client: AsyncClient):
    """Test token JWT invalide."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer token-invalide"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_jwt_token(client: AsyncClient, test_user):
    """Test token JWT expiré."""
    # Créer un token expiré
    expired_payload = {
        "sub": str(test_user.id),
        "role": test_user.role,
        "exp": datetime.utcnow() - timedelta(minutes=1),  # Expiré
        "iat": datetime.utcnow() - timedelta(minutes=16),
        "jti": str(uuid4())
    }

    expired_token = jwt.encode(
        expired_payload,
        "test_jwt_secret_minimum_32_characters_long",
        algorithm="HS256"
    )

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_authorization_header(client: AsyncClient):
    """Test requête sans header Authorization."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


# ============================================================
# TESTS EDGE CASES
# ============================================================

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    """Test inscription avec email déjà existant."""
    register_data = {
        "email": "test@notaire.fr",  # Email déjà existant
        "password": "AutreMotDePasse123!",
        "role": "client"
    }

    response = await client.post("/auth/register", json=register_data)
    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_register_invalid_role(client: AsyncClient):
    """Test inscription avec rôle invalide."""
    register_data = {
        "email": "invalid@notaire.fr",
        "password": "MotDePasse123!",
        "role": "super_admin"  # Rôle invalide
    }

    response = await client.post("/auth/register", json=register_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Test inscription avec mot de passe faible."""
    register_data = {
        "email": "weak@notaire.fr",
        "password": "123",  # Trop court
        "role": "client"
    }

    response = await client.post("/auth/register", json=register_data)
    assert response.status_code == 400