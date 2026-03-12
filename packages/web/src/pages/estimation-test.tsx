/**
 * Page de démonstration d'estimation immobilière
 * Accessible sans authentification pour les démos
 */
'use client';

import React, { useState, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';

// Import dynamique de la carte Leaflet pour éviter les erreurs SSR
const EstimationMap = dynamic(() => import('../components/map/EstimationMap'), {
  ssr: false,
  loading: () => <div className="h-96 bg-gray-100 animate-pulse rounded-lg"></div>
});

// Types pour les données
interface AdresseSuggestion {
  label: string;
  coordinates: [number, number];
  context: string;
}

interface TransactionComparable {
  id: string;
  prix_vente: number;
  surface_m2: number;
  prix_m2: number;
  nb_pieces?: number;
  date_vente: string;
  commune: string;
  code_postal: string;
  distance_km?: number;
  score_similarite: number;
  latitude: number;
  longitude: number;
}

interface EstimationResult {
  fourchette: {
    min: number;
    median: number;
    max: number;
  };
  prix_m2_estime: number;
  comparables: TransactionComparable[];
  facteurs_correction: string[];
  niveau_confiance: 'fort' | 'moyen' | 'faible';
  justification: string;
  nb_comparables_utilises: number;
}

interface FormData {
  adresse: string;
  type_bien: 'Appartement' | 'Maison' | 'Local industriel. commercial ou assimilé' | '';
  surface_m2: string;
  nb_pieces: string;
}

const EstimationTestPage = () => {
  // États du formulaire
  const [formData, setFormData] = useState<FormData>({
    adresse: '',
    type_bien: '',
    surface_m2: '',
    nb_pieces: ''
  });

  // États de l'autocomplétion
  const [addressSuggestions, setAddressSuggestions] = useState<AdresseSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedCoordinates, setSelectedCoordinates] = useState<[number, number] | null>(null);

  // États de l'estimation
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<EstimationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs
  const addressInputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // API URL
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Autocomplétion d'adresse avec l'API BAN
  const fetchAddressSuggestions = async (query: string) => {
    if (query.length < 3) {
      setAddressSuggestions([]);
      return;
    }

    try {
      const response = await fetch(
        `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(query)}&limit=5`
      );

      if (response.ok) {
        const data = await response.json();
        const suggestions: AdresseSuggestion[] = data.features.map((feature: any) => ({
          label: feature.properties.label,
          coordinates: feature.geometry.coordinates,
          context: feature.properties.context
        }));

        setAddressSuggestions(suggestions);
        setShowSuggestions(true);
      }
    } catch (error) {
      console.error('Erreur autocomplétion:', error);
    }
  };

  // Gestion de la saisie d'adresse
  const handleAddressChange = (value: string) => {
    setFormData(prev => ({ ...prev, adresse: value }));
    fetchAddressSuggestions(value);
  };

  // Sélection d'une suggestion
  const selectSuggestion = (suggestion: AdresseSuggestion) => {
    setFormData(prev => ({ ...prev, adresse: suggestion.label }));
    setSelectedCoordinates(suggestion.coordinates);
    setAddressSuggestions([]);
    setShowSuggestions(false);
  };

  // Soumission du formulaire
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.adresse || !formData.type_bien || !formData.surface_m2) {
      setError('Veuillez remplir tous les champs obligatoires');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const requestBody = {
        adresse: formData.adresse,
        type_bien: formData.type_bien,
        surface_m2: parseInt(formData.surface_m2),
        nb_pieces: formData.nb_pieces ? parseInt(formData.nb_pieces) : null,
        etage: null,
        annee_construction: null,
        dossier_id: null
      };

      const response = await fetch(`${API_URL}/estimations/analyse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Token demo pour la démo publique
          'Authorization': 'Bearer demo-token'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Aucune transaction comparable trouvée dans cette zone');
        } else if (response.status === 401) {
          throw new Error('Service temporairement indisponible');
        } else {
          throw new Error(`Erreur API: ${response.status}`);
        }
      }

      const estimationResult: EstimationResult = await response.json();
      setResult(estimationResult);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de l\'estimation');
    } finally {
      setIsLoading(false);
    }
  };

  // Fermer les suggestions si clic à l'extérieur
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        addressInputRef.current &&
        !addressInputRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Formatage des prix
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0
    }).format(price);
  };

  // Formatage du markdown simple
  const formatMarkdown = (text: string) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">

        {/* En-tête */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🏠 Estimation Immobilière DVF
          </h1>
          <p className="text-gray-600">
            Démonstration d'estimation basée sur les données DVF et l'intelligence artificielle
          </p>
        </div>

        {/* Formulaire d'estimation */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Estimer votre bien</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

              {/* Adresse avec autocomplétion */}
              <div className="relative md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Adresse complète *
                </label>
                <input
                  ref={addressInputRef}
                  type="text"
                  value={formData.adresse}
                  onChange={(e) => handleAddressChange(e.target.value)}
                  placeholder="8 rue de Rivoli, 75001 Paris"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  autoComplete="off"
                />

                {/* Suggestions d'autocomplétion */}
                {showSuggestions && addressSuggestions.length > 0 && (
                  <div
                    ref={suggestionsRef}
                    className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto"
                  >
                    {addressSuggestions.map((suggestion, index) => (
                      <button
                        key={index}
                        type="button"
                        onClick={() => selectSuggestion(suggestion)}
                        className="w-full px-4 py-2 text-left hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
                      >
                        <div className="text-sm font-medium text-gray-900">
                          {suggestion.label}
                        </div>
                        <div className="text-xs text-gray-500">
                          {suggestion.context}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Type de bien */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type de bien *
                </label>
                <select
                  value={formData.type_bien}
                  onChange={(e) => setFormData(prev => ({ ...prev, type_bien: e.target.value as any }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Sélectionnez...</option>
                  <option value="Appartement">Appartement</option>
                  <option value="Maison">Maison</option>
                  <option value="Local industriel. commercial ou assimilé">Local commercial</option>
                </select>
              </div>

              {/* Surface */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Surface (m²) *
                </label>
                <input
                  type="number"
                  value={formData.surface_m2}
                  onChange={(e) => setFormData(prev => ({ ...prev, surface_m2: e.target.value }))}
                  placeholder="65"
                  min="10"
                  max="2000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Nombre de pièces */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre de pièces
                </label>
                <input
                  type="number"
                  value={formData.nb_pieces}
                  onChange={(e) => setFormData(prev => ({ ...prev, nb_pieces: e.target.value }))}
                  placeholder="3"
                  min="1"
                  max="20"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Bouton de soumission */}
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={isLoading || !formData.adresse || !formData.type_bien || !formData.surface_m2}
                  className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Estimation...
                    </>
                  ) : (
                    '🎯 Estimer'
                  )}
                </button>
              </div>
            </div>

            <p className="text-sm text-gray-500">
              * Champs obligatoires. Estimation basée sur les transactions DVF des 24 derniers mois.
            </p>
          </form>
        </div>

        {/* Affichage des erreurs */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
            <div className="flex items-center">
              <div className="text-red-500 mr-2">⚠️</div>
              <div className="text-red-800">{error}</div>
            </div>
          </div>
        )}

        {/* Skeleton de chargement */}
        {isLoading && (
          <div className="space-y-6">
            {/* Skeleton carte */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
              <div className="h-96 bg-gray-100 animate-pulse rounded-lg"></div>
            </div>

            {/* Skeleton résumé */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
              <div className="grid grid-cols-3 gap-4">
                <div className="h-20 bg-gray-100 animate-pulse rounded"></div>
                <div className="h-20 bg-gray-100 animate-pulse rounded"></div>
                <div className="h-20 bg-gray-100 animate-pulse rounded"></div>
              </div>
            </div>
          </div>
        )}

        {/* Résultats de l'estimation */}
        {result && (
          <div className="space-y-6">

            {/* Carte avec transactions comparables */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold mb-4">📍 Localisation et comparables</h3>
              <div className="h-96 rounded-lg overflow-hidden">
                <EstimationMap
                  center={selectedCoordinates}
                  targetProperty={{
                    coordinates: selectedCoordinates || [2.3522, 48.8566],
                    address: formData.adresse,
                    surface: parseInt(formData.surface_m2),
                    estimatedPrice: result.fourchette.median
                  }}
                  comparables={result.comparables}
                />
              </div>
              <p className="text-sm text-gray-600 mt-2">
                🔴 Bien à estimer • 🔵 {result.nb_comparables_utilises} transactions comparables
              </p>
            </div>

            {/* Résumé de l'estimation */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold mb-4">💰 Résumé de l'estimation</h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                {/* Fourchette de prix */}
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-sm text-blue-600 font-medium">Fourchette d'estimation</div>
                  <div className="text-lg font-bold text-blue-800">
                    {formatPrice(result.fourchette.min)} - {formatPrice(result.fourchette.max)}
                  </div>
                  <div className="text-sm text-gray-600">
                    Médiane : {formatPrice(result.fourchette.median)}
                  </div>
                </div>

                {/* Prix au m² */}
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-sm text-green-600 font-medium">Prix au m²</div>
                  <div className="text-lg font-bold text-green-800">
                    {formatPrice(result.prix_m2_estime)}
                  </div>
                  <div className="text-sm text-gray-600">
                    Pour {formData.surface_m2} m²
                  </div>
                </div>

                {/* Niveau de confiance */}
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <div className="text-sm text-purple-600 font-medium">Niveau de confiance</div>
                  <div className="text-lg font-bold text-purple-800 capitalize">
                    {result.niveau_confiance}
                  </div>
                  <div className="text-sm text-gray-600">
                    {result.nb_comparables_utilises} comparables
                  </div>
                </div>
              </div>

              {/* Facteurs de correction */}
              <div className="mb-4">
                <h4 className="font-medium text-gray-800 mb-2">🔧 Facteurs de correction</h4>
                <div className="flex flex-wrap gap-2">
                  {result.facteurs_correction.map((facteur, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                    >
                      {facteur}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Analyse IA */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold mb-4">🤖 Analyse détaillée</h3>
              <div
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{
                  __html: `<p>${formatMarkdown(result.justification)}</p>`
                }}
              />
            </div>

            {/* Tableau des comparables */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold mb-4">📊 Transactions comparables</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-2 text-left">Commune</th>
                      <th className="px-4 py-2 text-right">Prix</th>
                      <th className="px-4 py-2 text-right">Surface</th>
                      <th className="px-4 py-2 text-right">€/m²</th>
                      <th className="px-4 py-2 text-center">Pièces</th>
                      <th className="px-4 py-2 text-center">Date</th>
                      <th className="px-4 py-2 text-center">Distance</th>
                      <th className="px-4 py-2 text-center">Similarité</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparables.slice(0, 10).map((comparable) => (
                      <tr key={comparable.id} className="border-t hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium">{comparable.commune}</td>
                        <td className="px-4 py-2 text-right">{formatPrice(comparable.prix_vente)}</td>
                        <td className="px-4 py-2 text-right">{comparable.surface_m2.toFixed(0)} m²</td>
                        <td className="px-4 py-2 text-right font-medium">{formatPrice(comparable.prix_m2)}</td>
                        <td className="px-4 py-2 text-center">{comparable.nb_pieces || '-'}</td>
                        <td className="px-4 py-2 text-center">
                          {new Date(comparable.date_vente).toLocaleDateString('fr-FR')}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {comparable.distance_km ? `${comparable.distance_km.toFixed(1)} km` : '-'}
                        </td>
                        <td className="px-4 py-2 text-center">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            comparable.score_similarite > 0.8
                              ? 'bg-green-100 text-green-800'
                              : comparable.score_similarite > 0.6
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {(comparable.score_similarite * 100).toFixed(0)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {result.comparables.length > 10 && (
                  <p className="text-sm text-gray-500 text-center mt-4">
                    ... et {result.comparables.length - 10} autres transactions comparables
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Avertissement */}
        <div className="mt-8 text-center">
          <p className="text-sm text-gray-500">
            ⚠️ Cette estimation est fournie à titre indicatif et ne constitue pas un avis de valeur officiel.
            Les données sont basées sur les transactions DVF publiques.
          </p>
        </div>
      </div>
    </div>
  );
};

export default EstimationTestPage;