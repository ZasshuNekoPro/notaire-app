"""
Tests end-to-end — Parcours complets utilisateur.
Lancer : pytest tests/e2e/ -v
"""
import pytest
import httpx
import asyncio
import os

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

@pytest.fixture
async def notaire_token():
    """Retourne un token JWT pour le compte notaire de test."""
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/auth/login",
            json={"email": "notaire1@test.fr", "password": "Notaire123!"})
        assert r.status_code == 200, f"Login échoué : {r.text}"
        return r.json()["access_token"]


@pytest.mark.asyncio
async def test_health():
    """L'API répond correctement."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_parcours_estimation(notaire_token):
    """Scénario complet : login → créer dossier → soumettre estimation."""
    headers = {"Authorization": f"Bearer {notaire_token}"}
    async with httpx.AsyncClient() as client:
        # Estimation
        r = await client.post(f"{BASE_URL}/estimations/analyse", headers=headers, json={
            "adresse": "8 Avenue de l'Opéra, 75001 Paris",
            "type_bien": "Appartement",
            "surface_m2": 65,
            "nb_pieces": 3,
        })
        assert r.status_code == 200
        data = r.json()
        assert "prix_m2_median" in data or "estimation" in data
        print(f"  ✅ Estimation reçue : {data}")


@pytest.mark.asyncio
async def test_auth_lockout():
    """Vérification du verrouillage après 5 tentatives échouées."""
    async with httpx.AsyncClient() as client:
        for i in range(5):
            r = await client.post(f"{BASE_URL}/auth/login",
                json={"email": "notaire1@test.fr", "password": "mauvais_mot_de_passe"})
            assert r.status_code in [401, 423]
        # La 6ème tentative doit retourner 423 (compte verrouillé)
        r = await client.post(f"{BASE_URL}/auth/login",
            json={"email": "notaire1@test.fr", "password": "mauvais_mot_de_passe"})
        assert r.status_code == 423, "Le compte devrait être verrouillé"
        print("  ✅ Verrouillage compte fonctionnel")
