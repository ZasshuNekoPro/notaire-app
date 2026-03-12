/**
 * Composant carte Leaflet pour l'affichage des estimations
 * Affiche le bien à estimer et les transactions comparables
 */
'use client';

import React, { useEffect, useRef } from 'react';

// Import conditionnel de Leaflet pour éviter les erreurs SSR
let L: any;
if (typeof window !== 'undefined') {
  L = require('leaflet');
  require('leaflet/dist/leaflet.css');

  // Fix des icônes Leaflet avec Webpack
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  });
}

interface TargetProperty {
  coordinates: [number, number];
  address: string;
  surface: number;
  estimatedPrice: number;
}

interface Comparable {
  id: string;
  prix_vente: number;
  surface_m2: number;
  prix_m2: number;
  nb_pieces?: number;
  date_vente: string;
  commune: string;
  distance_km?: number;
  score_similarite: number;
  latitude?: number;
  longitude?: number;
}

interface EstimationMapProps {
  center: [number, number] | null;
  targetProperty: TargetProperty;
  comparables: Comparable[];
}

const EstimationMap: React.FC<EstimationMapProps> = ({
  center,
  targetProperty,
  comparables
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  // Formatage des prix
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0
    }).format(price);
  };

  // Création d'une icône personnalisée
  const createCustomIcon = (color: string, size: 'small' | 'medium' | 'large' = 'medium') => {
    if (!L) return null;

    const sizes = {
      small: [20, 32],
      medium: [25, 40],
      large: [30, 48]
    };

    const [width, height] = sizes[size];

    return L.divIcon({
      className: 'custom-div-icon',
      html: `
        <div style="
          background-color: ${color};
          width: ${width}px;
          height: ${height}px;
          border-radius: 50% 50% 50% 0;
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          transform: rotate(-45deg);
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <div style="
            color: white;
            font-size: ${size === 'large' ? '14' : size === 'medium' ? '12' : '10'}px;
            font-weight: bold;
            transform: rotate(45deg);
          ">
            ${color === '#dc2626' ? '🏠' : '💰'}
          </div>
        </div>
      `,
      iconSize: [width, height],
      iconAnchor: [width / 2, height],
      popupAnchor: [0, -height]
    });
  };

  // Déterminer la taille du marqueur en fonction de la surface
  const getMarkerSize = (surface: number): 'small' | 'medium' | 'large' => {
    if (surface < 40) return 'small';
    if (surface < 80) return 'medium';
    return 'large';
  };

  // Déterminer la couleur en fonction du score de similarité
  const getComparableColor = (score: number): string => {
    if (score > 0.8) return '#059669'; // Vert foncé - très similaire
    if (score > 0.6) return '#0891b2'; // Bleu - assez similaire
    if (score > 0.4) return '#7c3aed'; // Violet - moyennement similaire
    return '#6b7280'; // Gris - peu similaire
  };

  useEffect(() => {
    if (!mapRef.current || !L || !center) return;

    // Détruire la carte existante si elle existe
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
    }

    // Créer une nouvelle carte
    const map = L.map(mapRef.current).setView(center, 14);

    // Ajouter les tuiles OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    // Marqueur du bien à estimer (rouge)
    const targetIcon = createCustomIcon('#dc2626', 'large');
    if (targetIcon) {
      const targetMarker = L.marker(center, { icon: targetIcon }).addTo(map);

      targetMarker.bindPopup(`
        <div class="p-2">
          <h3 class="font-bold text-red-600 mb-2">🏠 Bien à estimer</h3>
          <p class="text-sm"><strong>Adresse:</strong> ${targetProperty.address}</p>
          <p class="text-sm"><strong>Surface:</strong> ${targetProperty.surface} m²</p>
          <p class="text-sm"><strong>Estimation:</strong> ${formatPrice(targetProperty.estimatedPrice)}</p>
        </div>
      `);
    }

    // Marqueurs des transactions comparables
    const bounds = L.latLngBounds([center]);
    let comparablesAdded = 0;

    comparables.forEach((comparable) => {
      // Vérifier que le comparable a des coordonnées
      if (!comparable.latitude || !comparable.longitude) return;

      const coords: [number, number] = [comparable.latitude, comparable.longitude];
      const color = getComparableColor(comparable.score_similarite);
      const size = getMarkerSize(comparable.surface_m2);
      const icon = createCustomIcon(color, size);

      if (icon) {
        const marker = L.marker(coords, { icon }).addTo(map);

        const popupContent = `
          <div class="p-2 min-w-[200px]">
            <h3 class="font-bold text-blue-600 mb-2">💰 Transaction comparable</h3>
            <div class="space-y-1 text-sm">
              <p><strong>Prix:</strong> ${formatPrice(comparable.prix_vente)}</p>
              <p><strong>Surface:</strong> ${comparable.surface_m2.toFixed(0)} m²</p>
              <p><strong>Prix/m²:</strong> ${formatPrice(comparable.prix_m2)}</p>
              ${comparable.nb_pieces ? `<p><strong>Pièces:</strong> ${comparable.nb_pieces}</p>` : ''}
              <p><strong>Date:</strong> ${new Date(comparable.date_vente).toLocaleDateString('fr-FR')}</p>
              <p><strong>Commune:</strong> ${comparable.commune}</p>
              ${comparable.distance_km ? `<p><strong>Distance:</strong> ${comparable.distance_km.toFixed(1)} km</p>` : ''}
              <div class="mt-2">
                <span class="px-2 py-1 rounded text-xs font-medium ${
                  comparable.score_similarite > 0.8
                    ? 'bg-green-100 text-green-800'
                    : comparable.score_similarite > 0.6
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-gray-100 text-gray-800'
                }">
                  Similarité: ${(comparable.score_similarite * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent);
        bounds.extend(coords);
        comparablesAdded++;
      }
    });

    // Ajuster la vue pour inclure tous les marqueurs
    if (comparablesAdded > 0) {
      map.fitBounds(bounds, { padding: [20, 20] });
    }

    // Sauvegarder l'instance de la carte
    mapInstanceRef.current = map;

    // Nettoyage
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [center, targetProperty, comparables]);

  // Affichage de placeholder si pas de coordonnées
  if (!center) {
    return (
      <div className="h-full bg-gray-100 flex items-center justify-center rounded-lg">
        <div className="text-center text-gray-500">
          <div className="text-2xl mb-2">🗺️</div>
          <p>Géocodage de l'adresse...</p>
          <p className="text-sm">La carte s'affichera une fois l'adresse localisée</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div ref={mapRef} className="h-full w-full rounded-lg" />

      {/* Légende */}
      <div className="absolute top-4 right-4 bg-white bg-opacity-90 p-3 rounded-lg shadow-md text-xs z-[1000]">
        <h4 className="font-semibold mb-2">Légende</h4>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-red-600 rounded-full"></div>
            <span>Bien à estimer</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-600 rounded-full"></div>
            <span>Très similaire (&gt;80%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-600 rounded-full"></div>
            <span>Assez similaire (&gt;60%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
            <span>Moyennement similaire</span>
          </div>
        </div>
        <div className="mt-2 pt-2 border-t text-gray-600">
          <p>Taille = surface du bien</p>
        </div>
      </div>
    </>
  );
};

export default EstimationMap;