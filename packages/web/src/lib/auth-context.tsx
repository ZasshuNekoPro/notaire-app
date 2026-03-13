/**
 * AuthProvider React Context pour gestion centralisée de l'authentification.
 * Auto-récupération du profil utilisateur au chargement avec token localStorage.
 */
'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import apiClient, { UserProfile, AuthResponse } from './api-client'

// Types pour le contexte
interface AuthContextType {
  // État
  user: UserProfile | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean

  // Actions
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>

  // Utilitaires
  hasRole: (role: string) => boolean
  hasAnyRole: (roles: string[]) => boolean
}

// Contexte par défaut
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Provider Props
interface AuthProviderProps {
  children: ReactNode
}

/**
 * AuthProvider — fournit le contexte d'authentification à toute l'app
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  /**
   * Récupère le profil utilisateur depuis l'API
   */
  const refreshProfile = async (): Promise<void> => {
    try {
      setIsLoading(true)
      const profile = await apiClient.auth.me()
      setUser(profile)
    } catch (error) {
      console.error('Erreur récupération profil:', error)
      // Si erreur, on considère que l'utilisateur n'est pas authentifié
      setUser(null)
      setToken(null)
      localStorage.removeItem('auth_token')
      localStorage.removeItem('refresh_token')
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Connexion utilisateur
   */
  const login = async (email: string, password: string): Promise<void> => {
    try {
      setIsLoading(true)

      const authResponse: AuthResponse = await apiClient.auth.login(email, password)

      // Tokens déjà stockés dans localStorage par api-client
      setToken(authResponse.access_token)
      setUser(authResponse.user)

      console.log('✅ Connexion réussie pour:', email)
    } catch (error: any) {
      console.error('❌ Erreur de connexion:', error)

      // Nettoyer l'état en cas d'erreur
      setUser(null)
      setToken(null)

      // Re-lancer l'erreur pour que le composant puisse l'afficher
      throw new Error(
        error.response?.data?.detail ||
        error.message ||
        'Erreur de connexion'
      )
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Déconnexion utilisateur
   */
  const logout = async (): Promise<void> => {
    try {
      setIsLoading(true)

      // Appeler l'API de déconnexion (pour invalider le refresh token côté serveur)
      await apiClient.auth.logout()
    } catch (error) {
      // Même si l'API échoue, on déconnecte côté client
      console.warn('Erreur déconnexion API (mais déconnexion locale effectuée):', error)
    } finally {
      // Nettoyer l'état local
      setUser(null)
      setToken(null)
      setIsLoading(false)

      console.log('✅ Déconnexion effectuée')
    }
  }

  /**
   * Vérifie si l'utilisateur a un rôle spécifique
   */
  const hasRole = (role: string): boolean => {
    return user?.role === role
  }

  /**
   * Vérifie si l'utilisateur a au moins un des rôles spécifiés
   */
  const hasAnyRole = (roles: string[]): boolean => {
    return user ? roles.includes(user.role) : false
  }

  /**
   * Calcule si l'utilisateur est authentifié
   */
  const isAuthenticated = !!user && !!token

  /**
   * Effet : chargement initial
   * Vérifie si un token existe en localStorage et récupère le profil
   */
  useEffect(() => {
    const initializeAuth = async () => {
      // Vérifier si un token existe déjà
      const savedToken = localStorage.getItem('auth_token')

      if (savedToken) {
        console.log('🔑 Token trouvé, récupération du profil...')
        setToken(savedToken)
        await refreshProfile()
      } else {
        console.log('❌ Aucun token trouvé')
        setIsLoading(false)
      }
    }

    initializeAuth()
  }, [])

  /**
   * Valeur du contexte fournie aux composants enfants
   */
  const contextValue: AuthContextType = {
    // État
    user,
    token,
    isLoading,
    isAuthenticated,

    // Actions
    login,
    logout,
    refreshProfile,

    // Utilitaires
    hasRole,
    hasAnyRole
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook pour accéder au contexte d'authentification
 *
 * @returns {AuthContextType} Contexte d'authentification
 * @throws {Error} Si utilisé en dehors d'un AuthProvider
 *
 * @example
 * ```tsx
 * const { user, login, logout, isLoading } = useAuth()
 *
 * if (isLoading) return <Spinner />
 * if (!user) return <LoginPage />
 *
 * return <div>Bonjour {user.prenom} !</div>
 * ```
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)

  if (context === undefined) {
    throw new Error('useAuth doit être utilisé à l\'intérieur d\'un AuthProvider')
  }

  return context
}

/**
 * Hook pour protéger une route selon le rôle
 *
 * @param requiredRoles - Rôles autorisés (optionnel)
 * @returns {object} État d'autorisation
 *
 * @example
 * ```tsx
 * function AdminPage() {
 *   const { isAuthorized, isLoading } = useRequireAuth(['admin'])
 *
 *   if (isLoading) return <Spinner />
 *   if (!isAuthorized) return <div>Accès refusé</div>
 *
 *   return <AdminDashboard />
 * }
 * ```
 */
export function useRequireAuth(requiredRoles?: string[]) {
  const { user, isLoading, isAuthenticated, hasAnyRole } = useAuth()

  const isAuthorized = isAuthenticated && (
    !requiredRoles || // Pas de rôle requis
    hasAnyRole(requiredRoles) // A au moins un des rôles requis
  )

  return {
    isAuthorized,
    isLoading,
    user,
    missingRoles: requiredRoles && !hasAnyRole(requiredRoles)
  }
}

/**
 * Composant pour protéger des routes
 *
 * @example
 * ```tsx
 * <ProtectedRoute requiredRoles={['notaire', 'admin']}>
 *   <SensitiveComponent />
 * </ProtectedRoute>
 * ```
 */
interface ProtectedRouteProps {
  children: ReactNode
  requiredRoles?: string[]
  fallback?: ReactNode
  loadingFallback?: ReactNode
}

export function ProtectedRoute({
  children,
  requiredRoles,
  fallback = <div className="p-4 text-red-600">Accès refusé</div>,
  loadingFallback = <div className="p-4">Chargement...</div>
}: ProtectedRouteProps) {
  const { isAuthorized, isLoading } = useRequireAuth(requiredRoles)

  if (isLoading) {
    return <>{loadingFallback}</>
  }

  if (!isAuthorized) {
    return <>{fallback}</>
  }

  return <>{children}</>
}

export default AuthProvider