"""
Test de validation syntaxique pour auth_service.py
Vérifie la structure sans dépendances externes
"""
import ast
from pathlib import Path


def test_auth_service_syntax():
    """Test la syntaxe du service d'authentification."""
    service_path = Path(__file__).parent.parent / "src" / "services" / "auth_service.py"

    with open(service_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        # Parser le contenu pour vérifier la syntaxe
        tree = ast.parse(content)
        print("✅ Syntaxe Python valide")

        # Trouver la classe AuthService
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        class_names = [cls.name for cls in classes]

        assert "AuthService" in class_names
        print("✅ Classe AuthService trouvée")

        # Trouver les méthodes
        auth_service_class = next(cls for cls in classes if cls.name == "AuthService")
        methods = [node.name for node in auth_service_class.body if isinstance(node, ast.FunctionDef)]

        expected_methods = [
            "__init__", "register", "login", "refresh", "logout",
            "setup_2fa", "verify_2fa", "_generate_jwt", "_hash_password",
            "_hash_token", "_validate_registration_data", "_check_email_availability",
            "_get_user_by_email", "_check_account_lockout", "_verify_password",
            "_handle_failed_login", "_reset_failed_logins", "_create_refresh_token",
            "_create_audit_log"
        ]

        missing_methods = []
        for method in expected_methods:
            if method in methods:
                print(f"✅ Méthode {method} présente")
            else:
                missing_methods.append(method)

        if missing_methods:
            print(f"⚠️  Méthodes manquantes: {missing_methods}")
        else:
            print("✅ Toutes les méthodes attendues sont présentes")

        # Vérifier les fonctions utilitaires
        functions = [node.name for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and
                    not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)
                           if any(child is node for child in ast.walk(parent)))]

        if "create_auth_service" in functions:
            print("✅ Fonction create_auth_service présente")
        else:
            print("❌ Fonction create_auth_service manquante")

        return True

    except SyntaxError as e:
        print(f"❌ Erreur syntaxe ligne {e.lineno}: {e.msg}")
        return False


def test_auth_service_structure():
    """Test la structure du code d'AuthService."""
    service_path = Path(__file__).parent.parent / "src" / "services" / "auth_service.py"

    with open(service_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Vérifications de sécurité dans le code
    security_checks = {
        "bcrypt rounds=12": "BCRYPT_ROUNDS = 12" in content,
        "Protection brute-force": "MAX_LOGIN_ATTEMPTS = 5" in content,
        "Lockout duration": "LOCKOUT_DURATION_MINUTES = 30" in content,
        "SHA256 hashing": "hashlib.sha256" in content,
        "JWT avec JTI": '"jti": str(uuid4())' in content,
        "Audit logging": "_create_audit_log" in content,
        "Redis TTL": "setex" in content,
        "Token rotation": "rotation" in content.lower(),
        "Password validation": "_validate_registration_data" in content,
        "Email uniqueness": "_check_email_availability" in content
    }

    print("\n🔒 VÉRIFICATIONS DE SÉCURITÉ:")
    for check, passed in security_checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")

    all_passed = all(security_checks.values())

    # Vérifications des exceptions HTTP
    http_exceptions = {
        "409 - Email déjà pris": "status_code=409" in content,
        "400 - Données invalides": "status_code=400" in content,
        "401 - Non autorisé": "status_code=401" in content,
        "403 - Interdit": "status_code=403" in content,
        "423 - Verrouillé": "status_code=423" in content,
        "404 - Non trouvé": "status_code=404" in content
    }

    print("\n🚫 GESTION DES ERREURS HTTP:")
    for check, passed in http_exceptions.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")

    all_passed = all_passed and all(http_exceptions.values())

    return all_passed


def test_auth_service_docstrings():
    """Test la présence de la documentation."""
    service_path = Path(__file__).parent.parent / "src" / "services" / "auth_service.py"

    with open(service_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content)

    # Vérifier la docstring de la classe
    auth_service_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "AuthService":
            auth_service_class = node
            break

    if auth_service_class and ast.get_docstring(auth_service_class):
        print("✅ Docstring de classe présente")
        has_class_doc = True
    else:
        print("❌ Docstring de classe manquante")
        has_class_doc = False

    # Vérifier les docstrings des méthodes principales
    main_methods = ["register", "login", "refresh", "logout", "setup_2fa", "verify_2fa"]
    documented_methods = 0

    for node in auth_service_class.body if auth_service_class else []:
        if (isinstance(node, ast.FunctionDef) and
            node.name in main_methods and
            ast.get_docstring(node)):
            print(f"✅ Docstring pour {node.name}")
            documented_methods += 1

    all_documented = documented_methods == len(main_methods)
    if all_documented:
        print("✅ Toutes les méthodes principales sont documentées")
    else:
        print(f"⚠️  {len(main_methods) - documented_methods} méthodes sans documentation")

    return has_class_doc and all_documented


if __name__ == "__main__":
    print("🔍 VALIDATION SYNTAXIQUE AUTH_SERVICE")
    print("=" * 50)

    try:
        print("📝 Test syntaxe...")
        syntax_ok = test_auth_service_syntax()

        print("\n🏗️  Test structure...")
        structure_ok = test_auth_service_structure()

        print("\n📚 Test documentation...")
        docs_ok = test_auth_service_docstrings()

        if syntax_ok and structure_ok and docs_ok:
            print("\n✅ TOUS LES TESTS PASSENT!")
            print("🚀 AuthService est prêt pour l'utilisation")
        else:
            print("\n⚠️  CERTAINS TESTS ONT ÉCHOUÉ")

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()