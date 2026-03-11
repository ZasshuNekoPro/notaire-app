#!/bin/bash
# Vérification rapide d'un import DVF
docker exec notaire-postgres psql -U notaire -d notaire_app -c "
SELECT
  departement,
  type_bien,
  COUNT(*) as nb,
  ROUND(AVG(prix_m2)) as prix_m2_moyen,
  MIN(date_vente) as plus_ancienne,
  MAX(date_vente) as plus_recente
FROM transactions
GROUP BY departement, type_bien
ORDER BY departement, nb DESC;
"
