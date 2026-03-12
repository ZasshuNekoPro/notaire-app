"""
Middleware FastAPI pour l'API notaire-app
"""
from .auth_middleware import (
    get_current_user,
    get_current_user_optional,
    require_role,
    require_admin,
    require_notaire_or_admin,
    require_staff,
    require_authenticated,
    RBACPermissions,
    oauth2_scheme
)

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "require_role",
    "require_admin",
    "require_notaire_or_admin",
    "require_staff",
    "require_authenticated",
    "RBACPermissions",
    "oauth2_scheme",
]