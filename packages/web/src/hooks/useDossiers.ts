/**
 * Hook personnalisé pour la gestion des dossiers notariaux.
 * Logique métier : listing, filtrage, pagination, création.
 */
'use client'

import { useState, useEffect, useCallback } from 'react'
import apiClient, { DossierItem } from '@/lib/api-client'
import { useToast } from '@/components/ui/Toast'

interface DossierFilters {
  statut?: string
  type_acte?: string
  recherche?: string
}

interface UseDossiersReturn {
  // État
  dossiers: DossierItem[]
  loading: boolean
  error: string | null
  total: number

  // Pagination
  currentPage: number
  totalPages: number
  limit: number

  // Filtres
  filters: DossierFilters

  // Actions
  loadDossiers: () => Promise<void>
  setPage: (page: number) => void
  setFilters: (filters: DossierFilters) => void
  createDossier: (data: any) => Promise<DossierItem>
  refreshDossiers: () => Promise<void>
}

/**
 * Hook principal pour la gestion des dossiers
 */
export function useDossiers(): UseDossiersReturn {
  // États
  const [dossiers, setDossiers] = useState<DossierItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [filters, setFilters] = useState<DossierFilters>({})

  const toast = useToast()
  const limit = 20

  // Calculer le nombre total de pages
  const totalPages = Math.ceil(total / limit)

  /**
   * Charge les dossiers depuis l'API
   */
  const loadDossiers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const params = {
        limit,
        offset: (currentPage - 1) * limit,
        ...filters
      }

      const response = await apiClient.dossiers.list(params)

      setDossiers(response.dossiers)
      setTotal(response.total)
    } catch (err: any) {
      console.error('Erreur chargement dossiers:', err)
      setError(err.message || 'Erreur lors du chargement des dossiers')
      toast.error('Erreur', 'Impossible de charger les dossiers')
    } finally {
      setLoading(false)
    }
  }, [currentPage, filters, limit, toast])

  /**
   * Change la page courante
   */
  const setPage = useCallback((page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }, [totalPages])

  /**
   * Met à jour les filtres et recharge
   */
  const handleSetFilters = useCallback((newFilters: DossierFilters) => {
    setFilters(newFilters)
    setCurrentPage(1) // Reset à la page 1 lors du filtrage
  }, [])

  /**
   * Crée un nouveau dossier
   */
  const createDossier = useCallback(async (data: {
    type_acte: string
    parties: any[]
    description?: string
  }): Promise<DossierItem> => {
    try {
      const newDossier = await apiClient.dossiers.create(data)

      toast.success('Succès', 'Dossier créé avec succès')

      // Recharger la liste
      await loadDossiers()

      return newDossier
    } catch (err: any) {
      console.error('Erreur création dossier:', err)
      toast.error('Erreur', 'Impossible de créer le dossier')
      throw err
    }
  }, [loadDossiers, toast])

  /**
   * Actualise la liste des dossiers
   */
  const refreshDossiers = useCallback(async () => {
    await loadDossiers()
  }, [loadDossiers])

  // Effet : chargement initial et lors des changements
  useEffect(() => {
    loadDossiers()
  }, [loadDossiers])

  return {
    // État
    dossiers,
    loading,
    error,
    total,

    // Pagination
    currentPage,
    totalPages,
    limit,

    // Filtres
    filters,

    // Actions
    loadDossiers,
    setPage,
    setFilters: handleSetFilters,
    createDossier,
    refreshDossiers
  }
}

/**
 * Hook pour un dossier spécifique
 */
export function useDossier(dossierId: string) {
  const [dossier, setDossier] = useState<DossierItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const toast = useToast()

  const loadDossier = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const dossierData = await apiClient.dossiers.get(dossierId)
      setDossier(dossierData)
    } catch (err: any) {
      console.error('Erreur chargement dossier:', err)
      setError(err.message || 'Erreur lors du chargement du dossier')
      toast.error('Erreur', 'Impossible de charger le dossier')
    } finally {
      setLoading(false)
    }
  }, [dossierId, toast])

  useEffect(() => {
    if (dossierId) {
      loadDossier()
    }
  }, [loadDossier, dossierId])

  return {
    dossier,
    loading,
    error,
    loadDossier
  }
}

export default useDossiers