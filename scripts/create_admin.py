#!/usr/bin/env python3
"""
Création d'un compte administrateur.
Usage : python scripts/create_admin.py --email admin@etude.fr --password MonMotDePasse123
"""

import asyncio
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
import bcrypt
from datetime import datetime


async def create_admin(email: str, password: str, database_url: str):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    conn = await asyncpg.connect(database_url.replace("+asyncpg", ""))
    try:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if existing:
            print(f"⚠️  Un utilisateur avec l'email {email} existe déjà.")
            return

        user_id = await conn.fetchval("""
            INSERT INTO users (email, password_hash, role, is_active, is_verified)
            VALUES ($1, $2, 'admin', true, true)
            RETURNING id
        """, email, password_hash)

        print(f"\n✅ Compte administrateur créé !")
        print(f"   Email    : {email}")
        print(f"   Rôle     : admin")
        print(f"   ID       : {user_id}")
        print(f"\n   Connectez-vous sur http://localhost:3000\n")
    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Créer un compte administrateur")
    parser.add_argument("--email",    required=True, help="Email de l'administrateur")
    parser.add_argument("--password", required=True, help="Mot de passe (min 8 caractères)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ Le mot de passe doit contenir au moins 8 caractères")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "postgresql://notaire:changeme@localhost:5432/notaire_app")
    await create_admin(args.email, args.password, database_url)


if __name__ == "__main__":
    asyncio.run(main())
