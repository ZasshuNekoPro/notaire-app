# Roadmap Notaire App

## Phase 0 — Initialisation ✅
- [x] Lancement Claude Code sur le projet
- [x] Structure monorepo packages/
- [x] Docker compose PostgreSQL + Redis

## Phase 1 — Auth & Utilisateurs ✅
- [x] JWT + refresh tokens
- [x] RBAC (admin/notaire/clerc/client)
- [x] 2FA TOTP
- [x] Audit log des actions sensibles
- [x] Modèles SQLAlchemy User/Etude/AuditLog
- [ ] OAuth2 (Google, Microsoft) — optionnel

## Phase 2 — Estimation Immobilière ✅
- [x] Import DVF avec pipeline data-pipeline
- [x] API estimation avec IA
- [x] Géocodage BAN + analyse comparable
- [x] Routeur /estimations avec démo
- [ ] Carte interactive frontend — prochaine

## Phase 3 — RAG Juridique ✅
- [x] Ingestion Légifrance + BOFIP
- [x] Service RAG + pgvector embeddings
- [x] Table knowledge_chunks + index vectoriel
- [x] Assistant recherche juridique
- [ ] Interface frontend RAG — prochaine

## Phase 4 — Succession IA ✅
- [x] Modèles succession/héritiers/actifs
- [x] Moteur calcul fiscal (barèmes 2025)
- [x] Création automatique par IA (upload docs)
- [x] Routeur /successions avec tests TDD
- [ ] Interface frontend succession — prochaine

## Phase 5 — Veille Automatique ✅
- [x] Moteur de veille DVF/Légifrance/BOFIP
- [x] APScheduler + VeilleEngine
- [x] Alertes WebSocket temps réel
- [x] Routeur /alertes + notifications
- [ ] Configuration veille frontend — prochaine

## Phase 6 — Signature Électronique ✅
- [x] Provider abstraction (BaseSignatureProvider)
- [x] YousignProvider + SignatureSimuleeProvider
- [x] Routeur /signatures avec upload PDF
- [x] Webhook callbacks + statut temps réel
- [ ] Interface frontend signature — prochaine

## Phase 7 — Frontend Next.js ✅ (NOUVELLE)
- [x] Architecture Next.js 14 + TypeScript strict
- [x] Client API axios avec auto-refresh JWT
- [x] AuthProvider + contexte authentification
- [x] Composants UI : Button, Card, Input, Badge, Toast, Spinner
- [x] Layout responsive avec sidebar navigation
- [x] Page dashboard avec démo composants

## Phase 8 — Frontend Pages Métier (EN COURS)
- [ ] Pages login/register avec formulaires
- [ ] Interface estimation immobilière + carte
- [ ] Interface gestion dossiers + succession
- [ ] Interface signature électronique
- [ ] Interface alertes + configuration veille
- [ ] Interface RAG juridique + recherche

## Phase 9 — Déploiement & Production
- [ ] Docker images optimisées
- [ ] CI/CD GitHub Actions
- [ ] Monitoring Sentry + métriques
- [ ] HTTPS + certificats Let's Encrypt
- [ ] Backup automatique BDD
