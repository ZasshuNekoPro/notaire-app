# Backend API — Conventions

## Stack
FastAPI 0.115 + SQLAlchemy async + Pydantic v2 + PostgreSQL

## Structure d'un module
```
src/models/nom.py    → SQLAlchemy (UUID, timestamps)
src/schemas/nom.py   → Pydantic Create/Response/Update
src/services/nom.py  → logique métier async
src/routers/nom.py   → routes HTTP + RBAC
tests/test_nom.py    → pytest + httpx.AsyncClient
```

## Règles
- Toujours async, session via Depends(get_db)
- Schémas séparés : Create ≠ Response ≠ Update
- RBAC sur toutes les routes sensibles
- Logger les interactions IA dans ai_interactions
- Toute interaction LLM → get_ai_provider() de ai-core
- Tests AVANT l'implémentation

## Modules existants
- auth.py — JWT, refresh tokens, 2FA TOTP
- users.py — RBAC admin
- estimations.py — DVF + analyse IA
- dossiers.py — gestion dossiers notariaux
- successions.py — dossiers succession
- juridique.py — RAG + rédaction actes
- alertes.py + WebSocket — veille temps réel
- signatures.py — signature électronique eIDAS

## Lancer les tests
```bash
pytest tests/ -v --tb=short
```
