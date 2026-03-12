"""
Module RAG (Retrieval-Augmented Generation) pour le domaine notarial

Exports principaux :
- NotaireRAG : Service principal de RAG juridique
- get_notaire_rag : Factory function pour l'instance singleton
- KnowledgeChunk : Modèle de chunk de connaissance
- RAGResponse : Modèle de réponse RAG
"""

from .notaire_rag import (
    NotaireRAG,
    NotaireRAGService,
    get_notaire_rag,
    ChunkResult,
    KnowledgeChunk,  # Alias pour compatibilité
    RAGResponse
)

__all__ = [
    "NotaireRAG",
    "NotaireRAGService",
    "get_notaire_rag",
    "ChunkResult",
    "KnowledgeChunk",
    "RAGResponse"
]