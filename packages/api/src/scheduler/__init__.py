"""
Module scheduler pour les tâches automatisées.
Contient le scheduler de veille et autres tâches périodiques.
"""
from .veille_scheduler import (
    VeilleScheduler,
    demarrer_scheduler_veille,
    arreter_scheduler_veille,
    get_scheduler
)

__all__ = [
    "VeilleScheduler",
    "demarrer_scheduler_veille",
    "arreter_scheduler_veille",
    "get_scheduler"
]