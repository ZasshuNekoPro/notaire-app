"""
Modèle Dossier pour les successions.
Modèle minimal pour permettre la FK dans les tests.
"""
from typing import Optional, List
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Dossier(BaseModel, Base):
    """
    Dossier notarial.
    Modèle minimal pour permettre la FK succession.dossier_id.
    """
    __tablename__ = "dossiers"

    # Numéro de dossier
    numero: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    # Type de dossier
    type_dossier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="succession"
    )

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relation avec les successions
    successions: Mapped[List["Succession"]] = relationship(
        "Succession",
        back_populates="dossier",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Dossier {self.numero}>"