#!/usr/bin/env python3
"""
Script de test et démonstration du pipeline RAG

Ce script permet de :
1. Initialiser le schéma de base
2. Tester l'ingestion de données légales simulées
3. Tester la recherche vectorielle
4. Tester la génération de réponses

Usage :
    python scripts/test_rag_pipeline.py --help
    python scripts/test_rag_pipeline.py --init-schema
    python scripts/test_rag_pipeline.py --test-ingestion
    python scripts/test_rag_pipeline.py --test-search "droits de succession"
    python scripts/test_rag_pipeline.py --full-demo
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path

# Ajouter le package à Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.data_pipeline.src.ingest_legal import LegalIngestionService, LegalChunk
from packages.ai_core.src.rag.notaire_rag import NotaireRAG


class RAGTester:
    """Testeur du pipeline RAG"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://notaire:changeme_en_production@localhost:5432/notaire_app")
        self.ingestion_service = LegalIngestionService(self.db_url)
        self.rag = NotaireRAG(self.db_url)

    async def init_schema(self):
        """Initialise le schéma de base de données"""
        print("🗄️ Initialisation du schéma RAG...")

        try:
            conn = await self.ingestion_service.init_database()
            await conn.close()
            print("✅ Schéma initialisé avec succès")
        except Exception as e:
            print(f"❌ Erreur initialisation schéma : {e}")
            return False

        return True

    async def test_ingestion_demo(self):
        """Teste l'ingestion avec des données simulées"""
        print("📥 Test d'ingestion avec données simulées...")

        # Créer des chunks de test
        demo_chunks = [
            LegalChunk(
                source="Code civil art.734",
                source_type="loi",
                content="""Article 734 du Code civil : Les libéralités sont les actes par lesquels une personne dispose à titre gratuit de tout ou partie de ses biens ou de ses droits au profit d'autrui. Elles ne peuvent avoir lieu qu'entre vifs, par donation, ou pour cause de mort, par testament, dans les formes ci-après établies.""",
                metadata={"article": 734, "code": "civil", "titre": "Des libéralités"}
            ),
            LegalChunk(
                source="Code civil art.720",
                source_type="loi",
                content="""Article 720 du Code civil : Les successions s'ouvrent par la mort, au dernier domicile du défunt. L'héritier recueille la succession, sous réserve de l'exercice de l'option prévue aux articles 804 et suivants, à compter du décès et sans désemparer.""",
                metadata={"article": 720, "code": "civil", "titre": "De l'ouverture des successions"}
            ),
            LegalChunk(
                source="BOFIP ENR-3169",
                source_type="bofip",
                content="""Les droits de succession sont dus par les héritiers et légataires lors de la transmission d'un patrimoine à la suite d'un décès. Le taux applicable dépend du lien de parenté entre le défunt et le bénéficiaire. Les enfants bénéficient d'un abattement de 100 000 euros.""",
                metadata={"page": "ENR-3169", "section": "Calcul des droits"}
            ),
            LegalChunk(
                source="Code civil art.777",
                source_type="loi",
                content="""Article 777 du Code civil : Les enfants ou leurs descendants succèdent à leurs père et mère ou autres ascendants, sans distinction de sexe ni de primogéniture, et encore qu'ils soient issus d'unions différentes.""",
                metadata={"article": 777, "code": "civil", "titre": "Des successions dévolues par la loi"}
            )
        ]

        try:
            # Simuler l'embedding pipeline
            conn = await self.ingestion_service.init_database()

            # Pour le test, on utilise des embeddings simulés
            chunks_with_embeddings = []
            for chunk in demo_chunks:
                # Embedding simulé (768 dimensions)
                fake_embedding = [0.1 + i * 0.01 for i in range(768)]
                chunks_with_embeddings.append((chunk, fake_embedding))

            # Stocker en base
            inserted = await self.ingestion_service.store_chunks(conn, chunks_with_embeddings)
            await conn.close()

            print(f"✅ {inserted} chunks de démonstration insérés")
            return True

        except Exception as e:
            print(f"❌ Erreur ingestion : {e}")
            return False

    async def test_search(self, query: str):
        """Teste la recherche vectorielle"""
        print(f"🔍 Test de recherche : '{query}'")

        try:
            # Récupérer les stats
            stats = await self.rag.get_stats()
            print(f"📊 Base de connaissances : {stats}")

            # Note : pour un vrai test, il faudrait un provider Ollama fonctionnel
            # Ici on simule juste la structure
            print("⚠️  Test de recherche nécessite Ollama configuré")
            print("   Vous pouvez tester avec : docker run -d -p 11434:11434 ollama/ollama")

            return True

        except Exception as e:
            print(f"❌ Erreur recherche : {e}")
            return False

    async def test_full_rag_query(self, question: str):
        """Teste le pipeline RAG complet"""
        print(f"🤖 Test RAG complet : '{question}'")

        try:
            # Ceci nécessite Ollama + provider IA configuré
            response = await self.rag.query(question)

            print(f"📝 Réponse : {response.answer}")
            print(f"📚 Sources trouvées : {len(response.sources)}")
            print(f"🎯 Confiance : {response.confidence:.2f}")
            print(f"⏱️  Temps total : {response.query_embedding_time_ms + response.search_time_ms + response.generation_time_ms:.1f}ms")

            return True

        except Exception as e:
            print(f"❌ Erreur RAG : {e}")
            print("💡 Assurez-vous que Ollama et le provider IA sont configurés")
            return False

    async def demo_complet(self):
        """Démonstration complète du pipeline"""
        print("🎭 === DÉMONSTRATION PIPELINE RAG NOTAIRE ===\n")

        # 1. Initialisation
        success = await self.init_schema()
        if not success:
            return

        print()

        # 2. Ingestion de données de test
        success = await self.test_ingestion_demo()
        if not success:
            return

        print()

        # 3. Test de recherche
        await self.test_search("droits de succession")

        print()

        # 4. Test RAG complet (si services disponibles)
        questions_test = [
            "Comment calculer les droits de succession ?",
            "Qui hérite en ligne directe ?",
            "Quels sont les abattements applicables ?"
        ]

        for question in questions_test:
            print()
            await self.test_full_rag_query(question)

        print("\n🎉 Démonstration terminée !")


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Testeur du pipeline RAG notarial")

    parser.add_argument("--init-schema", action="store_true",
                       help="Initialise le schéma de base de données")
    parser.add_argument("--test-ingestion", action="store_true",
                       help="Teste l'ingestion avec des données simulées")
    parser.add_argument("--test-search", metavar="QUERY",
                       help="Teste la recherche vectorielle")
    parser.add_argument("--test-rag", metavar="QUESTION",
                       help="Teste le pipeline RAG complet")
    parser.add_argument("--full-demo", action="store_true",
                       help="Lance la démonstration complète")
    parser.add_argument("--db-url", metavar="URL",
                       help="URL de connexion PostgreSQL")

    args = parser.parse_args()

    if not any([args.init_schema, args.test_ingestion, args.test_search,
                args.test_rag, args.full_demo]):
        parser.print_help()
        return

    # Créer le testeur
    tester = RAGTester(args.db_url)

    try:
        if args.init_schema:
            await tester.init_schema()

        if args.test_ingestion:
            await tester.test_ingestion_demo()

        if args.test_search:
            await tester.test_search(args.test_search)

        if args.test_rag:
            await tester.test_full_rag_query(args.test_rag)

        if args.full_demo:
            await tester.demo_complet()

    except KeyboardInterrupt:
        print("\n⚠️  Interruption utilisateur")
    except Exception as e:
        print(f"\n💥 Erreur inattendue : {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Vérifier les dépendances
    try:
        import asyncpg
        import aiohttp
    except ImportError as e:
        print(f"❌ Dépendance manquante : {e}")
        print("💡 Installez avec : pip install asyncpg aiohttp")
        sys.exit(1)

    # Lancer le testeur
    asyncio.run(main())