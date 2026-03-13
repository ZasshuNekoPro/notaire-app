/**
 * Hook personnalisé pour la gestion des alertes avec WebSocket temps réel.
 * Logique métier : listing, filtrage, WebSocket, notifications.
 */
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import apiClient, { AlerteItem } from '@/lib/api-client'
import { useToast } from '@/components/ui/Toast'

interface AlerteFilters {
  niveau_impact?: string
  type?: string
  non_lues_seulement?: boolean
}

interface AlertesStats {
  total_alertes: number
  non_lues: number
  critiques_actives: number
  par_impact: Record<string, number>
}

interface NotificationMessage {
  type: 'alerte' | 'info' | 'warning' | 'error'
  alerte_id: string
  dossier_id?: string
  titre: string
  impact: string
  timestamp: string
  details?: Record<string, any>
}

interface UseAlertesReturn {
  // État des alertes
  alertes: AlerteItem[]
  stats: AlertesStats | null
  loading: boolean
  error: string | null

  // État WebSocket
  isConnected: boolean

  // Filtres
  filters: AlerteFilters

  // Actions
  loadAlertes: () => Promise<void>
  marquerLue: (alerteId: string) => Promise<void>
  marquerToutesLues: () => Promise<void>
  setFilters: (filters: AlerteFilters) => void
  creerAlerteTest: (data: any) => Promise<void>

  // Utilitaires
  getNombreNonLues: () => number
  getAlertesParImpact: (impact: string) => AlerteItem[]
}

/**
 * Hook principal pour la gestion des alertes
 */
export function useAlertes(): UseAlertesReturn {
  // États
  const [alertes, setAlertes] = useState<AlerteItem[]>([])
  const [stats, setStats] = useState<AlertesStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<AlerteFilters>({})

  // État WebSocket
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()
  const reconnectAttemptsRef = useRef(0)

  const toast = useToast()

  // Configuration WebSocket
  const WS_URL = process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000

  /**
   * Récupère le token JWT depuis le localStorage
   */
  const getAuthToken = useCallback((): string | null => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('auth_token')
  }, [])

  /**
   * Charge les alertes depuis l'API
   */
  const loadAlertes = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const params = {
        limit: 50,
        ...filters
      }

      const response = await apiClient.alertes.list(params)

      // Mapper les alertes avec statut "lue"
      const alertesAvecStatutLu = response.alertes.map((alerte: any) => ({
        ...alerte,
        lue: alerte.date_traitement !== null
      }))

      setAlertes(alertesAvecStatutLu)
    } catch (err: any) {
      console.error('Erreur chargement alertes:', err)
      setError(err.message || 'Erreur lors du chargement des alertes')
      toast.error('Erreur', 'Impossible de charger les alertes')
    } finally {
      setLoading(false)
    }
  }, [filters, toast])

  /**
   * Charge les statistiques des alertes
   */
  const loadStats = useCallback(async () => {
    try {
      const statsData = await apiClient.alertes.stats()
      setStats(statsData)
    } catch (err: any) {
      console.error('Erreur chargement stats:', err)
    }
  }, [])

  /**
   * Marque une alerte comme lue
   */
  const marquerLue = useCallback(async (alerteId: string) => {
    try {
      await apiClient.alertes.marquerLue(alerteId)

      // Mettre à jour l'état local
      setAlertes(prev => prev.map(alerte =>
        alerte.id === alerteId
          ? { ...alerte, lue: true, statut: 'en_cours' }
          : alerte
      ))

      // Actualiser les stats
      await loadStats()

      toast.success('Alerte marquée comme lue')
    } catch (err: any) {
      console.error('Erreur marquer lue:', err)
      toast.error('Erreur', 'Impossible de marquer l\'alerte comme lue')
    }
  }, [loadStats, toast])

  /**
   * Marque toutes les alertes comme lues
   */
  const marquerToutesLues = useCallback(async () => {
    const nonLues = alertes.filter(alerte => !alerte.lue)

    if (nonLues.length === 0) {
      toast.info('Aucune alerte non lue')
      return
    }

    try {
      await Promise.all(
        nonLues.map(alerte => apiClient.alertes.marquerLue(alerte.id))
      )

      // Mettre à jour l'état local
      setAlertes(prev => prev.map(alerte => ({ ...alerte, lue: true })))

      // Actualiser les stats
      await loadStats()

      toast.success(`${nonLues.length} alerte(s) marquée(s) comme lues`)
    } catch (err: any) {
      console.error('Erreur marquer toutes lues:', err)
      toast.error('Erreur', 'Impossible de marquer toutes les alertes')
    }
  }, [alertes, loadStats, toast])

  /**
   * Crée une alerte de test (admin uniquement)
   */
  const creerAlerteTest = useCallback(async (data: {
    titre: string
    niveau_impact: string
    contenu: string
  }) => {
    try {
      await apiClient.alertes.creerTest(data)
      toast.success('Alerte de test créée')
      await loadAlertes()
    } catch (err: any) {
      console.error('Erreur création alerte test:', err)
      toast.error('Erreur', 'Impossible de créer l\'alerte de test')
    }
  }, [loadAlertes, toast])

  /**
   * Traite un message de notification WebSocket
   */
  const traiterMessageWebSocket = useCallback((message: NotificationMessage) => {
    console.log('Message WebSocket reçu:', message)

    switch (message.type) {
      case 'alerte':
        // Nouvelle alerte reçue
        const nouvelleAlerte: AlerteItem = {
          id: message.alerte_id,
          titre: message.titre,
          niveau_impact: message.impact as any,
          statut: 'nouvelle',
          contenu: message.details?.contenu || '',
          dossier_id: message.dossier_id,
          created_at: message.timestamp,
          lue: false
        }

        // Ajouter à la liste des alertes
        setAlertes(prev => [nouvelleAlerte, ...prev])

        // Notification toast selon l'impact
        if (message.impact === 'critique') {
          toast.error(`🚨 ALERTE CRITIQUE: ${message.titre}`, '', {
            duration: 0, // Ne pas fermer automatiquement
            action: {
              label: 'Voir détails',
              handler: () => {
                // TODO: Naviguer vers l'alerte
                console.log('Navigation vers alerte:', message.alerte_id)
              }
            }
          })
        } else if (message.impact === 'fort') {
          toast.warning(`⚠️ ${message.titre}`, '', { duration: 8000 })
        } else {
          toast.info(`ℹ️ ${message.titre}`, '', { duration: 5000 })
        }

        // Mettre à jour les stats
        loadStats()
        break

      case 'info':
        toast.info(message.titre)
        break

      case 'warning':
        toast.warning(message.titre)
        break

      case 'error':
        toast.error(message.titre)
        break

      default:
        console.log('Type de message non géré:', message.type)
    }
  }, [loadStats, toast])

  /**
   * Établit la connexion WebSocket
   */
  const connecterWebSocket = useCallback(() => {
    const token = getAuthToken()

    if (!token) {
      console.warn('Impossible de connecter WebSocket: token manquant')
      return
    }

    try {
      // Fermer la connexion existante si elle existe
      if (wsRef.current) {
        wsRef.current.close()
      }

      // Nouvelle connexion WebSocket
      const ws = new WebSocket(`${WS_URL}/ws/notifications?token=${token}`)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('🔗 WebSocket connecté')
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0

        // Envoyer un ping initial
        ws.send(JSON.stringify({ type: 'ping' }))
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as NotificationMessage
          traiterMessageWebSocket(message)
        } catch (err) {
          console.error('Erreur parsing message WebSocket:', err)
        }
      }

      ws.onclose = (event) => {
        console.log('🔌 WebSocket fermé:', event.code, event.reason)
        setIsConnected(false)

        // Tentative de reconnexion automatique
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(`Tentative de reconnexion ${reconnectAttemptsRef.current}/${maxReconnectAttempts}`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connecterWebSocket()
          }, reconnectDelay)
        } else {
          setError('Connexion WebSocket perdue. Veuillez actualiser la page.')
          toast.error('Connexion temps réel perdue')
        }
      }

      ws.onerror = (error) => {
        console.error('Erreur WebSocket:', error)
        setError('Erreur de connexion WebSocket')
      }

    } catch (err) {
      console.error('Erreur création WebSocket:', err)
      setError('Impossible de créer la connexion WebSocket')
    }
  }, [getAuthToken, traiterMessageWebSocket, WS_URL, maxReconnectAttempts, reconnectDelay, toast])

  /**
   * Ferme la connexion WebSocket
   */
  const deconnecterWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
  }, [])

  /**
   * Utilitaire : Nombre d'alertes non lues
   */
  const getNombreNonLues = useCallback((): number => {
    return alertes.filter(alerte => !alerte.lue).length
  }, [alertes])

  /**
   * Utilitaire : Alertes par niveau d'impact
   */
  const getAlertesParImpact = useCallback((impact: string): AlerteItem[] => {
    return alertes.filter(alerte => alerte.niveau_impact === impact)
  }, [alertes])

  // Effet : Chargement initial et connexion WebSocket
  useEffect(() => {
    const initAsync = async () => {
      // Charger les données initiales
      await Promise.all([loadAlertes(), loadStats()])

      // Connecter WebSocket si authentifié
      const token = getAuthToken()
      if (token) {
        connecterWebSocket()
      }
    }

    initAsync()

    // Nettoyage à la désactivation
    return () => {
      deconnecterWebSocket()
    }
  }, [loadAlertes, loadStats, getAuthToken, connecterWebSocket, deconnecterWebSocket])

  // Effet : Reconnexion WebSocket si token change
  useEffect(() => {
    const token = getAuthToken()
    if (token && !isConnected && wsRef.current?.readyState !== WebSocket.CONNECTING) {
      connecterWebSocket()
    }
  }, [getAuthToken, isConnected, connecterWebSocket])

  return {
    // État des alertes
    alertes,
    stats,
    loading,
    error,

    // État WebSocket
    isConnected,

    // Filtres
    filters,

    // Actions
    loadAlertes,
    marquerLue,
    marquerToutesLues,
    setFilters,
    creerAlerteTest,

    // Utilitaires
    getNombreNonLues,
    getAlertesParImpact
  }
}

export default useAlertes