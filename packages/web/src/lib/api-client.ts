/**
 * Client API centralisé avec axios et gestion automatique de l'authentification.
 * Intercepteurs pour auto-refresh des tokens JWT expirés.
 */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// Types pour les réponses API
interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: {
    id: string
    email: string
    nom: string
    prenom: string
    role: string
    etude_id?: string
    is_verified: boolean
  }
}

interface RefreshResponse {
  access_token: string
  token_type: string
  expires_in: number
}

interface UserProfile {
  id: string
  email: string
  nom: string
  prenom: string
  role: string
  etude_id?: string
  is_verified: boolean
  created_at: string
  last_login?: string
}

interface EstimationStats {
  transactions_total: number
  prix_moyen_m2: number
  evolution_prix: number
  departements_couverts: string[]
}

interface EstimationAnalyse {
  prix_estime: number
  fourchette_min: number
  fourchette_max: number
  confiance: number
  comparables: any[]
  rapport_ia: string
}

interface DossierItem {
  id: string
  numero: string
  type_acte: string
  statut: string
  parties: any[]
  created_at: string
  notaire_id: string
}

interface SuccessionRapport {
  defunt: any
  heritiers: any[]
  actifs: any[]
  calculs_fiscaux: any
  documents_generes: string[]
}

interface AlerteItem {
  id: string
  titre: string
  niveau_impact: 'info' | 'faible' | 'moyen' | 'fort' | 'critique'
  statut: 'nouvelle' | 'en_cours' | 'traitee' | 'archivee'
  contenu: string
  dossier_id?: string
  created_at: string
  lue: boolean
}

// Configuration de l'API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Clés localStorage
const TOKEN_KEY = 'auth_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

class ApiClient {
  private client: AxiosInstance
  private isRefreshing = false
  private failedQueue: Array<{
    resolve: (value: string) => void
    reject: (error: any) => void
  }> = []

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 10000 // 10 secondes
    })

    this.setupInterceptors()
  }

  /**
   * Configuration des intercepteurs pour gestion automatique auth
   */
  private setupInterceptors() {
    // Intercepteur requête : ajoute token Bearer
    this.client.interceptors.request.use(
      (config) => {
        if (typeof window !== 'undefined') {
          const token = localStorage.getItem(TOKEN_KEY)
          if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
          }
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Intercepteur réponse : gestion auto-refresh 401
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            // Attendre que le refresh en cours se termine
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject })
            }).then((token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              return this.client(originalRequest)
            }).catch((err) => {
              return Promise.reject(err)
            })
          }

          originalRequest._retry = true
          this.isRefreshing = true

          try {
            const newToken = await this.refreshToken()
            this.processQueue(null, newToken)
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            return this.client(originalRequest)
          } catch (refreshError) {
            this.processQueue(refreshError, null)
            this.handleLogout()
            return Promise.reject(refreshError)
          } finally {
            this.isRefreshing = false
          }
        }

        return Promise.reject(error)
      }
    )
  }

  /**
   * Traite la queue des requêtes en attente de refresh
   */
  private processQueue(error: any, token: string | null) {
    this.failedQueue.forEach(({ resolve, reject }) => {
      if (error) {
        reject(error)
      } else {
        resolve(token!)
      }
    })

    this.failedQueue = []
  }

  /**
   * Refresh automatique du token JWT
   */
  private async refreshToken(): Promise<string> {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

    if (!refreshToken) {
      throw new Error('No refresh token available')
    }

    const response = await axios.post<RefreshResponse>(
      `${API_BASE_URL}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } }
    )

    const { access_token } = response.data
    localStorage.setItem(TOKEN_KEY, access_token)
    return access_token
  }

  /**
   * Déconnexion automatique
   */
  private handleLogout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)

    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
  }

  // ============================================================
  // MÉTHODES AUTHENTIFICATION
  // ============================================================

  auth = {
    /**
     * Connexion utilisateur
     */
    login: async (email: string, password: string): Promise<AuthResponse> => {
      const response = await this.client.post<AuthResponse>('/auth/login', {
        username: email, // FastAPI OAuth2 utilise 'username'
        password
      }, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })

      // Stocker les tokens
      localStorage.setItem(TOKEN_KEY, response.data.access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, response.data.refresh_token)

      return response.data
    },

    /**
     * Récupérer profil utilisateur connecté
     */
    me: async (): Promise<UserProfile> => {
      const response = await this.client.get<UserProfile>('/auth/me')
      return response.data
    },

    /**
     * Déconnexion
     */
    logout: async (): Promise<void> => {
      try {
        await this.client.post('/auth/logout')
      } finally {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
      }
    },

    /**
     * Refresh manuel du token
     */
    refresh: async (): Promise<RefreshResponse> => {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
      const response = await this.client.post<RefreshResponse>('/auth/refresh', {
        refresh_token: refreshToken
      })

      localStorage.setItem(TOKEN_KEY, response.data.access_token)
      return response.data
    }
  }

  // ============================================================
  // MÉTHODES ESTIMATIONS
  // ============================================================

  estimations = {
    /**
     * Statistiques globales DVF
     */
    stats: async (): Promise<EstimationStats> => {
      const response = await this.client.get<EstimationStats>('/estimations/stats')
      return response.data
    },

    /**
     * Analyse d'estimation immobilière
     */
    analyse: async (data: {
      adresse: string
      surface: number
      pieces?: number
      type_bien: 'appartement' | 'maison'
      departement?: string
    }): Promise<EstimationAnalyse> => {
      const response = await this.client.post<EstimationAnalyse>('/estimations/analyse', data)
      return response.data
    },

    /**
     * Démonstration estimation
     */
    demo: async (): Promise<EstimationAnalyse> => {
      const response = await this.client.get<EstimationAnalyse>('/estimations/demo')
      return response.data
    }
  }

  // ============================================================
  // MÉTHODES DOSSIERS
  // ============================================================

  dossiers = {
    /**
     * Liste des dossiers
     */
    list: async (params?: {
      limit?: number
      offset?: number
      type_acte?: string
      statut?: string
    }): Promise<{ dossiers: DossierItem[]; total: number }> => {
      const response = await this.client.get('/dossiers', { params })
      return response.data
    },

    /**
     * Détail d'un dossier
     */
    get: async (dossierId: string): Promise<DossierItem> => {
      const response = await this.client.get<DossierItem>(`/dossiers/${dossierId}`)
      return response.data
    },

    /**
     * Créer un nouveau dossier
     */
    create: async (data: {
      type_acte: string
      parties: any[]
      description?: string
    }): Promise<DossierItem> => {
      const response = await this.client.post<DossierItem>('/dossiers', data)
      return response.data
    }
  }

  // ============================================================
  // MÉTHODES SUCCESSIONS
  // ============================================================

  successions = {
    /**
     * Rapport de succession complet
     */
    rapport: async (successionId: string): Promise<SuccessionRapport> => {
      const response = await this.client.get<SuccessionRapport>(`/successions/${successionId}/rapport`)
      return response.data
    },

    /**
     * Calcul fiscal automatique
     */
    calculFiscal: async (data: {
      defunt: any
      heritiers: any[]
      actifs_successoraux: any[]
    }): Promise<{ calculs_fiscaux: any; rapport_pdf?: string }> => {
      const response = await this.client.post(`/successions/calcul-fiscal`, data)
      return response.data
    },

    /**
     * Création automatique par IA
     */
    creerParIA: async (formData: FormData): Promise<{
      succession_id: string
      dossier_cree: boolean
      donnees_extraites: any
    }> => {
      const response = await this.client.post('/successions/creer-par-ia', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      return response.data
    }
  }

  // ============================================================
  // MÉTHODES ALERTES
  // ============================================================

  alertes = {
    /**
     * Liste des alertes
     */
    list: async (params?: {
      limit?: number
      offset?: number
      niveau_impact?: string
      non_lues_seulement?: boolean
    }): Promise<{ alertes: AlerteItem[]; total: number }> => {
      const response = await this.client.get('/alertes', { params })
      return response.data
    },

    /**
     * Marquer une alerte comme lue
     */
    marquerLue: async (alerteId: string): Promise<void> => {
      await this.client.patch(`/alertes/${alerteId}/lire`)
    },

    /**
     * Statistiques des alertes
     */
    stats: async (): Promise<{
      total_alertes: number
      non_lues: number
      critiques_actives: number
      par_impact: Record<string, number>
    }> => {
      const response = await this.client.get('/alertes/stats')
      return response.data
    },

    /**
     * Créer alerte de test (admin)
     */
    creerTest: async (data: {
      titre: string
      niveau_impact: string
      contenu: string
    }): Promise<AlerteItem> => {
      const response = await this.client.post<AlerteItem>('/alertes/test', data)
      return response.data
    }
  }

  // ============================================================
  // MÉTHODES SIGNATURES
  // ============================================================

  signatures = {
    /**
     * Initier une signature électronique
     */
    initier: async (
      fichier: File,
      data: {
        titre_document: string
        demandeurs: Array<{
          nom: string
          prenom: string
          email: string
          telephone?: string
        }>
        callback_url?: string
        dossier_id?: string
      }
    ): Promise<{
      signature_id: string
      statut: string
      url_signature?: string
      demandeurs: any[]
    }> => {
      const formData = new FormData()
      formData.append('fichier', fichier)
      formData.append('signature_data', JSON.stringify(data))

      const response = await this.client.post('/signatures/initier', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      return response.data
    },

    /**
     * Statut d'une signature
     */
    statut: async (signatureId: string): Promise<{
      signature_id: string
      statut: string
      pourcentage_completion: number
      demandeurs: any[]
    }> => {
      const response = await this.client.get(`/signatures/${signatureId}/statut`)
      return response.data
    },

    /**
     * Télécharger document signé
     */
    telecharger: async (signatureId: string): Promise<Blob> => {
      const response = await this.client.get(`/signatures/${signatureId}/telecharger`, {
        responseType: 'blob'
      })
      return response.data
    }
  }

  // ============================================================
  // UTILITAIRES
  // ============================================================

  /**
   * Check de santé de l'API
   */
  health = async (): Promise<{
    status: string
    version: string
    services: Record<string, string>
  }> => {
    const response = await this.client.get('/health')
    return response.data
  }

  /**
   * Upload générique de fichier
   */
  upload = async (file: File, endpoint: string): Promise<any> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await this.client.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  }

  /**
   * Méthode générique pour requests custom
   */
  request = async <T>(config: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
    return this.client.request<T>(config)
  }
}

// Instance singleton
const apiClient = new ApiClient()

export default apiClient
export type {
  AuthResponse,
  UserProfile,
  EstimationStats,
  EstimationAnalyse,
  DossierItem,
  SuccessionRapport,
  AlerteItem
}