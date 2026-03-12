-- ============================================================
-- Initialisation du schéma RAG pour la base de connaissances
-- ============================================================
--
-- Ce script crée les tables et index nécessaires au système RAG
-- du projet notaire-app.
--
-- Usage :
--   psql -U notaire -d notaire_app -f scripts/init_rag_schema.sql
--
-- ============================================================

-- Activer l'extension pgvector si elle n'existe pas
CREATE EXTENSION IF NOT EXISTS vector;

-- Table principale des chunks de connaissance
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Métadonnées source
    source VARCHAR(255) NOT NULL,           -- ex: "Code civil art.734"
    source_type VARCHAR(50) NOT NULL,       -- 'loi' | 'jurisprudence' | 'bofip' | 'acte_type'

    -- Contenu
    content TEXT NOT NULL,                  -- texte du chunk (512 tokens max)
    content_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 pour déduplication

    -- Vecteur d'embedding
    embedding vector(768) NOT NULL,         -- nomic-embed-text (768 dimensions)

    -- Métadonnées JSON
    metadata JSONB DEFAULT '{}' NOT NULL,   -- { article, date_version, url, etc. }

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Index de recherche vectorielle (IVFFlat pour < 100k vecteurs)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
ON knowledge_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Index pour les requêtes par type de source
CREATE INDEX IF NOT EXISTS idx_chunks_source_type
ON knowledge_chunks (source_type);

-- Index pour les requêtes par source spécifique
CREATE INDEX IF NOT EXISTS idx_chunks_source
ON knowledge_chunks (source);

-- Index sur le hash pour la déduplication (unique constraint)
CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_content_hash
ON knowledge_chunks (content_hash);

-- Index sur les dates pour les requêtes temporelles
CREATE INDEX IF NOT EXISTS idx_chunks_created_at
ON knowledge_chunks (created_at DESC);

-- Index GIN sur les métadonnées JSON
CREATE INDEX IF NOT EXISTS idx_chunks_metadata
ON knowledge_chunks USING gin (metadata);

-- ============================================================
-- VUES UTILITAIRES
-- ============================================================

-- Vue des statistiques par type de source
CREATE OR REPLACE VIEW v_chunks_stats AS
SELECT
    source_type,
    COUNT(*) as nb_chunks,
    AVG(LENGTH(content)) as taille_moyenne_contenu,
    MIN(created_at) as premier_chunk,
    MAX(created_at) as dernier_chunk
FROM knowledge_chunks
GROUP BY source_type
ORDER BY nb_chunks DESC;

-- Vue des sources les plus représentées
CREATE OR REPLACE VIEW v_sources_top AS
SELECT
    source,
    source_type,
    COUNT(*) as nb_chunks,
    AVG(LENGTH(content)) as taille_moyenne
FROM knowledge_chunks
GROUP BY source, source_type
HAVING COUNT(*) > 1
ORDER BY nb_chunks DESC
LIMIT 50;

-- ============================================================
-- FONCTIONS UTILITAIRES
-- ============================================================

-- Fonction de recherche similaire simplifiée
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(768),
    similarity_threshold float DEFAULT 0.75,
    result_limit integer DEFAULT 5,
    filter_source_type text DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    source text,
    source_type text,
    content text,
    similarity float,
    metadata jsonb
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        id,
        knowledge_chunks.source,
        knowledge_chunks.source_type,
        knowledge_chunks.content,
        1 - (embedding <=> query_embedding) AS similarity,
        knowledge_chunks.metadata
    FROM knowledge_chunks
    WHERE 1 - (embedding <=> query_embedding) > similarity_threshold
        AND (filter_source_type IS NULL OR knowledge_chunks.source_type = filter_source_type)
    ORDER BY embedding <=> query_embedding
    LIMIT result_limit;
$$;

-- Fonction de nettoyage des doublons (si nécessaire)
CREATE OR REPLACE FUNCTION clean_duplicate_chunks()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count integer;
BEGIN
    WITH duplicates AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY content_hash
                ORDER BY created_at DESC
            ) as rn
        FROM knowledge_chunks
    )
    DELETE FROM knowledge_chunks
    WHERE id IN (
        SELECT id FROM duplicates WHERE rn > 1
    );

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Trigger pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trigger_chunks_updated_at
    BEFORE UPDATE ON knowledge_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- PERMISSIONS (à adapter selon vos rôles)
-- ============================================================

-- Donner les permissions au rôle notaire
GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_chunks TO notaire;
GRANT SELECT ON v_chunks_stats TO notaire;
GRANT SELECT ON v_sources_top TO notaire;
GRANT EXECUTE ON FUNCTION search_similar_chunks TO notaire;
GRANT EXECUTE ON FUNCTION clean_duplicate_chunks TO notaire;

-- ============================================================
-- COMMENTAIRES
-- ============================================================

COMMENT ON TABLE knowledge_chunks IS
'Table principale du système RAG contenant les chunks de connaissances juridiques avec leurs embeddings vectoriels';

COMMENT ON COLUMN knowledge_chunks.source IS
'Référence de la source (ex: "Code civil art.734", "BOFIP 3169-PGP")';

COMMENT ON COLUMN knowledge_chunks.source_type IS
'Type de source juridique : loi, jurisprudence, bofip, acte_type';

COMMENT ON COLUMN knowledge_chunks.content IS
'Contenu textuel du chunk (max 512 tokens recommandé)';

COMMENT ON COLUMN knowledge_chunks.content_hash IS
'Hash SHA256 du contenu pour déduplication';

COMMENT ON COLUMN knowledge_chunks.embedding IS
'Vecteur d''embedding 768D généré par nomic-embed-text';

COMMENT ON COLUMN knowledge_chunks.metadata IS
'Métadonnées JSON : {article, date_version, url, section, etc.}';

COMMENT ON INDEX idx_chunks_embedding IS
'Index IVFFlat pour recherche de similarité cosinus (< 100k vecteurs)';

COMMENT ON FUNCTION search_similar_chunks IS
'Fonction de recherche vectorielle avec seuil de similarité configurable';

-- ============================================================
-- DONNÉES D'EXEMPLE (optionnel pour les tests)
-- ============================================================

-- Insertion de quelques chunks d'exemple pour valider le schéma
-- (à supprimer en production)

-- INSERT INTO knowledge_chunks (source, source_type, content, content_hash, embedding, metadata)
-- VALUES
-- (
--     'Code civil art.734',
--     'loi',
--     'Article 734 du Code civil : Les libéralités sont les actes par lesquels une personne dispose à titre gratuit de tout ou partie de ses biens ou de ses droits au profit d''autrui.',
--     encode(sha256('Article 734 du Code civil : Les libéralités sont les actes par lesquels une personne dispose à titre gratuit de tout ou partie de ses biens ou de ses droits au profit d''autrui.'::bytea), 'hex'),
--     array_fill(0.0, ARRAY[768])::vector, -- Embedding factice
--     '{"article": 734, "code": "civil", "titre": "Des libéralités"}'::jsonb
-- );

-- Afficher les statistiques finales
SELECT 'Schéma RAG initialisé avec succès' as status;
SELECT * FROM v_chunks_stats;