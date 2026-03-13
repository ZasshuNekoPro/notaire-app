"""
Routers FastAPI pour l'API notaire-app
"""
from . import auth, users, estimations, successions, veille, notifications, alertes

__all__ = [
    "auth",
    "users",
    "estimations",
    "successions",
    "veille",
    "notifications",
    "alertes",
]