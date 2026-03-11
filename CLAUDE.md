# 🏛️ Notaire App — Contexte Global

## Vision
Application IA notariale : estimation immobilière DVF + RAG juridique + succession automatique + veille temps réel.

## Stack
- Backend : FastAPI + PostgreSQL/pgvector + Redis
- Frontend : Next.js 14 + Tailwind
- IA : Multi-provider (Claude / GPT-4o / Ollama local)
- Data : DVF open data + Légifrance + BOFIP

## Règles critiques (lire avant tout)
1. **Toute interaction IA → `ai-core/src/providers/`** (jamais d'appel direct)
2. **Tests avant implémentation** (TDD obligatoire)
3. **Une session = un module** (ne pas mélanger les packages)
4. **Fichiers < 300 lignes** (scinder si dépassé)
5. **/compact à 50% de contexte** (éviter la "dumb zone")

## Packages → CLAUDE.md détaillés
- `packages/api/CLAUDE.md` — conventions FastAPI, RBAC, services
- `packages/ai-core/CLAUDE.md` — providers IA, RAG, prompts
- `packages/web/CLAUDE.md` — conventions Next.js, composants
- `packages/data-pipeline/CLAUDE.md` — DVF, Légifrance, geocodage

## Skills disponibles (chargés automatiquement)
- `notaire-domain` — droit notarial, barèmes succession, actes
- `dvf-pipeline` — import DVF, bulk insert, estimation
- `rag-juridique` — embeddings, pgvector, ingestion légale
- `succession-fiscale` — calculs fiscaux, extraction IA
- `fastapi-conventions` — patterns API backend
- `pgvector-rag` — optimisation vectorielle
- `auth-securite` — JWT, RBAC, 2FA
- `ai-provider` — factory multi-provider

## Commands disponibles
- `/demarrage-projet` — initialiser une session (TOUJOURS en premier)
- `/phase-estimation` — workflow Phase 2 DVF
- `/phase-rag` — workflow Phase 3 RAG juridique
- `/phase-succession` — workflow Phase 4 succession IA
- `/commit-session` — finaliser et commiter

## Sources open data
- DVF : https://files.data.gouv.fr/geo-dvf/
- Légifrance : https://api.piste.gouv.fr
- BOFIP : https://bofip.impots.gouv.fr
- BAN : https://api-adresse.data.gouv.fr

## Agents spécialisés
- `data-engineer` — pipeline DVF + ingestion légale
- `backend-notaire` — API FastAPI + métier
- `rag-specialist` — RAG + pgvector
- `succession-analyst` — calculs fiscaux
