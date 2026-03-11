"""
NOTAIRE APP — Point d'entrée FastAPI
Lancer : uvicorn src.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Notaire App API",
    version="0.1.0",
    description="API pour l'application notariale IA"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

# Les routers seront ajoutés ici par Claude Code :
# from src.routers import auth, users, estimations, dossiers, actes, successions, alertes
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
