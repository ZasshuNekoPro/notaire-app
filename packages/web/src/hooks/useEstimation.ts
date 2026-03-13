/**
 * Hook personnalisé pour l'estimation immobilière avec IA et intégration dossiers.
 * Logique métier : estimation, autocomplétion BAN, historique, association dossier.
 */
'use client'

import { useState, useEffect, useCallback } from 'react'
import apiClient, { EstimationAnalyse, DossierItem } from '@/lib/api-client'
import { useToast } from '@/components/ui/Toast'

interface EstimationRequest {
  adresse: string
  surface: number
  pieces?: number
  type_bien: 'appartement' | 'maison'
  departement?: string
}

interface EstimationHistorique extends EstimationAnalyse {
  id: string
  timestamp: string
  request: EstimationRequest
  dossier_associe?: {
    id: string
    numero: string
    client: string
  }
}

interface AdresseSuggestion {
  label: string
  value: string
  context: string
  coordinates: [number, number]
}

interface UseEstimationReturn {
  // État principal
  isEstimating: boolean
  currentEstimation: EstimationAnalyse | null
  error: string | null

  // Historique
  historique: EstimationHistorique[]

  // Autocomplétion adresse
  isLoadingAddresses: boolean
  addressSuggestions: AdresseSuggestion[]

  // Dossiers pour association
  dossiers: DossierItem[]
  isLoadingDossiers: boolean

  // Actions principales
  estimer: (request: EstimationRequest) => Promise<void>
  rechercherAdresses: (query: string) => Promise<void>
  clearAddressSuggestions: () => void
  loadDossiers: () => Promise<void>
  associerDossier: (estimationId: string, dossierId: string) => Promise<void>

  // Utilitaires
  clearCurrentEstimation: () => void
  clearHistorique: () => void
}

/**
 * Hook principal pour l'estimation immobilière
 */
export function useEstimation(): UseEstimationReturn {
  // États principaux
  const [isEstimating, setIsEstimating] = useState(false)
  const [currentEstimation, setCurrentEstimation] = useState<EstimationAnalyse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Historique des estimations
  const [historique, setHistorique] = useState<EstimationHistorique[]>([])

  // Autocomplétion adresse
  const [isLoadingAddresses, setIsLoadingAddresses] = useState(false)
  const [addressSuggestions, setAddressSuggestions] = useState<AdresseSuggestion[]>([])

  // Dossiers pour association
  const [dossiers, setDossiers] = useState<DossierItem[]>([])
  const [isLoadingDossiers, setIsLoadingDossiers] = useState(false)

  const toast = useToast()

  /**
   * Lance une estimation immobilière
   */
  const estimer = useCallback(async (request: EstimationRequest) => {
    try {
      setIsEstimating(true)
      setError(null)

      const estimation = await apiClient.estimations.analyse(request)

      // Créer une entrée d'historique
      const historiqueItem: EstimationHistorique = {
        ...estimation,
        id: `est_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date().toISOString(),
        request
      }

      setCurrentEstimation(estimation)
      setHistorique(prev => [historiqueItem, ...prev])

      toast.success('Estimation terminée', 'Votre estimation immobilière est prête')

    } catch (err: any) {
      console.error('Erreur estimation:', err)
      setError(err.message || 'Erreur lors de l\'estimation')
      toast.error('Erreur', 'Impossible de réaliser l\'estimation')
    } finally {
      setIsEstimating(false)
    }
  }, [toast])

  /**
   * Recherche d'adresses avec l'API BAN
   */
  const rechercherAdresses = useCallback(async (query: string) => {
    if (!query || query.length < 3) {
      setAddressSuggestions([])
      return
    }

    try {
      setIsLoadingAddresses(true)

      // Appel à l'API BAN (Base Adresse Nationale)
      const response = await fetch(
        `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(query)}&limit=5`
      )

      if (!response.ok) {
        throw new Error('Erreur recherche adresse')
      }

      const data = await response.json()

      const suggestions: AdresseSuggestion[] = data.features.map((feature: any) => ({
        label: feature.properties.label,
        value: feature.properties.label,
        context: feature.properties.context,
        coordinates: feature.geometry.coordinates as [number, number]
      }))

      setAddressSuggestions(suggestions)

    } catch (err: any) {
      console.error('Erreur recherche adresses:', err)
      setAddressSuggestions([])
    } finally {
      setIsLoadingAddresses(false)
    }
  }, [])

  /**
   * Efface les suggestions d'adresses
   */
  const clearAddressSuggestions = useCallback(() => {
    setAddressSuggestions([])
  }, [])

  /**
   * Charge la liste des dossiers pour association
   */
  const loadDossiers = useCallback(async () => {
    try {
      setIsLoadingDossiers(true)

      const response = await apiClient.dossiers.list({
        statut: 'en_cours', // Seulement les dossiers en cours
        limit: 50
      })

      setDossiers(response.dossiers)

    } catch (err: any) {
      console.error('Erreur chargement dossiers:', err)
      toast.error('Erreur', 'Impossible de charger les dossiers')
    } finally {
      setIsLoadingDossiers(false)
    }
  }, [toast])

  /**
   * Associe une estimation à un dossier
   */
  const associerDossier = useCallback(async (estimationId: string, dossierId: string) => {
    try {
      const dossier = dossiers.find(d => d.id === dossierId)
      if (!dossier) {
        throw new Error('Dossier introuvable')
      }

      // Mettre à jour l'historique avec l'association
      setHistorique(prev => prev.map(item =>
        item.id === estimationId
          ? {
              ...item,
              dossier_associe: {
                id: dossier.id,
                numero: dossier.numero,
                client: dossier.parties?.[0]
                  ? `${dossier.parties[0].prenom} ${dossier.parties[0].nom}`
                  : 'Client non renseigné'
              }
            }
          : item
      ))

      // TODO: Appel API pour sauvegarder l'association
      // await apiClient.estimations.associerDossier(estimationId, dossierId)

      toast.success('Association réussie', `Estimation associée au dossier ${dossier.numero}`)

    } catch (err: any) {
      console.error('Erreur association dossier:', err)
      toast.error('Erreur', 'Impossible d\'associer le dossier')
    }
  }, [dossiers, toast])

  /**
   * Efface l'estimation courante
   */
  const clearCurrentEstimation = useCallback(() => {
    setCurrentEstimation(null)
    setError(null)
  }, [])

  /**
   * Efface l'historique des estimations
   */
  const clearHistorique = useCallback(() => {
    setHistorique([])
  }, [])

  // Effet : Charger les dossiers au montage
  useEffect(() => {
    loadDossiers()
  }, [loadDossiers])

  return {
    // État principal
    isEstimating,
    currentEstimation,
    error,

    // Historique
    historique,

    // Autocomplétion adresse
    isLoadingAddresses,
    addressSuggestions,

    // Dossiers pour association
    dossiers,
    isLoadingDossiers,

    // Actions principales
    estimer,
    rechercherAdresses,
    clearAddressSuggestions,
    loadDossiers,
    associerDossier,

    // Utilitaires
    clearCurrentEstimation,
    clearHistorique
  }
}

export default useEstimation