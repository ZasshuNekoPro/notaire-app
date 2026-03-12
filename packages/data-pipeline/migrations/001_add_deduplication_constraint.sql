-- Migration: Ajout contrainte de déduplication pour les transactions DVF
-- Date: 2026-03-12
-- Description: Ajoute une contrainte unique sur (date_vente, prix_vente, code_postal, surface_m2)
--              pour éviter les doublons lors des imports DVF

-- Créer le dossier migrations s'il n'existe pas
-- Étape 1: Supprimer les éventuels doublons existants
WITH duplicates AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY date_vente, prix_vente, code_postal, surface_m2
            ORDER BY created_at DESC
        ) as rn
    FROM transactions
    WHERE date_vente IS NOT NULL
    AND prix_vente IS NOT NULL
    AND code_postal IS NOT NULL
    AND surface_m2 IS NOT NULL
)
DELETE FROM transactions
WHERE id IN (
    SELECT id FROM duplicates WHERE rn > 1
);

-- Étape 2: Ajouter la contrainte unique pour déduplication
ALTER TABLE transactions
ADD CONSTRAINT uk_transactions_dedup
UNIQUE (date_vente, prix_vente, code_postal, surface_m2);

-- Étape 3: Ajouter les colonnes manquantes pour l'import DVF (si elles n'existent pas)
DO $$
BEGIN
    -- Ajouter numero_voie si elle n'existe pas
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'numero_voie'
    ) THEN
        ALTER TABLE transactions ADD COLUMN numero_voie INTEGER;
    END IF;

    -- Ajouter nom_voie si elle n'existe pas
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'nom_voie'
    ) THEN
        ALTER TABLE transactions ADD COLUMN nom_voie VARCHAR(255);
    END IF;

    -- Ajouter source si elle n'existe pas
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'source'
    ) THEN
        ALTER TABLE transactions ADD COLUMN source VARCHAR(50) DEFAULT 'DVF';
    END IF;
END $$;

-- Étape 4: Améliorer les index pour les requêtes de géocodage
CREATE INDEX IF NOT EXISTS idx_transactions_geocoding
ON transactions(latitude, longitude)
WHERE latitude IS NULL;

CREATE INDEX IF NOT EXISTS idx_transactions_address
ON transactions(numero_voie, nom_voie, code_postal)
WHERE latitude IS NULL;

-- Commentaire sur la contrainte
COMMENT ON CONSTRAINT uk_transactions_dedup ON transactions IS
'Contrainte de déduplication DVF: même transaction = même date+prix+cp+surface';

-- Log de la migration
INSERT INTO pipeline_runs (
    source,
    statut,
    nb_lignes,
    started_at,
    finished_at
) VALUES (
    'MIGRATION_001',
    'terminé',
    0,
    NOW(),
    NOW()
);