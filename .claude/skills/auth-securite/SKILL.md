---
name: auth-securite
description: Implémentation sécurisée de l'authentification JWT, RBAC, 2FA TOTP, et audit log pour une application notariale. Active quand l'utilisateur travaille sur le module auth, la gestion des tokens JWT, le contrôle d'accès par rôle, le 2FA, ou quand il pose des questions sur la sécurité du backend. Active aussi pour les questions sur le verrouillage de compte, les refresh tokens, ou la conformité RGPD pour une étude notariale.
allowed-tools: Bash, Read, Write
---

# Auth & Sécurité — Notaire App

## Architecture JWT

```
Login (email + password)
    ↓ verify password (bcrypt)
    ↓ générer access_token (JWT, 15 min)
    ↓ générer refresh_token (UUID, 7 jours, stocké Redis hashé)
    → retourner TokenPair

Requête API protégée
    ↓ Authorization: Bearer <access_token>
    ↓ verify_jwt() → payload { sub, role, exp, jti }
    ↓ require_role() → vérifier role autorisé
    → continuer

Refresh
    ↓ POST /auth/refresh { refresh_token }
    ↓ vérifier en Redis (non révoqué, non expiré)
    ↓ rotation : révoquer l'ancien, émettre nouveau
    → nouveau TokenPair
```

## Payload JWT

```python
payload = {
    "sub": str(user.id),        # user UUID
    "role": user.role,          # admin|notaire|clerc|client
    "exp": datetime.utcnow() + timedelta(minutes=15),
    "iat": datetime.utcnow(),
    "jti": str(uuid4()),        # JWT ID unique (pour révocation)
}
```

## RBAC — Matrice des permissions

| Ressource | admin | notaire | clerc | client |
|-----------|-------|---------|-------|--------|
| Users (lecture) | ✅ | ❌ | ❌ | ❌ |
| Users (écriture) | ✅ | ❌ | ❌ | ❌ |
| Dossiers (tous) | ✅ | ses dossiers | assignés | ses dossiers |
| Estimations | ✅ | ✅ | ✅ | ❌ |
| Succession (calcul) | ✅ | ✅ | ❌ | ❌ |
| Documents (upload) | ✅ | ✅ | ✅ | lecture seule |
| Alertes | ✅ | ✅ | lecture | ❌ |
| Admin panel | ✅ | ❌ | ❌ | ❌ |

## Protection brute-force

```python
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=30)

async def check_and_increment_failures(user: User, db: AsyncSession):
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(423, "Compte verrouillé. Réessayez dans 30 minutes.")

    user.failed_login_count += 1
    if user.failed_login_count >= MAX_ATTEMPTS:
        user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
    await db.commit()
```

## 2FA TOTP

```python
import pyotp

# Génération du secret
secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)

# QR code URI (pour Google Authenticator)
uri = totp.provisioning_uri(
    name=user.email,
    issuer_name="Notaire App"
)

# Vérification
is_valid = totp.verify(code_saisi, valid_window=1)
```

## Règles de sécurité absolues

1. **Jamais de mot de passe en clair** : bcrypt rounds=12 minimum
2. **Refresh tokens hashés** : stocker SHA256(token) dans Redis
3. **HTTPS uniquement** en production (Caddy gère ça)
4. **Audit log obligatoire** pour toute action sensible
5. **Rate limiting** : max 10 req/min sur /auth/login
6. **CORS strict** : whitelist des origines dans .env
