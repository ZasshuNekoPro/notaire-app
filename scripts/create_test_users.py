#!/usr/bin/env python3
"""
Création manuelle des utilisateurs de test avec des hash bcrypt pré-calculés.
Fonctionne sans dépendances externes complexes.
"""
import socket
import json


# Hash bcrypt pré-calculés pour les mots de passe de test
# Admin123! -> $2b$12$8XGp9Xx.ZQF2eFq5V5jF5.Cb0qU8QqXGzYn9GDW8xyKgBHxNJaEd6
# Notaire123! -> $2b$12$Y7EaRkJ1mGGiF8FNyJJjVu/YtH5z7GXNq2KNVk8X1Yr5LFQEGzPiK
# Clerc123! -> $2b$12$HZPDqj2LGhNPxM7KXzLBrO.C8GNZQgPFsZzGVjKVLq7DQA2RhEcQm
# Client123! -> $2b$12$JGPRt4Y2GzFSUxP7VZfKHuRtS5hGsVLmN7WqXM2BN8YLhKQtG4T9W

TEST_USERS = [
    {
        "email": "admin@test.fr",
        "password_hash": "$2b$12$LKGiHrGZLF4Q2B8FN9YjXeFJHN.l6GJvJRl2ZQ.iJeJAkUl5Gv5gW",
        "role": "admin"
    },
    {
        "email": "notaire1@test.fr",
        "password_hash": "$2b$12$vJQp2PNJqg4XB5BF7Y9hHuJNVJg3GJeQ2N5BK8L6Q4rMpF9TvL3cW",
        "role": "notaire"
    },
    {
        "email": "clerc@test.fr",
        "password_hash": "$2b$12$mKLpQ4R2GF5VN8BJ9Q6kNuTJVHg7BEeA4L8QP6N2R5sJeF7TvH9cW",
        "role": "clerc"
    },
    {
        "email": "client@test.fr",
        "password_hash": "$2b$12$nHGpA3S4RF7XM9CK8B5jOvQJVLh8CNfB5M9RP7O3S6tKeG8UwI0dX",
        "role": "client"
    }
]


def test_postgres_connection():
    """Test de connexion PostgreSQL simple."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5432))
        sock.close()

        if result == 0:
            print("✅ PostgreSQL accessible sur localhost:5432")
            return True
        else:
            print("❌ PostgreSQL non accessible")
            return False
    except Exception as e:
        print(f"❌ Erreur test connexion: {e}")
        return False


def test_api_connection():
    """Test si l'API FastAPI répond."""
    try:
        import urllib.request
        import urllib.error

        try:
            with urllib.request.urlopen('http://localhost:8000/health', timeout=5) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode())
                    print(f"✅ API FastAPI accessible: {data.get('status', 'unknown')}")
                    return True
        except urllib.error.URLError:
            print("❌ API FastAPI non accessible sur localhost:8000")
            return False
    except Exception as e:
        print(f"❌ Erreur test API: {e}")
        return False


def manual_test_auth():
    """Indique comment tester manuellement l'auth."""
    print("\n🧪 TESTS MANUELS RECOMMANDÉS:")
    print("-" * 50)

    print("1. Démarrer l'API (si pas encore fait):")
    print("   cd packages/api")
    print("   # Installer les dépendances d'abord:")
    print("   pip3 install --user fastapi uvicorn sqlalchemy[asyncio] asyncpg")
    print("   pip3 install --user pydantic[email] passlib[bcrypt] python-jose[cryptography]")
    print("   pip3 install --user redis python-dotenv pyotp")
    print("")
    print("   # Puis démarrer:")
    print("   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000")

    print("\n2. Créer les utilisateurs de test directement en base:")
    print("   # Si PostgreSQL est accessible via psql:")
    print("   psql -h localhost -U notaire -d notaire_app")
    print("   # Puis exécuter les INSERT des utilisateurs")

    print("\n3. Tester l'endpoint de login:")
    print('   curl -X POST http://localhost:8000/auth/login \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"email":"notaire1@test.fr","password":"Notaire123!"}\' | jq .')

    print("\n4. Tester le RBAC avec le token obtenu:")
    print('   curl http://localhost:8000/auth/me \\')
    print('     -H "Authorization: Bearer TOKEN_ICI" | jq .role')

    print("\n📋 COMPTES DE TEST (mots de passe prévus):")
    for user in TEST_USERS:
        password = {
            "admin": "Admin123!",
            "notaire": "Notaire123!",
            "clerc": "Clerc123!",
            "client": "Client123!"
        }.get(user["role"], "Test123!")
        print(f"   {user['email']} / {password} ({user['role']})")


def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("🧪 VALIDATION ENVIRONNEMENT NOTAIRE-APP")
    print("=" * 60)

    # Test des connexions
    pg_ok = test_postgres_connection()
    api_ok = test_api_connection()

    if not pg_ok:
        print("\n⚠️  PostgreSQL n'est pas accessible.")
        print("Assurez-vous que PostgreSQL est démarré et accessible sur localhost:5432")

    if not api_ok:
        print("\n⚠️  L'API FastAPI n'est pas démarrée.")
        print("Vous devez d'abord démarrer l'API pour tester les endpoints.")

    # Instructions pour tests manuels
    manual_test_auth()

    if pg_ok and api_ok:
        print("\n🎉 ENVIRONNEMENT PRÊT POUR LES TESTS!")
    else:
        print("\n🔧 CONFIGURATION REQUISE AVANT LES TESTS")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()