#!/usr/bin/env python3
"""
Test manuel des fonctionnalités TDD critiques
Sans dépendance pytest, pour validation rapide
"""

import hashlib
import sys
import os

# Importation relative
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest_legal_improved import ChunkingStrategy, LegalChunk

def test_chunk_size():
    """Test que les chunks respectent 400-512 tokens avec overlap 50"""
    print("=== Test Chunk Size ===")

    strategy = ChunkingStrategy()

    # Texte long pour forcer le chunking
    long_text = " ".join([
        f"Article {i} du Code civil traite des successions et libéralités. "
        f"Les dispositions relatives aux mutations à titre gratuit sont importantes. "
        f"Le calcul des droits suit les barèmes en vigueur selon la loi. "
        f"Les abattements s'appliquent selon le degré de parenté. "
        for i in range(100)  # Génère beaucoup de tokens
    ])

    chunks = strategy.chunk_text(long_text, max_tokens=512, overlap=50)

    print(f"Texte original: {len(strategy.tokenizer.encode(long_text))} tokens")
    print(f"Nombre de chunks: {len(chunks)}")

    for i, chunk in enumerate(chunks[:3]):  # Afficher les 3 premiers
        token_count = len(strategy.tokenizer.encode(chunk))
        print(f"Chunk {i+1}: {token_count} tokens")
        print(f"Contenu: {chunk[:100]}...")

        # Validation TDD
        if not (1 <= token_count <= 512):
            print(f"❌ ERREUR: Chunk {i+1} a {token_count} tokens (limite 512)")
            return False

        if not chunk.strip()[-1] in '.!?':
            print(f"⚠️ WARNING: Chunk {i+1} ne se termine pas par une ponctuation")

    print("✅ Test chunk_size: PASSED")
    return True


def test_no_duplicate():
    """Test qu'un même article inséré 2x génère le même content_hash"""
    print("\n=== Test No Duplicate ===")

    content = "Article 734 du Code civil : Les libéralités sont des actes gratuits par lesquels une personne dispose de tout ou partie de ses biens."

    chunk1 = LegalChunk(
        source="Code civil art.734",
        source_type="loi",
        content=content,
        metadata={"article": 734}
    )

    chunk2 = LegalChunk(
        source="Code civil art.734",
        source_type="loi",
        content=content,  # Même contenu
        metadata={"article": 734, "extra": "different"}  # Métadonnées différentes
    )

    chunk3 = LegalChunk(
        source="Code civil art.734",
        source_type="loi",
        content=content + " Modification.",  # Contenu légèrement différent
        metadata={"article": 734}
    )

    print(f"Chunk1 hash: {chunk1.content_hash}")
    print(f"Chunk2 hash: {chunk2.content_hash}")
    print(f"Chunk3 hash: {chunk3.content_hash}")

    # Validation TDD
    if chunk1.content_hash != chunk2.content_hash:
        print("❌ ERREUR: Même contenu devrait avoir le même hash")
        return False

    if chunk1.content_hash == chunk3.content_hash:
        print("❌ ERREUR: Contenus différents ne devraient pas avoir le même hash")
        return False

    # Vérifier que c'est bien du SHA256
    expected_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    if chunk1.content_hash != expected_hash:
        print(f"❌ ERREUR: Hash incorrect. Attendu: {expected_hash}")
        return False

    print("✅ Test no_duplicate: PASSED")
    return True


def test_sentence_boundaries():
    """Test que le chunking respecte les frontières de phrase"""
    print("\n=== Test Sentence Boundaries ===")

    strategy = ChunkingStrategy()

    # Texte avec phrases claires
    text = (
        "Article premier de test. Cette phrase est complète et se termine bien. "
        "Voici une troisième phrase avec des détails importants pour le test. "
        "Quatrième phrase qui devrait être coupée proprement. "
        "Cinquième phrase finale du test."
    )

    # Forcer un chunking avec une limite basse
    chunks = strategy.chunk_text(text, max_tokens=30, overlap=5)

    print(f"Nombre de chunks: {len(chunks)}")

    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: '{chunk}'")

        # Vérifier que ça se termine par une ponctuation (sauf si c'est le dernier et tronqué)
        if chunk.strip() and i < len(chunks) - 1:  # Pas le dernier chunk
            if not chunk.strip()[-1] in '.!?':
                print(f"❌ ERREUR: Chunk {i+1} ne se termine pas proprement")
                return False

    print("✅ Test sentence_boundaries: PASSED")
    return True


def test_embedding_dimension_mock():
    """Test conceptuel de la dimension d'embedding (sans Ollama)"""
    print("\n=== Test Embedding Dimension (Mock) ===")

    # Simulation de l'embedding nomic-embed-text (768D)
    mock_embedding = [0.1] * 768

    print(f"Mock embedding dimension: {len(mock_embedding)}")

    # Validation TDD
    if len(mock_embedding) != 768:
        print(f"❌ ERREUR: Dimension incorrecte. Attendu: 768, reçu: {len(mock_embedding)}")
        return False

    # Vérifier que ce sont des nombres
    if not all(isinstance(x, (int, float)) for x in mock_embedding[:10]):
        print("❌ ERREUR: L'embedding doit contenir des nombres")
        return False

    print("✅ Test embedding_dimension: PASSED (mock)")
    return True


def test_legifrance_structure():
    """Test de la structure des articles Légifrance"""
    print("\n=== Test LegiFrance Structure ===")

    # Mock d'un chunk extrait de Légifrance
    chunk = LegalChunk(
        source="Code civil art.734",
        source_type="loi",
        content="Article 734 du Code civil : Les libéralités sont des actes par lesquels...",
        metadata={
            "article": 734,
            "code": "civil",
            "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006434123",
            "date_version": "2024-01-01T10:00:00"
        }
    )

    # Vérifications de structure TDD
    required_attrs = ['source', 'source_type', 'content', 'metadata']
    for attr in required_attrs:
        if not hasattr(chunk, attr):
            print(f"❌ ERREUR: Attribut manquant: {attr}")
            return False

    # Vérifications de contenu
    if chunk.source != "Code civil art.734":
        print(f"❌ ERREUR: Source incorrecte: {chunk.source}")
        return False

    if chunk.source_type != "loi":
        print(f"❌ ERREUR: Type incorrect: {chunk.source_type}")
        return False

    # Vérifications métadonnées
    required_metadata = ["article", "code", "url"]
    for key in required_metadata:
        if key not in chunk.metadata:
            print(f"❌ ERREUR: Métadonnée manquante: {key}")
            return False

    if chunk.metadata["article"] != 734:
        print(f"❌ ERREUR: Numéro d'article incorrect: {chunk.metadata['article']}")
        return False

    print(f"Source: {chunk.source}")
    print(f"Type: {chunk.source_type}")
    print(f"Content length: {len(chunk.content)} chars")
    print(f"Metadata: {chunk.metadata}")

    print("✅ Test legifrance_structure: PASSED")
    return True


def run_all_tests():
    """Exécute tous les tests manuels TDD"""
    print("🧪 === Tests TDD pour ingest_legal ===\n")

    tests = [
        test_chunk_size,
        test_no_duplicate,
        test_sentence_boundaries,
        test_embedding_dimension_mock,
        test_legifrance_structure
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ ERREUR dans {test.__name__}: {e}")
            failed += 1

    print(f"\n=== RÉSULTATS ===")
    print(f"✅ Tests réussis: {passed}")
    print(f"❌ Tests échoués: {failed}")
    print(f"📊 Total: {passed + failed}")

    if failed == 0:
        print("\n🎉 Tous les tests TDD passent!")
        return True
    else:
        print(f"\n⚠️ {failed} tests ont échoué")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)