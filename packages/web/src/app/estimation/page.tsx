/**
 * Page estimation immobilière complète avec IA, carte et intégration dossiers.
 */
'use client'

import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { AppLayout } from '@/components/layout'
import {
  Card,
  FullCard,
  Button,
  Input,
  Spinner,
  Badge,
  StatusBadge
} from '@/components/ui'
import { useEstimation } from '@/hooks/useEstimation'

// Import dynamique de la carte pour éviter les erreurs SSR
const MapComponent = dynamic(() => import('../../../components/map/EstimationMap'), {
  ssr: false,
  loading: () => (
    <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
})

// Composant Autocomplétion Adresse
function AddressAutocomplete({
  value,
  onChange,
  onSelect,
  suggestions,
  isLoading,
  onSearch
}: {
  value: string
  onChange: (value: string) => void
  onSelect: (suggestion: any) => void
  suggestions: any[]
  isLoading: boolean
  onSearch: (query: string) => void
}) {
  const [showSuggestions, setShowSuggestions] = useState(false)

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    onChange(newValue)
    onSearch(newValue)
    setShowSuggestions(true)
  }

  const handleSelectSuggestion = (suggestion: any) => {
    onSelect(suggestion)
    setShowSuggestions(false)
  }

  return (
    <div className="relative">
      <Input
        label="Adresse du bien"
        value={value}
        onChange={handleInputChange}
        onFocus={() => setShowSuggestions(suggestions.length > 0)}
        placeholder="Tapez une adresse..."
        rightIcon={isLoading ? <Spinner size="sm" /> : undefined}
        required
      />

      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => handleSelectSuggestion(suggestion)}
              className="w-full text-left px-4 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none border-b border-gray-100 last:border-b-0"
            >
              <div className="font-medium text-gray-900">{suggestion.label}</div>
              <div className="text-sm text-gray-500">{suggestion.context}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// Composant Formulaire d'Estimation
function EstimationForm({
  onSubmit,
  isLoading,
  addressSuggestions,
  isLoadingAddresses,
  onAddressSearch,
  onClearAddressSuggestions
}: {
  onSubmit: (data: any) => void
  isLoading: boolean
  addressSuggestions: any[]
  isLoadingAddresses: boolean
  onAddressSearch: (query: string) => void
  onClearAddressSuggestions: () => void
}) {
  const [formData, setFormData] = useState({
    adresse: '',
    surface: '',
    pieces: '',
    type_bien: 'appartement',
    coordinates: null as [number, number] | null
  })

  const handleAddressSelect = (suggestion: any) => {
    setFormData({
      ...formData,
      adresse: suggestion.value,
      coordinates: suggestion.coordinates
    })
    onClearAddressSuggestions()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.surface) {
      return
    }

    onSubmit({
      adresse: formData.adresse,
      surface: parseInt(formData.surface),
      pieces: formData.pieces ? parseInt(formData.pieces) : undefined,
      type_bien: formData.type_bien as 'appartement' | 'maison',
      coordinates: formData.coordinates
    })
  }

  return (
    <FullCard title="Estimation immobilière" subtitle="Obtenez une estimation précise avec l'IA">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Adresse avec autocomplétion */}
          <div className="md:col-span-2">
            <AddressAutocomplete
              value={formData.adresse}
              onChange={(value) => setFormData({ ...formData, adresse: value })}
              onSelect={handleAddressSelect}
              suggestions={addressSuggestions}
              isLoading={isLoadingAddresses}
              onSearch={onAddressSearch}
            />
          </div>

          {/* Surface */}
          <Input
            label="Surface habitable"
            type="number"
            value={formData.surface}
            onChange={(e) => setFormData({ ...formData, surface: e.target.value })}
            placeholder="Ex: 65"
            rightIcon={<span className="text-gray-500">m²</span>}
            required
          />

          {/* Nombre de pièces */}
          <Input
            label="Nombre de pièces"
            type="number"
            value={formData.pieces}
            onChange={(e) => setFormData({ ...formData, pieces: e.target.value })}
            placeholder="Ex: 3"
            helperText="Optionnel"
          />

          {/* Type de bien */}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type de bien
            </label>
            <div className="flex space-x-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="appartement"
                  checked={formData.type_bien === 'appartement'}
                  onChange={(e) => setFormData({ ...formData, type_bien: e.target.value as any })}
                  className="mr-2 text-blue-600 focus:ring-blue-500"
                />
                Appartement
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="maison"
                  checked={formData.type_bien === 'maison'}
                  onChange={(e) => setFormData({ ...formData, type_bien: e.target.value as any })}
                  className="mr-2 text-blue-600 focus:ring-blue-500"
                />
                Maison
              </label>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            type="submit"
            isLoading={isLoading}
            loadingText="Estimation en cours..."
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            }
          >
            Estimer le bien
          </Button>
        </div>
      </form>
    </FullCard>
  )
}

// Composant Résultats d'Estimation
function EstimationResults({
  estimation,
  dossiers,
  onAssocierDossier,
  coordinates
}: {
  estimation: any
  dossiers: any[]
  onAssocierDossier: (dossierId: string) => void
  coordinates?: [number, number] | null
}) {
  const [selectedDossier, setSelectedDossier] = useState('')

  const handleAssociation = () => {
    if (selectedDossier) {
      onAssocierDossier(selectedDossier)
      setSelectedDossier('')
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(price)
  }

  return (
    <div className="space-y-6">
      {/* Fourchette d'estimation */}
      <FullCard
        title="Estimation du bien"
        actions={
          <div className="flex items-center space-x-2">
            <Badge
              variant={estimation.confiance > 0.8 ? 'success' : 'warning'}
              className="ml-2"
            >
              Confiance: {Math.round(estimation.confiance * 100)}%
            </Badge>
          </div>
        }
      >
        <div className="text-center space-y-4">
          <div>
            <p className="text-sm text-gray-600 mb-2">Prix estimé</p>
            <p className="text-4xl font-bold text-blue-600">
              {formatPrice(estimation.prix_estime)}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div className="text-center">
              <p className="text-sm text-gray-600">Fourchette basse</p>
              <p className="text-xl font-semibold text-gray-900">
                {formatPrice(estimation.fourchette_min)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-600">Fourchette haute</p>
              <p className="text-xl font-semibold text-gray-900">
                {formatPrice(estimation.fourchette_max)}
              </p>
            </div>
          </div>
        </div>
      </FullCard>

      {/* Association à un dossier */}
      <FullCard title="Associer à un dossier">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sélectionner un dossier
            </label>
            <select
              value={selectedDossier}
              onChange={(e) => setSelectedDossier(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Choisir un dossier...</option>
              {dossiers.map((dossier) => (
                <option key={dossier.id} value={dossier.id}>
                  {dossier.numero} - {dossier.parties?.[0] ?
                    `${dossier.parties[0].prenom} ${dossier.parties[0].nom}` :
                    'Client non renseigné'
                  } ({dossier.type_acte})
                </option>
              ))}
            </select>
          </div>

          <Button
            onClick={handleAssociation}
            disabled={!selectedDossier}
            size="sm"
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            }
          >
            Associer cette estimation
          </Button>
        </div>
      </FullCard>

      {/* Carte */}
      {coordinates && (
        <FullCard title="Localisation">
          <MapComponent
            center={[coordinates[1], coordinates[0]]} // Leaflet utilise [lat, lng]
            markers={[{
              position: [coordinates[1], coordinates[0]],
              popup: `Bien estimé: ${formatPrice(estimation.prix_estime)}`
            }]}
            comparables={estimation.comparables?.map((comp: any) => ({
              position: [comp.latitude || coordinates[1], comp.longitude || coordinates[0]],
              popup: `Comparable: ${formatPrice(comp.prix)} (${comp.surface}m²)`
            })) || []}
          />
        </FullCard>
      )}

      {/* Biens comparables */}
      {estimation.comparables && estimation.comparables.length > 0 && (
        <FullCard title="Biens comparables">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Adresse
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Surface
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Prix
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Prix/m²
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date vente
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {estimation.comparables.map((comp: any, index: number) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {comp.adresse}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {comp.surface} m²
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {formatPrice(comp.prix)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatPrice(Math.round(comp.prix / comp.surface))}/m²
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(comp.date_vente).toLocaleDateString('fr-FR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </FullCard>
      )}

      {/* Rapport IA */}
      {estimation.rapport_ia && (
        <FullCard title="Analyse IA">
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-gray-700">
              {estimation.rapport_ia}
            </div>
          </div>
        </FullCard>
      )}
    </div>
  )
}

// Composant Historique
function EstimationHistorique({ historique, onAssocierDossier, dossiers }: {
  historique: any[]
  onAssocierDossier: (estimationId: string, dossierId: string) => void
  dossiers: any[]
}) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(price)
  }

  if (historique.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="mt-2">Aucune estimation réalisée</p>
          <p className="text-sm">Vos estimations apparaîtront ici</p>
        </div>
      </Card>
    )
  }

  return (
    <FullCard title="Historique des estimations">
      <div className="space-y-4">
        {historique.map((estimation) => (
          <div key={estimation.id} className="border rounded-lg p-4 hover:bg-gray-50">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-medium text-gray-900 mb-2">
                  {estimation.request.adresse}
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Surface:</span>
                    <span className="ml-1 font-medium">{estimation.request.surface} m²</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Type:</span>
                    <span className="ml-1 font-medium">{estimation.request.type_bien}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Estimation:</span>
                    <span className="ml-1 font-medium text-blue-600">
                      {formatPrice(estimation.prix_estime)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Date:</span>
                    <span className="ml-1 font-medium">
                      {new Date(estimation.timestamp).toLocaleDateString('fr-FR')}
                    </span>
                  </div>
                </div>

                {estimation.dossier_associe && (
                  <div className="mt-2">
                    <Badge variant="success" size="sm">
                      Dossier {estimation.dossier_associe.numero} - {estimation.dossier_associe.client}
                    </Badge>
                  </div>
                )}
              </div>

              {!estimation.dossier_associe && (
                <div className="ml-4">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      // TODO: Ouvrir un modal pour sélectionner le dossier
                      const dossierId = prompt('ID du dossier à associer:')
                      if (dossierId) {
                        onAssocierDossier(estimation.id, dossierId)
                      }
                    }}
                  >
                    Associer
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </FullCard>
  )
}

// Page principale
export default function EstimationPage() {
  const {
    isEstimating,
    currentEstimation,
    error,
    historique,
    addressSuggestions,
    isLoadingAddresses,
    dossiers,
    estimer,
    rechercherAdresses,
    clearAddressSuggestions,
    associerDossier,
    clearCurrentEstimation
  } = useEstimation()

  const [currentCoordinates, setCurrentCoordinates] = useState<[number, number] | null>(null)

  const handleEstimation = async (data: any) => {
    setCurrentCoordinates(data.coordinates)
    await estimer(data)
  }

  const handleAssocierDossier = async (dossierId: string) => {
    if (currentEstimation && historique.length > 0) {
      await associerDossier(historique[0].id, dossierId)
    }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Estimation immobilière
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Estimation précise avec l'IA et données DVF officielles.
            </p>
          </div>

          {currentEstimation && (
            <Button
              onClick={clearCurrentEstimation}
              variant="outline"
              size="sm"
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              }
            >
              Nouvelle estimation
            </Button>
          )}
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Colonne gauche : Formulaire ou Résultats */}
          <div className="lg:col-span-2">
            {!currentEstimation ? (
              <EstimationForm
                onSubmit={handleEstimation}
                isLoading={isEstimating}
                addressSuggestions={addressSuggestions}
                isLoadingAddresses={isLoadingAddresses}
                onAddressSearch={rechercherAdresses}
                onClearAddressSuggestions={clearAddressSuggestions}
              />
            ) : (
              <EstimationResults
                estimation={currentEstimation}
                dossiers={dossiers}
                onAssocierDossier={handleAssocierDossier}
                coordinates={currentCoordinates}
              />
            )}
          </div>

          {/* Colonne droite : Historique */}
          <div>
            <EstimationHistorique
              historique={historique}
              onAssocierDossier={associerDossier}
              dossiers={dossiers}
            />
          </div>
        </div>
      </div>
    </AppLayout>
  )
}