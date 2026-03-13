/**
 * Hook React pour la gestion des alertes et notifications temps réel.
 * Connexion WebSocket automatique + gestion état alertes + notifications toast.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { toast } from 'react-toastify'

// Types
interface Alerte {
  id: string
  titre: string
  niveau_impact: 'info' | 'faible' | 'moyen' | 'fort' | 'critique'
  statut: 'nouvelle' | 'en_cours' | 'traitee' | 'archivee'
  contenu: string
  dossier_id?: string
  created_at: string
  lue: boolean
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

interface AlertesStats {
  total_alertes: number
  non_lues: number
  critiques_actives: number
  par_impact: Record<string, number>
  derniere_alerte?: Alerte
}

interface UseAlertesReturn {
  // État des alertes
  alertes: Alerte[]
  stats: AlertesStats | null
  loading: boolean
  error: string | null

  // État WebSocket
  isConnected: boolean

  // Actions
  marquerLue: (alerteId: string) => Promise<void>
  actualiserAlertes: () => Promise<void>
  creerAlerteTest: (data: any) => Promise<void>

  // Utilitaires
  getNombreNonLues: () => number
  getAlertesParImpact: (impact: string) => Alerte[]
}

/**
 * Configuration de l'API
 */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS_URL = API_BASE_URL.replace('http', 'ws')

/**
 * Hook principal pour la gestion des alertes
 */
export function useAlertes(): UseAlertesReturn {
  // État des alertes
  const [alertes, setAlertes] = useState<Alerte[]>([])
  const [stats, setStats] = useState<AlertesStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // État WebSocket
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  // Configuration
  const reconnectDelay = 3000 // 3 secondes
  const maxReconnectAttempts = 5
  const reconnectAttemptsRef = useRef(0)

  /**
   * Récupère le token JWT depuis le localStorage
   */
  const getAuthToken = useCallback((): string | null => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('auth_token')
  }, [])

  /**
   * Effectue une requête API authentifiée
   */
  const apiRequest = useCallback(async (
    endpoint: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    const token = getAuthToken()

    if (!token) {
      throw new Error('Token d\'authentification manquant')
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options.headers
      }
    })

    if (!response.ok) {
      throw new Error(`Erreur API: ${response.status} ${response.statusText}`)
    }

    return response
  }, [getAuthToken])

  /**
   * Charge les alertes depuis l'API
   */
  const chargerAlertes = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiRequest('/alertes?limit=50')
      const data = await response.json()

      // Mapper les alertes avec le statut "lue"
      const alertesAvecStatutLu = data.alertes.map((alerte: any) => ({
        ...alerte,
        lue: alerte.date_traitement !== null
      }))

      setAlertes(alertesAvecStatutLu)
    } catch (err) {
      console.error('Erreur chargement alertes:', err)
      setError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  }, [apiRequest])

  /**
   * Charge les statistiques des alertes
   */
  const chargerStats = useCallback(async () => {
    try {
      const response = await apiRequest('/alertes/stats')
      const statsData = await response.json()
      setStats(statsData)
    } catch (err) {
      console.error('Erreur chargement stats:', err)
    }
  }, [apiRequest])

  /**
   * Marque une alerte comme lue
   */
  const marquerLue = useCallback(async (alerteId: string) => {
    try {
      await apiRequest(`/alertes/${alerteId}/lire`, {
        method: 'PATCH'
      })

      // Mettre à jour l'état local
      setAlertes(prev => prev.map(alerte =>
        alerte.id === alerteId
          ? { ...alerte, lue: true, statut: 'en_cours' }
          : alerte
      ))

      // Actualiser les stats
      await chargerStats()

      toast.success('Alerte marquée comme lue')
    } catch (err) {
      console.error('Erreur marquer lue:', err)
      toast.error('Erreur lors du marquage de l\'alerte')
    }
  }, [apiRequest, chargerStats])

  /**
   * Actualise les alertes
   */
  const actualiserAlertes = useCallback(async () => {
    await Promise.all([chargerAlertes(), chargerStats()])
  }, [chargerAlertes, chargerStats])

  /**
   * Crée une alerte de test (admin uniquement)
   */
  const creerAlerteTest = useCallback(async (data: any) => {
    try {
      await apiRequest('/alertes/test', {
        method: 'POST',
        body: JSON.stringify(data)
      })

      toast.success('Alerte de test créée')
      await actualiserAlertes()
    } catch (err) {
      console.error('Erreur création alerte test:', err)
      toast.error('Erreur lors de la création de l\'alerte de test')
    }
  }, [apiRequest, actualiserAlertes])

  /**
   * Traite un message de notification WebSocket
   */
  const traiterMessageWebSocket = useCallback((message: NotificationMessage) => {
    console.log('Message WebSocket reçu:', message)

    switch (message.type) {
      case 'alerte':
        // Nouvelle alerte reçue
        const nouvelleAlerte: Alerte = {
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
          toast.error(`🚨 ALERTE CRITIQUE: ${message.titre}`, {
            autoClose: false, // Ne pas fermer automatiquement
            className: 'toast-critique'
          })
        } else if (message.impact === 'fort') {
          toast.warning(`⚠️ ${message.titre}`, {
            autoClose: 8000
          })
        } else {
          toast.info(`ℹ️ ${message.titre}`, {
            autoClose: 5000
          })
        }

        // Mettre à jour les stats
        chargerStats()
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
  }, [chargerStats])

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
  }, [getAuthToken, traiterMessageWebSocket])

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
  const getAlertesParImpact = useCallback((impact: string): Alerte[] => {
    return alertes.filter(alerte => alerte.niveau_impact === impact)
  }, [alertes])

  // Effet : Chargement initial et connexion WebSocket
  useEffect(() => {
    const initAsync = async () => {
      // Charger les données initiales
      await actualiserAlertes()

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
  }, [actualiserAlertes, getAuthToken, connecterWebSocket, deconnecterWebSocket])

  // Effet : Reconnexion WebSocket si token change
  useEffect(() => {
    const token = getAuthToken()
    if (token && !isConnected && wsRef.current?.readyState !== WebSocket.CONNECTING) {
      connecterWebSocket()
    }
  }, [getAuthToken, isConnected, connecterWebSocket])

  return {
    // État
    alertes,
    stats,
    loading,
    error,
    isConnected,

    // Actions
    marquerLue,
    actualiserAlertes,
    creerAlerteTest,

    // Utilitaires
    getNombreNonLues,
    getAlertesParImpact
  }
}

/**
 * Hook pour badge de notification avec nombre non lues
 */
export function useNotificationBadge() {
  const { stats, getNombreNonLues } = useAlertes()

  return {
    nombreNonLues: getNombreNonLues(),
    critiquesActives: stats?.critiques_actives || 0,
    afficherBadge: getNombreNonLues() > 0
  }
}

/**
 * Hook pour les actions rapides sur les alertes
 */
export function useAlertesActions() {
  const { marquerLue, actualiserAlertes } = useAlertes()

  const marquerToutesLues = useCallback(async (alertes: Alerte[]) => {
    const nonLues = alertes.filter(alerte => !alerte.lue)

    try {
      await Promise.all(
        nonLues.map(alerte => marquerLue(alerte.id))
      )

      toast.success(`${nonLues.length} alerte(s) marquée(s) comme lue(s)`)
    } catch (err) {
      toast.error('Erreur lors du marquage des alertes')
    }
  }, [marquerLue])

  return {
    marquerLue,
    marquerToutesLues,
    actualiserAlertes
  }
}

export default useAlertes