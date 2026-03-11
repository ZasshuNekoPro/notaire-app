#!/usr/bin/env python3
"""
Seed de données de développement.
Crée des comptes de test, clients et dossiers fictifs.
Usage : python scripts/seed_dev.py
"""

import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
import random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
import bcrypt
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://notaire:changeme@localhost:5432/notaire_app").replace("+asyncpg", "")

USERS = [
    {"email": "admin@test.fr",    "password": "Admin123!",   "role": "admin",    "nom": "Admin Système"},
    {"email": "notaire1@test.fr", "password": "Notaire123!", "role": "notaire",  "nom": "Me Dupont Marie"},
    {"email": "notaire2@test.fr", "password": "Notaire123!", "role": "notaire",  "nom": "Me Martin Pierre"},
    {"email": "clerc@test.fr",    "password": "Clerc123!",   "role": "clerc",    "nom": "Leclerc Sophie"},
    {"email": "client@test.fr",   "password": "Client123!",  "role": "client",   "nom": "Durand Jean"},
]

CLIENTS = [
    {"nom": "Durand",   "prenom": "Jean",    "email": "jean.durand@example.fr",   "telephone": "0612345678"},
    {"nom": "Bernard",  "prenom": "Marie",   "email": "marie.bernard@example.fr", "telephone": "0623456789"},
    {"nom": "Moreau",   "prenom": "Paul",    "email": "paul.moreau@example.fr",   "telephone": "0634567890"},
]

TRANSACTIONS_TEST = [
    {"type_bien": "Appartement", "surface_m2": 45, "prix_vente": 360000, "code_postal": "75008", "commune": "Paris 8e", "departement": "75", "nb_pieces": 2},
    {"type_bien": "Appartement", "surface_m2": 65, "prix_vente": 520000, "code_postal": "75008", "commune": "Paris 8e", "departement": "75", "nb_pieces": 3},
    {"type_bien": "Appartement", "surface_m2": 85, "prix_vente": 680000, "code_postal": "75008", "commune": "Paris 8e", "departement": "75", "nb_pieces": 4},
    {"type_bien": "Appartement", "surface_m2": 38, "prix_vente": 295000, "code_postal": "75011", "commune": "Paris 11e","departement": "75", "nb_pieces": 1},
    {"type_bien": "Appartement", "surface_m2": 72, "prix_vente": 576000, "code_postal": "75011", "commune": "Paris 11e","departement": "75", "nb_pieces": 3},
    {"type_bien": "Maison",      "surface_m2": 120,"prix_vente": 850000, "code_postal": "92200", "commune": "Neuilly",  "departement": "92", "nb_pieces": 5},
    {"type_bien": "Maison",      "surface_m2": 95, "prix_vente": 620000, "code_postal": "92200", "commune": "Neuilly",  "departement": "92", "nb_pieces": 4},
]


async def seed():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("\n🌱 Seed des données de développement...\n")

        # Utilisateurs
        user_ids = {}
        for u in USERS:
            pwd_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt(rounds=10)).decode()
            uid = await conn.fetchval("""
                INSERT INTO users (email, password_hash, role, is_active, is_verified)
                VALUES ($1, $2, $3, true, true)
                ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
                RETURNING id
            """, u["email"], pwd_hash, u["role"])
            user_ids[u["email"]] = uid
            print(f"  ✅ {u['role'].capitalize():10} : {u['email']} / {u['password']}")

        # Clients
        client_ids = []
        for c in CLIENTS:
            cid = await conn.fetchval("""
                INSERT INTO clients (nom, prenom, email, telephone)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (email) DO UPDATE SET nom = EXCLUDED.nom
                RETURNING id
            """, c["nom"], c["prenom"], c["email"], c["telephone"])
            client_ids.append(cid)

        # Dossiers
        notaire_id = user_ids.get("notaire1@test.fr")
        types = [("vente", "en_cours"), ("succession", "en_cours"), ("donation", "signe"), ("vente", "signe")]
        for i, (client_id, (type_acte, statut)) in enumerate(zip(client_ids + [client_ids[0]], types)):
            ref = f"2025-{str(i+1).zfill(4)}"
            await conn.execute("""
                INSERT INTO dossiers (reference, type_acte, statut, client_id, notaire_id, description)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (reference) DO NOTHING
            """, ref, type_acte, statut, client_id, notaire_id,
                f"Dossier de test {type_acte} - {ref}")

        # Transactions DVF de test
        base_date = date.today() - timedelta(days=180)
        for i, t in enumerate(TRANSACTIONS_TEST):
            t_date = base_date + timedelta(days=random.randint(0, 180))
            prix_m2 = int(t["prix_vente"] / t["surface_m2"])
            await conn.execute("""
                INSERT INTO transactions
                (date_vente, prix_vente, prix_m2, surface_m2, type_bien, nb_pieces,
                 code_postal, commune, departement, latitude, longitude, nature_mutation)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'Vente')
                ON CONFLICT DO NOTHING
            """, t_date, t["prix_vente"], prix_m2, t["surface_m2"], t["type_bien"],
                t["nb_pieces"], t["code_postal"], t["commune"], t["departement"],
                48.87 + random.uniform(-0.02, 0.02), 2.30 + random.uniform(-0.02, 0.02))

        print(f"\n  ✅ {len(client_ids)} clients créés")
        print(f"  ✅ {len(types)} dossiers créés")
        print(f"  ✅ {len(TRANSACTIONS_TEST)} transactions DVF de test insérées")
        print("\n🎉 Seed terminé ! Vous pouvez vous connecter sur http://localhost:3000\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
