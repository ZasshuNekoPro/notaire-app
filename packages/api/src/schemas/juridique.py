#!/usr/bin/env python3
"""
Schémas Pydantic pour les endpoints juridiques
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID


class QuestionJuridiqueRequest(BaseModel):
    """Requête de consultation juridique RAG"""
    question: str = Field(min_length=5, max_length=1000, description="Question juridique")
    source_types: Optional[List[str]] = Field(
        default=None,
        description="Types de sources à filtrer (loi, bofip, jurisprudence, acte_type)"
    )
    dossier_id: Optional[UUID] = Field(
        default=None,
        description="ID du dossier pour sauvegarder l'interaction"
    )


class QuestionJuridiqueResponse(BaseModel):
    """Réponse de consultation juridique"""
    model_config = ConfigDict(from_attributes=True)

    reponse: str = Field(description="Réponse juridique générée")
    sources_citees: List[str] = Field(description="Sources légales citées")
    confiance: float = Field(ge=0.0, le=1.0, description="Score de confiance (0-1)")
    avertissements: List[str] = Field(default=[], description="Avertissements éventuels")


class StatistiquesJuridiques(BaseModel):
    """Statistiques de la base de connaissances juridiques"""
    total_chunks: int = Field(description="Nombre total de chunks juridiques")
    by_source_type: dict = Field(description="Répartition par type de source")