#!/usr/bin/env python3
"""
Schémas Pydantic pour les actes notariaux
"""
from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class TypeActe(str, Enum):
    """Types d'actes supportés"""
    VENTE = "VENTE"
    SUCCESSION = "SUCC"
    DONATION = "DON"
    TESTAMENT = "TEST"
    SCI = "SCI"
    PACS = "PACS"
    MARIAGE = "MARIAGE"
    BAIL = "BAIL"


class StyleRedaction(str, Enum):
    """Styles de rédaction disponibles"""
    FORMEL = "formel"
    SIMPLIFIE = "simplifie"


class AnalyserActeRequest(BaseModel):
    """Requête d'analyse d'acte"""
    type_acte: TypeActe = Field(description="Type d'acte à analyser")
    elements: Dict[str, Any] = Field(description="Éléments de l'acte fournis")

    @validator('elements')
    def elements_not_empty(cls, v):
        if not v:
            raise ValueError("Les éléments de l'acte ne peuvent pas être vides")
        return v


class AnalyseActeResponse(BaseModel):
    """Résultat d'analyse d'acte"""
    structure_suggeree: List[str] = Field(description="Structure recommandée pour l'acte")
    clauses_manquantes: List[str] = Field(description="Clauses obligatoires manquantes")
    points_attention: List[str] = Field(description="Points nécessitant attention")
    annexes_requises: List[str] = Field(description="Annexes ou documents requis")
    articles_loi: List[str] = Field(description="Articles de loi applicables")


class RedigerActeRequest(BaseModel):
    """Requête de rédaction d'acte"""
    type_acte: TypeActe = Field(description="Type d'acte à rédiger")
    elements: Dict[str, Any] = Field(description="Éléments de l'acte")
    style: StyleRedaction = Field(default=StyleRedaction.FORMEL, description="Style de rédaction")

    @validator('elements')
    def elements_not_empty(cls, v):
        if not v:
            raise ValueError("Les éléments de l'acte ne peuvent pas être vides")
        return v


class RelireActeRequest(BaseModel):
    """Requête de relecture d'acte"""
    contenu_acte: str = Field(min_length=50, description="Contenu de l'acte à relire")
    type_acte: TypeActe = Field(description="Type d'acte")


class CorrectionActe(BaseModel):
    """Une correction suggérée"""
    ligne: Optional[int] = Field(default=None, description="Numéro de ligne concerné")
    type: str = Field(description="Type de correction (grammaire, juridique, etc.)")
    message: str = Field(description="Description de la correction")
    suggestion: Optional[str] = Field(default=None, description="Texte de remplacement suggéré")


class RisqueJuridique(BaseModel):
    """Un risque juridique identifié"""
    niveau: Literal["faible", "moyen", "élevé"] = Field(description="Niveau de risque")
    description: str = Field(description="Description du risque")
    consequence: str = Field(description="Conséquence possible")
    solution: Optional[str] = Field(default=None, description="Solution recommandée")


class RelectureActeResponse(BaseModel):
    """Résultat de relecture d'acte"""
    score_completude: int = Field(ge=0, le=100, description="Score de complétude (0-100)")
    corrections: List[CorrectionActe] = Field(description="Corrections suggérées")
    risques_juridiques: List[RisqueJuridique] = Field(description="Risques juridiques identifiés")
    clauses_manquantes: List[str] = Field(description="Clauses manquantes importantes")