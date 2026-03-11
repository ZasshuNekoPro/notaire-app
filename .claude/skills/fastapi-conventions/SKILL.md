---
name: fastapi-conventions
description: Conventions et patterns FastAPI pour le backend notaire-app. Active quand l'utilisateur travaille dans packages/api/, crée des routes FastAPI, des modèles SQLAlchemy, des schémas Pydantic, des services async, ou questionne sur les conventions du projet backend. Active aussi pour les migrations Alembic, la gestion des sessions DB, ou les tests pytest avec httpx.
user-invocable: false
---

# FastAPI — Conventions Backend Notaire App

## Structure d'un module complet

```
packages/api/src/
├── models/nom_module.py      # SQLAlchemy (BDD)
├── schemas/nom_module.py     # Pydantic (validation)
├── services/nom_module.py    # Logique métier
├── routers/nom_module.py     # Routes HTTP
└── tests/test_nom_module.py  # Tests pytest
```

## Pattern modèle SQLAlchemy

```python
# models/exemple.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base
import uuid

class Exemple(Base):
    __tablename__ = "exemples"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom        = Column(String(100), nullable=False)
    metadata   = Column(JSONB, default={})
    created_at = Column(DateTime, server_default="NOW()")
    updated_at = Column(DateTime, server_default="NOW()", onupdate="NOW()")
```

## Pattern schéma Pydantic v2

```python
# schemas/exemple.py
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime

class ExempleBase(BaseModel):
    nom: str
    metadata: dict = {}

class ExempleCreate(ExempleBase):
    pass

class ExempleResponse(ExempleBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
```

## Pattern service async

```python
# services/exemple_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_by_id(db: AsyncSession, item_id: UUID) -> Exemple | None:
    result = await db.execute(select(Exemple).where(Exemple.id == item_id))
    return result.scalar_one_or_none()

async def create(db: AsyncSession, data: ExempleCreate) -> Exemple:
    item = Exemple(**data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
```

## Pattern route avec auth RBAC

```python
# routers/exemple.py
from fastapi import APIRouter, Depends, HTTPException
from middleware.auth_middleware import require_role, get_current_user

router = APIRouter(prefix="/exemples", tags=["exemples"])

@router.post("/", response_model=ExempleResponse,
             dependencies=[Depends(require_role("notaire", "admin"))])
async def create_exemple(
    data: ExempleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await exemple_service.create(db, data)
```

## Règles absolues

1. **Toujours async** : toutes les fonctions de route et service
2. **Session DB via Depends** : jamais de session globale
3. **Schémas séparés** : Create / Response / Update distincts
4. **Erreurs HTTP explicites** : raise HTTPException avec detail clair
5. **Tests avant implémentation** : générer les tests en premier
6. **Pas de logique dans les routes** : déléguer aux services

## Test type

```python
# tests/test_exemple.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_exemple(client: AsyncClient, notaire_token: str):
    response = await client.post(
        "/exemples/",
        json={"nom": "Test"},
        headers={"Authorization": f"Bearer {notaire_token}"}
    )
    assert response.status_code == 201
    assert response.json()["nom"] == "Test"
```
