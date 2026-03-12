/**
 * Composant carte Leaflet pour affichage des transactions DVF
 * Utilise React Leaflet avec markers colorés selon prix au m²
 */
'use client';

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix des icônes Leaflet avec Next.js
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

// Types
interface TransactionPoint {
  id: string;
  longitude: number;
  latitude: number;
  prix_vente: number;
  surface_m2: number;
  prix_m2: number;
  type_bien: string;
  adresse: string;
  date_vente: string;
  distance_km?: number;
  similarite_score?: number;
}

interface EstimationMapProps {
  departement: string;
  typeBien: string;
  transactions?: TransactionPoint[];
}

// Composant pour centrer la carte automatiquement
function MapCenterController({ transactions }: { transactions: TransactionPoint[] }) {
  const map = useMap();

  useEffect(() => {
    if (transactions.length > 0) {
      const bounds = L.latLngBounds(
        transactions.map(t => [t.latitude, t.longitude])
      );
      map.fitBounds(bounds, { padding: [20, 20] });
    }
  }, [transactions, map]);

  return null;
}

// Fonction pour obtenir une couleur selon le prix au m²
function getPriceColor(prixM2: number): string {
  if (prixM2 < 2000) return '#22c55e';  // Vert - bon marché
  if (prixM2 < 4000) return '#eab308';  // Jaune - modéré
  if (prixM2 < 6000) return '#f97316';  // Orange - cher
  return '#ef4444';                     // Rouge - très cher
}

// Créer des icônes colorées dynamiquement
function createColoredIcon(color: string): L.Icon {
  const svgIcon = `
    <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
      <path fill="${color}" stroke="#fff" stroke-width="2"
        d="M12.5 0C5.596 0 0 5.596 0 12.5c0 12.5 12.5 28.5 12.5 28.5s12.5-16 12.5-28.5C25 5.596 19.404 0 12.5 0z"/>
      <circle fill="#fff" cx="12.5" cy="12.5" r="6"/>
    </svg>
  `;

  return L.icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(svgIcon)}`,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
  });
}

// Formatage des prix
const formatPrice = (price: number) => {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0
  }).format(price);
};

// Formatage des dates
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('fr-FR');
};

export default function EstimationMap({ departement, typeBien, transactions = [] }: EstimationMapProps) {
  const [mapData, setMapData] = useState<TransactionPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Position par défaut (Paris si pas de données)
  const defaultCenter: [number, number] = [48.8566, 2.3522];
  const defaultZoom = 11;

  // Charger les données DVF depuis l'API si pas de transactions fournies
  useEffect(() => {
    if (transactions.length > 0) {
      setMapData(transactions);
      return;
    }

    const fetchMapData = async () => {
      if (!departement) return;

      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          dept: departement,
          mois_recents: '12'
        });

        if (typeBien && typeBien !== '') {
          params.append('type_bien', typeBien);
        }

        const response = await fetch(`/api/estimations/carte?${params}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || 'demo-token'}`
          }
        });

        if (!response.ok) {
          throw new Error(`Erreur API: ${response.status}`);
        }

        const data = await response.json();

        // Convertir le GeoJSON en format utilisable
        const points: TransactionPoint[] = data.features.map((feature: any) => ({
          id: feature.properties.id,
          longitude: feature.geometry.coordinates[0],
          latitude: feature.geometry.coordinates[1],
          prix_vente: feature.properties.prix_vente,
          surface_m2: feature.properties.surface_m2,
          prix_m2: feature.properties.prix_m2,
          type_bien: feature.properties.type_bien,
          adresse: feature.properties.adresse,
          date_vente: feature.properties.date_vente,
        }));

        setMapData(points);

      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erreur lors du chargement de la carte');
        setMapData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchMapData();
  }, [departement, typeBien, transactions]);

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100 rounded">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Chargement de la carte...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-red-50 rounded border border-red-200">
        <div className="text-center text-red-700">
          <p className="font-medium">Erreur de chargement</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative rounded overflow-hidden">
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        className="w-full h-full"
        zoomControl={true}
      >
        {/* Couche de tuiles OpenStreetMap */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Contrôleur pour centrer automatiquement */}
        {mapData.length > 0 && <MapCenterController transactions={mapData} />}

        {/* Markers des transactions */}
        {mapData.map((transaction) => {
          const color = getPriceColor(transaction.prix_m2);
          const coloredIcon = createColoredIcon(color);

          return (
            <Marker
              key={transaction.id}
              position={[transaction.latitude, transaction.longitude]}
              icon={coloredIcon}
            >
              <Popup maxWidth={300} className="transaction-popup">
                <div className="space-y-2">
                  <h4 className="font-semibold text-sm text-gray-900">
                    {transaction.type_bien}
                  </h4>

                  <div className="text-xs space-y-1">
                    <p className="text-gray-600">{transaction.adresse}</p>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                      <div>
                        <span className="font-medium">Prix:</span>
                        <div className="text-green-600 font-bold">
                          {formatPrice(transaction.prix_vente)}
                        </div>
                      </div>

                      <div>
                        <span className="font-medium">Surface:</span>
                        <div>{transaction.surface_m2.toFixed(0)} m²</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="font-medium">Prix/m²:</span>
                        <div className="font-bold" style={{ color }}>
                          {formatPrice(transaction.prix_m2)}
                        </div>
                      </div>

                      <div>
                        <span className="font-medium">Date:</span>
                        <div>{formatDate(transaction.date_vente)}</div>
                      </div>
                    </div>

                    {/* Informations supplémentaires si c'est un comparable */}
                    {transaction.distance_km !== undefined && (
                      <div className="pt-2 border-t bg-blue-50 p-2 rounded mt-2">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="font-medium">Distance:</span>
                            <div className="text-blue-600">
                              {transaction.distance_km.toFixed(1)} km
                            </div>
                          </div>

                          {transaction.similarite_score !== undefined && (
                            <div>
                              <span className="font-medium">Similarité:</span>
                              <div className="text-blue-600">
                                {(transaction.similarite_score * 100).toFixed(0)}%
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Légende des couleurs */}
      <div className="absolute bottom-4 left-4 bg-white p-3 rounded shadow-lg border z-[1000]">
        <h4 className="text-sm font-semibold mb-2">Prix au m²</h4>
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span>&lt; 2 000€</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <span>2 000€ - 4 000€</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500"></div>
            <span>4 000€ - 6 000€</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>&gt; 6 000€</span>
          </div>
        </div>
      </div>

      {/* Compteur de transactions */}
      {mapData.length > 0 && (
        <div className="absolute top-4 right-4 bg-white px-3 py-2 rounded shadow-lg border z-[1000]">
          <div className="text-sm">
            <span className="font-semibold">{mapData.length}</span> transactions affichées
          </div>
        </div>
      )}
    </div>
  );
}