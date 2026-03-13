"""
NOTAIRE APP — Point d'entrée FastAPI
Lancer : uvicorn src.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import redis.asyncio as redis

from .models.base import Base
from .routers import auth, users, estimations, successions, veille, notifications, alertes, signatures
from .scheduler import demarrer_scheduler_veille, arreter_scheduler_veille


# ============================================================
# CONFIGURATION BASE DE DONNÉES
# ============================================================

# URL de base de données depuis .env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://notaire:changeme_en_production@localhost:5432/notaire_app"
)

# URL Redis depuis .env
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Créer l'engine SQLAlchemy
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("API_DEBUG", "false").lower() == "true",
    pool_size=10,
    max_overflow=20
)

# Créer le sessionmaker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ============================================================
# DÉPENDANCES
# ============================================================

async def get_db() -> AsyncSession:
    """
    Dépendance pour obtenir une session de base de données.

    Yields:
        AsyncSession: Session de base de données SQLAlchemy
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    """
    Dépendance pour obtenir un client Redis.

    Yields:
        redis.Redis: Client Redis configuré
    """
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


# ============================================================
# GESTION DU CYCLE DE VIE
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion du cycle de vie de l'application.

    Args:
        app: Instance FastAPI
    """
    # Startup
    try:
        # Test de connexion à la base de données
        async with engine.begin() as conn:
            # Optionnel : créer les tables si elles n'existent pas
            # await conn.run_sync(Base.metadata.create_all)
            pass

        # Test de connexion Redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()

        # Démarrer le scheduler de veille automatique
        try:
            await demarrer_scheduler_veille()
            print("✅ Scheduler de veille démarré")
        except Exception as e:
            print(f"⚠️ Erreur démarrage scheduler veille: {e}")

        print("✅ Connexions DB, Redis et scheduler établis")

    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        raise

    yield

    # Shutdown
    try:
        await arreter_scheduler_veille()
        print("✅ Scheduler de veille arrêté")
    except Exception as e:
        print(f"⚠️ Erreur arrêt scheduler: {e}")

    await engine.dispose()
    print("✅ Connexions fermées proprement")


# ============================================================
# APPLICATION FASTAPI
# ============================================================

app = FastAPI(
    title="Notaire App API",
    version="0.1.0",
    description="""
    ## API pour l'application notariale IA

    Cette API fournit :
    - 🔐 **Authentification** : JWT + refresh tokens + 2FA
    - 👥 **Gestion utilisateurs** : RBAC avec rôles notariaux
    - 📊 **Estimation immobilière** : Données DVF + IA
    - ⚖️ **Succession** : Calculs fiscaux automatisés
    - 📄 **RAG juridique** : Assistant rédaction d'actes
    - 🚨 **Veille automatique** : Surveillance DVF, Légifrance, BOFIP

    ### Authentification
    Utilisez un token Bearer JWT dans le header `Authorization: Bearer <token>`.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================================
# MIDDLEWARE
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTES
# ============================================================

@app.get(
    "/health",
    summary="Statut de l'API",
    description="Vérifie la santé de l'API et des services connectés.",
    tags=["Système"]
)
async def health_check():
    """Endpoint de santé global."""
    from datetime import datetime

    try:
        # Test DB
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        # Test Redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    overall_status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return {
        "status": overall_status,
        "version": "0.1.0",
        "timestamp": datetime.utcnow(),
        "services": {
            "database": db_status,
            "redis": redis_status
        }
    }


# ============================================================
# ENREGISTREMENT DES ROUTERS
# ============================================================

# Override des dépendances dans les routers
# Cela permet aux routers d'utiliser nos vraies dépendances
auth.router.dependency_overrides.update({
    "get_db": get_db,
    "get_redis": get_redis
})

users.router.dependency_overrides.update({
    "get_db": get_db
})

estimations.router.dependency_overrides.update({
    "get_db": get_db,
    "get_redis": get_redis
})

successions.router.dependency_overrides.update({
    "get_db": get_db
})

veille.router.dependency_overrides.update({
    "get_db": get_db
})

notifications.router.dependency_overrides.update({
    "get_db": get_db
})

alertes.router.dependency_overrides.update({
    "get_db": get_db
})

signatures.router.dependency_overrides.update({
    "get_db": get_db
})

# Enregistrement des routers
app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentification"]
)

app.include_router(
    users.router,
    prefix="/users",
    tags=["Gestion des utilisateurs"]
)

app.include_router(
    estimations.router,
    prefix="/estimations",
    tags=["Estimation immobilière"]
)

app.include_router(
    successions.router,
    prefix="/successions",
    tags=["Succession"]
)

app.include_router(
    veille.router,
    prefix="/veille",
    tags=["Veille automatique"]
)

app.include_router(
    notifications.router,
    tags=["WebSocket Notifications"]
)

app.include_router(
    alertes.router,
    prefix="/alertes",
    tags=["Alertes temps réel"]
)

app.include_router(
    signatures.router,
    prefix="/signatures",
    tags=["Signature électronique"]
)

# TODO: Ajouter d'autres routers quand ils seront implémentés
# app.include_router(dossiers.router, prefix="/dossiers", tags=["Dossiers"])
# app.include_router(juridique.router, prefix="/juridique", tags=["RAG Juridique"])


# ============================================================
# ENDPOINTS RACINE
# ============================================================

@app.get(
    "/",
    summary="Informations de l'API",
    description="Informations générales sur l'API notariale.",
    tags=["Système"]
)
async def root():
    """Endpoint racine avec informations de l'API."""
    return {
        "name": "Notaire App API",
        "version": "0.1.0",
        "description": "API pour l'application notariale IA",
        "endpoints": {
            "auth": "/auth/",
            "users": "/users/",
            "estimations": "/estimations/",
            "successions": "/successions/",
            "veille": "/veille/",
            "alertes": "/alertes/",
            "signatures": "/signatures/",
            "websocket": "/ws/notifications",
            "docs": "/docs",
            "health": "/health"
        },
        "features": [
            "Authentification JWT + 2FA",
            "Gestion utilisateurs RBAC",
            "Estimation immobilière DVF",
            "Calculs de succession",
            "RAG juridique",
            "Alertes légales",
            "Signature électronique"
        ]
    }
