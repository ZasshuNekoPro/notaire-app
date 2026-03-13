/**
 * Composant carte Leaflet pour l'affichage des estimations immobilières.
 * Import dynamique requis pour éviter les erreurs SSR.
 */
'use client'

import { useEffect, useRef } from 'react'

// Types pour les props du composant
interface Marker {
  position: [number, number]
  popup: string
}

interface EstimationMapProps {
  center: [number, number]
  markers?: Marker[]
  comparables?: Marker[]
  zoom?: number
  height?: string
}

/**
 * Composant carte Leaflet
 */
function EstimationMap({
  center,
  markers = [],
  comparables = [],
  zoom = 15,
  height = '400px'
}: EstimationMapProps) {
  const mapRef = useRef<any>(null)
  const mapInstanceRef = useRef<any>(null)

  useEffect(() => {
    // Import dynamique de Leaflet pour éviter les erreurs SSR
    const initMap = async () => {
      if (typeof window === 'undefined') return

      // Import dynamique de Leaflet
      const L = await import('leaflet')

      // Fix des icônes par défaut de Leaflet
      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
      })

      // Créer la carte si elle n'existe pas déjà
      if (!mapInstanceRef.current && mapRef.current) {
        mapInstanceRef.current = L.map(mapRef.current).setView(center, zoom)

        // Ajouter les tuiles OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(mapInstanceRef.current)

        // Créer des icônes personnalisées
        const mainIcon = L.divIcon({
          html: '<div style="background-color: #2563eb; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.3);"></div>',
          className: 'custom-marker',
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        })

        const comparableIcon = L.divIcon({
          html: '<div style="background-color: #059669; width: 16px; height: 16px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>',
          className: 'comparable-marker',
          iconSize: [16, 16],
          iconAnchor: [8, 8]
        })

        // Ajouter les marqueurs principaux
        markers.forEach(marker => {
          L.marker(marker.position, { icon: mainIcon })
            .addTo(mapInstanceRef.current)
            .bindPopup(marker.popup)
        })

        // Ajouter les marqueurs des comparables
        comparables.forEach(comparable => {
          L.marker(comparable.position, { icon: comparableIcon })
            .addTo(mapInstanceRef.current)
            .bindPopup(comparable.popup)
        })

        // Ajuster la vue pour inclure tous les marqueurs
        if (markers.length > 0 || comparables.length > 0) {
          const group = L.featureGroup([
            ...markers.map(m => L.marker(m.position)),
            ...comparables.map(c => L.marker(c.position))
          ])
          mapInstanceRef.current.fitBounds(group.getBounds(), { padding: [20, 20] })
        }
      } else if (mapInstanceRef.current) {
        // Mettre à jour la vue si la carte existe déjà
        mapInstanceRef.current.setView(center, zoom)
      }
    }

    initMap()

    // Cleanup à la désactivation
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [center, markers, comparables, zoom])

  return (
    <>
      {/* Styles CSS pour Leaflet */}
      <style jsx global>{`
        @import url('https://unpkg.com/leaflet@1.7.1/dist/leaflet.css');

        .custom-marker {
          background: transparent;
        }

        .comparable-marker {
          background: transparent;
        }

        .leaflet-popup-content-wrapper {
          border-radius: 8px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        }

        .leaflet-popup-content {
          margin: 12px 16px;
          font-size: 14px;
          line-height: 1.4;
          font-family: system-ui, -apple-system, sans-serif;
        }
      `}</style>

      <div
        ref={mapRef}
        style={{ height }}
        className="w-full rounded-lg border border-gray-200 overflow-hidden"
      />
    </>
  )
}

export default EstimationMap
