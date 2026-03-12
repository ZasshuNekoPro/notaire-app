"""
Services métier pour l'API notaire-app
"""
from .auth_service import AuthService, create_auth_service

__all__ = [
    "AuthService",
    "create_auth_service",
]