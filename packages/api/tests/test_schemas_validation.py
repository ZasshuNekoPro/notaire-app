"""
Tests de validation des schémas Pydantic
Simule la validation des données d'entrée/sortie
"""
import json
import re
from datetime import datetime, timedelta
from uuid import uuid4


# ============================================================
# SIMULATION DES SCHÉMAS PYDANTIC (sans dépendances)
# ============================================================

class MockUserCreate:
    """Simulation du schéma UserCreate."""

    def __init__(self, email: str, password: str, role: str = "client"):
        # Validation email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Email invalide")

        # Validation mot de passe
        if len(password) < 8:
            raise ValueError("Mot de passe trop court (minimum 8 caractères)")
        if len(password) > 128:
            raise ValueError("Mot de passe trop long (maximum 128 caractères)")

        # Validation rôle
        if role not in ["admin", "notaire", "clerc", "client"]:
            raise ValueError(f"Rôle invalide: {role}")

        self.email = email.strip()
        self.password = password
        self.role = role


class MockUserLogin:
    """Simulation du schéma UserLogin."""

    def __init__(self, email: str, password: str, totp_code: str = None):
        # Validation email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Email invalide")

        # Validation mot de passe
        if len(password) < 1:
            raise ValueError("Mot de passe requis")

        # Validation code TOTP si fourni
        if totp_code and not re.match(r'^\d{6}$', totp_code):
            raise ValueError("Code TOTP doit être 6 chiffres")

        self.email = email.strip()
        self.password = password
        self.totp_code = totp_code


class MockUserResponse:
    """Simulation du schéma UserResponse."""

    def __init__(self, user_data: dict):
        required_fields = [
            'id', 'email', 'role', 'is_active', 'is_verified',
            'totp_enabled', 'failed_login_count', 'created_at', 'updated_at'
        ]

        for field in required_fields:
            if field not in user_data:
                raise ValueError(f"Champ requis manquant: {field}")

        # Validation des types
        if not isinstance(user_data['is_active'], bool):
            raise ValueError("is_active doit être un booléen")

        self.__dict__.update(user_data)


class MockTokenPair:
    """Simulation du schéma TokenPair."""

    def __init__(self, access_token: str, refresh_token: str, expires_in: int):
        if not access_token:
            raise ValueError("Access token requis")
        if not refresh_token:
            raise ValueError("Refresh token requis")
        if expires_in <= 0:
            raise ValueError("expires_in doit être positif")

        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.token_type = "bearer"


class MockPasswordChangeRequest:
    """Simulation du schéma PasswordChangeRequest."""

    def __init__(self, current_password: str, new_password: str, new_password_confirm: str):
        if not current_password:
            raise ValueError("Mot de passe actuel requis")

        if len(new_password) < 8:
            raise ValueError("Nouveau mot de passe trop court")

        if new_password != new_password_confirm:
            raise ValueError("Les mots de passe ne correspondent pas")

        self.current_password = current_password
        self.new_password = new_password
        self.new_password_confirm = new_password_confirm


# ============================================================
# TESTS DES SCHÉMAS
# ============================================================

def test_user_create_schema():
    """Test du schéma UserCreate."""
    print("Test schéma UserCreate...")

    # Données valides
    valid_data = MockUserCreate(
        email="notaire@etude.fr",
        password="SecurePass123!",
        role="notaire"
    )
    assert valid_data.email == "notaire@etude.fr"
    assert valid_data.role == "notaire"
    print("✅ UserCreate valide")

    # Email invalide
    try:
        MockUserCreate("email-invalide", "password123", "client")
        raise AssertionError("Email invalide accepté")
    except ValueError:
        print("✅ Email invalide rejeté")

    # Mot de passe trop court
    try:
        MockUserCreate("test@test.fr", "123", "client")
        raise AssertionError("Mot de passe trop court accepté")
    except ValueError:
        print("✅ Mot de passe trop court rejeté")

    # Rôle invalide
    try:
        MockUserCreate("test@test.fr", "password123", "super_user")
        raise AssertionError("Rôle invalide accepté")
    except ValueError:
        print("✅ Rôle invalide rejeté")


def test_user_login_schema():
    """Test du schéma UserLogin."""
    print("Test schéma UserLogin...")

    # Login classique
    login_basic = MockUserLogin(
        email="user@test.fr",
        password="motdepasse"
    )
    assert login_basic.totp_code is None
    print("✅ Login basique OK")

    # Login avec 2FA
    login_2fa = MockUserLogin(
        email="user@test.fr",
        password="motdepasse",
        totp_code="123456"
    )
    assert login_2fa.totp_code == "123456"
    print("✅ Login avec 2FA OK")

    # Code TOTP invalide
    try:
        MockUserLogin("user@test.fr", "pass", "abc123")
        raise AssertionError("Code TOTP invalide accepté")
    except ValueError:
        print("✅ Code TOTP invalide rejeté")


def test_user_response_schema():
    """Test du schéma UserResponse."""
    print("Test schéma UserResponse...")

    # Données complètes
    user_data = {
        'id': str(uuid4()),
        'email': 'response@test.fr',
        'role': 'clerc',
        'is_active': True,
        'is_verified': False,
        'totp_enabled': True,
        'failed_login_count': 0,
        'locked_until': None,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    response = MockUserResponse(user_data)
    assert response.email == 'response@test.fr'
    assert response.is_active is True
    print("✅ UserResponse complet OK")

    # Champ manquant
    incomplete_data = user_data.copy()
    del incomplete_data['role']

    try:
        MockUserResponse(incomplete_data)
        raise AssertionError("Données incomplètes acceptées")
    except ValueError:
        print("✅ Champ manquant détecté")


def test_token_pair_schema():
    """Test du schéma TokenPair."""
    print("Test schéma TokenPair...")

    # Tokens valides
    tokens = MockTokenPair(
        access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        refresh_token=str(uuid4()),
        expires_in=900
    )

    assert tokens.token_type == "bearer"
    assert tokens.expires_in == 900
    print("✅ TokenPair valide")

    # expires_in invalide
    try:
        MockTokenPair("token", "refresh", -1)
        raise AssertionError("expires_in négatif accepté")
    except ValueError:
        print("✅ expires_in invalide rejeté")


def test_password_change_schema():
    """Test du schéma PasswordChangeRequest."""
    print("Test schéma PasswordChangeRequest...")

    # Changement valide
    change_request = MockPasswordChangeRequest(
        current_password="ancien_password",
        new_password="nouveau_password_123",
        new_password_confirm="nouveau_password_123"
    )
    print("✅ Changement mot de passe valide")

    # Mots de passe non correspondants
    try:
        MockPasswordChangeRequest(
            current_password="ancien",
            new_password="nouveau1",
            new_password_confirm="nouveau2"
        )
        raise AssertionError("Mots de passe différents acceptés")
    except ValueError:
        print("✅ Mots de passe non correspondants rejetés")


def test_realistic_data_scenarios():
    """Test avec des données réalistes du domaine notarial."""
    print("Test données réalistes notariales...")

    # Création compte notaire
    notaire = MockUserCreate(
        email="maitre.dupont@notaire-paris.fr",
        password="NotaireSecure2024!",
        role="notaire"
    )
    assert "@notaire-" in notaire.email
    print("✅ Compte notaire créé")

    # Création compte clerc
    clerc = MockUserCreate(
        email="j.martin@etude-dupont.fr",
        password="ClercPassword123",
        role="clerc"
    )
    assert clerc.role == "clerc"
    print("✅ Compte clerc créé")

    # Login avec 2FA (notaire)
    login_secure = MockUserLogin(
        email="maitre.dupont@notaire-paris.fr",
        password="NotaireSecure2024!",
        totp_code="456789"
    )
    assert login_secure.totp_code == "456789"
    print("✅ Login sécurisé 2FA")

    # Réponse utilisateur complète
    user_response_data = {
        'id': str(uuid4()),
        'email': 'maitre.dupont@notaire-paris.fr',
        'role': 'notaire',
        'is_active': True,
        'is_verified': True,
        'totp_enabled': True,
        'failed_login_count': 0,
        'locked_until': None,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    user_response = MockUserResponse(user_response_data)
    assert user_response.totp_enabled is True
    print("✅ Profil notaire avec 2FA")

    # Changement mot de passe
    password_change = MockPasswordChangeRequest(
        current_password="NotaireSecure2024!",
        new_password="NotaireSecure2025@",
        new_password_confirm="NotaireSecure2025@"
    )
    print("✅ Changement mot de passe sécurisé")


def test_edge_cases():
    """Test des cas limites."""
    print("Test cas limites...")

    # Email avec caractères spéciaux
    email_special = MockUserCreate(
        email="jean-claude.van@etude-martin.fr",
        password="password123",
        role="clerc"
    )
    print("✅ Email avec tirets accepté")

    # Mot de passe exactement 8 caractères
    pwd_min = MockUserCreate(
        email="test@test.fr",
        password="12345678",  # Exactement 8
        role="client"
    )
    print("✅ Mot de passe minimum accepté")

    # Code TOTP avec zéros
    login_totp_zeros = MockUserLogin(
        email="test@test.fr",
        password="password",
        totp_code="000123"
    )
    assert login_totp_zeros.totp_code == "000123"
    print("✅ Code TOTP avec zéros OK")


if __name__ == "__main__":
    print("📋 TESTS DE VALIDATION SCHÉMAS PYDANTIC")
    print("=" * 55)

    try:
        test_user_create_schema()
        print()

        test_user_login_schema()
        print()

        test_user_response_schema()
        print()

        test_token_pair_schema()
        print()

        test_password_change_schema()
        print()

        test_realistic_data_scenarios()
        print()

        test_edge_cases()
        print()

        print("✅ TOUS LES TESTS DE SCHÉMAS PASSENT!")
        print("🚀 Validation des données d'entrée/sortie OK")

    except Exception as e:
        print(f"\n❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        exit(1)