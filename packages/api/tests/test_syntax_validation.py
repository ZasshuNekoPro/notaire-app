"""
Tests de validation syntaxique et structurelle
Vérifie que le code est bien formé sans dépendances externes
"""
import ast
import os
import sys
from pathlib import Path


def test_python_syntax_models():
    """Test que tous les fichiers modèles ont une syntaxe Python valide."""
    models_dir = Path(__file__).parent.parent / "src" / "models"

    for py_file in models_dir.glob("*.py"):
        print(f"Vérification syntaxe: {py_file.name}")

        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            # Parser le contenu pour vérifier la syntaxe
            ast.parse(content)
            print(f"✅ {py_file.name}: Syntaxe valide")
        except SyntaxError as e:
            print(f"❌ {py_file.name}: Erreur syntaxe ligne {e.lineno}: {e.msg}")
            raise


def test_python_syntax_schemas():
    """Test que tous les fichiers schémas ont une syntaxe Python valide."""
    schemas_dir = Path(__file__).parent.parent / "src" / "schemas"

    for py_file in schemas_dir.glob("*.py"):
        print(f"Vérification syntaxe: {py_file.name}")

        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            ast.parse(content)
            print(f"✅ {py_file.name}: Syntaxe valide")
        except SyntaxError as e:
            print(f"❌ {py_file.name}: Erreur syntaxe ligne {e.lineno}: {e.msg}")
            raise


def test_auth_models_structure():
    """Test la structure des modèles d'auth."""
    auth_models_path = Path(__file__).parent.parent / "src" / "models" / "auth.py"

    with open(auth_models_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)

    # Trouver toutes les classes
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    class_names = [cls.name for cls in classes]

    print(f"Classes trouvées: {class_names}")

    # Vérifier que nos 3 modèles sont présents
    expected_classes = ["User", "RefreshToken", "AuditLog"]
    for expected in expected_classes:
        assert expected in class_names, f"Classe {expected} manquante"
        print(f"✅ Classe {expected} présente")


def test_auth_schemas_structure():
    """Test la structure des schémas d'auth."""
    auth_schemas_path = Path(__file__).parent.parent / "src" / "schemas" / "auth.py"

    with open(auth_schemas_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)

    # Trouver toutes les classes
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    class_names = [cls.name for cls in classes]

    print(f"Schémas trouvés: {class_names}")

    # Vérifier les schémas principaux
    expected_schemas = [
        "UserCreate", "UserLogin", "UserResponse", "UserUpdate",
        "TokenPair", "RefreshRequest", "LoginResponse"
    ]

    for expected in expected_schemas:
        assert expected in class_names, f"Schéma {expected} manquant"
        print(f"✅ Schéma {expected} présent")


def test_alembic_configuration():
    """Test que la configuration Alembic est présente et valide."""
    alembic_ini = Path(__file__).parent.parent / "alembic.ini"

    assert alembic_ini.exists(), "Fichier alembic.ini manquant"
    print("✅ alembic.ini présent")

    with open(alembic_ini, 'r') as f:
        content = f.read()

    # Vérifications basiques
    assert "script_location = migrations" in content
    assert "sqlalchemy.url" in content
    print("✅ Configuration Alembic valide")

    # Vérifier que le répertoire migrations existe
    migrations_dir = Path(__file__).parent.parent / "migrations"
    assert migrations_dir.exists(), "Répertoire migrations manquant"
    print("✅ Répertoire migrations présent")

    # Vérifier env.py
    env_py = migrations_dir / "env.py"
    assert env_py.exists(), "Fichier migrations/env.py manquant"
    print("✅ migrations/env.py présent")


def test_requirements_completeness():
    """Test que requirements.txt contient les dépendances essentielles."""
    requirements_path = Path(__file__).parent.parent / "requirements.txt"

    assert requirements_path.exists(), "requirements.txt manquant"

    with open(requirements_path, 'r') as f:
        content = f.read()

    # Dépendances critiques
    essential_deps = [
        "fastapi", "sqlalchemy", "asyncpg", "alembic",
        "pydantic", "passlib", "python-jose", "pyotp",
        "pytest", "pytest-asyncio"
    ]

    for dep in essential_deps:
        assert dep in content, f"Dépendance {dep} manquante"
        print(f"✅ Dépendance {dep} présente")


if __name__ == "__main__":
    print("🔍 TESTS DE VALIDATION STRUCTURELLE")
    print("=" * 50)

    try:
        print("\n📝 Test syntaxe modèles...")
        test_python_syntax_models()

        print("\n📝 Test syntaxe schémas...")
        test_python_syntax_schemas()

        print("\n🏗️  Test structure modèles auth...")
        test_auth_models_structure()

        print("\n📋 Test structure schémas auth...")
        test_auth_schemas_structure()

        print("\n⚙️  Test configuration Alembic...")
        test_alembic_configuration()

        print("\n📦 Test requirements.txt...")
        test_requirements_completeness()

        print("\n✅ TOUS LES TESTS PASSENT!")
        print("🚀 L'implémentation TDD est structurellement valide")

    except Exception as e:
        print(f"\n❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)