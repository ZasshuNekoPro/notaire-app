-- Vue estimation_stats pour les statistiques d'estimation immobilière
-- Utilisée par l'API /estimations/stats
-- Calcule les prix médians et quartiles par zone et type de bien

DROP VIEW IF EXISTS estimation_stats CASCADE;

CREATE VIEW estimation_stats AS
WITH transaction_stats AS (
    SELECT
        code_postal,
        type_bien,
        COUNT(*) as nb_transactions,
        MIN(prix_vente) as prix_min,
        MAX(prix_vente) as prix_max,
        ROUND(AVG(surface_m2), 1) as surface_moyenne,
        -- Calcul des quartiles et médiane avec PERCENTILE_CONT
        ROUND(
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_vente / surface_m2)::numeric,
            0
        ) as prix_m2_q1,
        ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_vente / surface_m2)::numeric,
            0
        ) as prix_m2_median,
        ROUND(
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_vente / surface_m2)::numeric,
            0
        ) as prix_m2_q3,
        MIN(date_vente) as date_debut,
        MAX(date_vente) as date_fin
    FROM transactions
    WHERE
        -- Filtres de qualité
        date_vente >= CURRENT_DATE - INTERVAL '24 months'
        AND prix_vente > 0
        AND surface_m2 > 0
        AND prix_vente / surface_m2 BETWEEN 100 AND 50000  -- Prix au m² réaliste
        AND nature_mutation = 'Vente'
    GROUP BY code_postal, type_bien
    HAVING COUNT(*) >= 3  -- Au moins 3 transactions pour avoir des stats fiables
)
SELECT
    code_postal,
    type_bien,
    prix_m2_q1,
    prix_m2_median,
    prix_m2_q3,
    nb_transactions,
    prix_min,
    prix_max,
    surface_moyenne,
    date_debut,
    date_fin
FROM transaction_stats
ORDER BY code_postal, type_bien;

-- Index pour optimiser les requêtes sur la vue
CREATE INDEX IF NOT EXISTS idx_transactions_estimation_stats
ON transactions (code_postal, type_bien, date_vente)
WHERE
    date_vente >= CURRENT_DATE - INTERVAL '24 months'
    AND prix_vente > 0
    AND surface_m2 > 0
    AND nature_mutation = 'Vente';

-- Commentaires pour la documentation
COMMENT ON VIEW estimation_stats IS
'Vue des statistiques d''estimation immobilière par zone et type de bien.
Calcule les prix médians et quartiles sur les 24 derniers mois.
Utilisée par l''API GET /estimations/stats.';

-- Exemple d'utilisation
/*
-- Récupérer les stats pour un code postal et type de bien
SELECT * FROM estimation_stats
WHERE code_postal = '75008'
AND type_bien = 'Appartement';

-- Top 10 des zones les plus chères (appartements)
SELECT code_postal, prix_m2_median, nb_transactions
FROM estimation_stats
WHERE type_bien = 'Appartement'
ORDER BY prix_m2_median DESC
LIMIT 10;
*/