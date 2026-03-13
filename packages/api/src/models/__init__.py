"""
Modèles SQLAlchemy pour l'API notaire-app
"""
from .base import Base, BaseModel
from .auth import User, RefreshToken, AuditLog
from .dossiers import Dossier
from .succession import (
    Succession, Heritier, ActifSuccessoral, PassifSuccessoral,
    StatutTraitement, LienParente, TypeActif
)
from .veille import (
    VeilleRule, Alerte, HistoriqueVeille,
    TypeSource, NiveauImpact, StatutAlerte
)

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "RefreshToken",
    "AuditLog",
    "Dossier",
    "Succession",
    "Heritier",
    "ActifSuccessoral",
    "PassifSuccessoral",
    "StatutTraitement",
    "LienParente",
    "TypeActif",
    "VeilleRule",
    "Alerte",
    "HistoriqueVeille",
    "TypeSource",
    "NiveauImpact",
    "StatutAlerte",
]