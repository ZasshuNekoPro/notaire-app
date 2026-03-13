/**
 * Système de Toast pour les notifications avec auto-dismiss.
 * Support de différents types (success, error, warning, info) et actions.
 */
'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

// Types pour les toasts
type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
  action?: {
    label: string
    handler: () => void
  }
  dismissible?: boolean
}

interface ToastContextType {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  removeAllToasts: () => void
}

// Context pour les toasts
const ToastContext = createContext<ToastContextType | undefined>(undefined)

/**
 * Provider pour les toasts
 */
interface ToastProviderProps {
  children: ReactNode
  maxToasts?: number
}

export function ToastProvider({ children, maxToasts = 5 }: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([])

  /**
   * Ajoute un nouveau toast
   */
  const addToast = (toast: Omit<Toast, 'id'>): string => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    const newToast: Toast = {
      id,
      duration: 4000, // 4 secondes par défaut
      dismissible: true,
      ...toast
    }

    setToasts(current => {
      const updated = [newToast, ...current]
      // Limiter le nombre de toasts
      return updated.slice(0, maxToasts)
    })

    // Auto-dismiss si duration > 0
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, newToast.duration)
    }

    return id
  }

  /**
   * Supprime un toast
   */
  const removeToast = (id: string) => {
    setToasts(current => current.filter(toast => toast.id !== id))
  }

  /**
   * Supprime tous les toasts
   */
  const removeAllToasts = () => {
    setToasts([])
  }

  const contextValue: ToastContextType = {
    toasts,
    addToast,
    removeToast,
    removeAllToasts
  }

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  )
}

/**
 * Hook pour utiliser les toasts
 */
export function useToast() {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast doit être utilisé dans un ToastProvider')
  }

  const { addToast, removeToast, removeAllToasts } = context

  // Méthodes de convenance
  const toast = {
    success: (title: string, message?: string, options?: Partial<Toast>) =>
      addToast({ type: 'success', title, message, ...options }),

    error: (title: string, message?: string, options?: Partial<Toast>) =>
      addToast({ type: 'error', title, message, duration: 6000, ...options }),

    warning: (title: string, message?: string, options?: Partial<Toast>) =>
      addToast({ type: 'warning', title, message, ...options }),

    info: (title: string, message?: string, options?: Partial<Toast>) =>
      addToast({ type: 'info', title, message, ...options }),

    custom: (toast: Omit<Toast, 'id'>) => addToast(toast),

    dismiss: removeToast,
    dismissAll: removeAllToasts
  }

  return toast
}

/**
 * Container pour afficher les toasts
 */
function ToastContainer() {
  const { toasts } = useToast()

  // Protection SSR : s'assurer que toasts est un tableau
  if (!toasts || toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm w-full">
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  )
}

/**
 * Composant individual pour un toast
 */
interface ToastItemProps {
  toast: Toast
}

function ToastItem({ toast }: ToastItemProps) {
  const { removeToast } = useToast()
  const [isVisible, setIsVisible] = useState(false)
  const [isLeaving, setIsLeaving] = useState(false)

  // Animation d'entrée
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 100)
    return () => clearTimeout(timer)
  }, [])

  // Gestion de la fermeture avec animation
  const handleDismiss = () => {
    setIsLeaving(true)
    setTimeout(() => {
      removeToast(toast.id)
    }, 300)
  }

  // Configuration visuelle par type
  const typeConfig = {
    success: {
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      textColor: 'text-green-800',
      iconColor: 'text-green-400',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
      )
    },
    error: {
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      textColor: 'text-red-800',
      iconColor: 'text-red-400',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      )
    },
    warning: {
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
      textColor: 'text-yellow-800',
      iconColor: 'text-yellow-400',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )
    },
    info: {
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
      textColor: 'text-blue-800',
      iconColor: 'text-blue-400',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
      )
    }
  }

  const config = typeConfig[toast.type]

  // Classes d'animation
  const baseClasses = 'max-w-sm w-full shadow-lg rounded-lg pointer-events-auto ring-1 ring-black ring-opacity-5 overflow-hidden transition-all duration-300 transform'
  const animationClasses = isLeaving
    ? 'translate-x-full opacity-0'
    : isVisible
    ? 'translate-x-0 opacity-100'
    : 'translate-x-full opacity-0'

  const toastClasses = [
    baseClasses,
    config.bgColor,
    config.borderColor,
    animationClasses
  ].join(' ')

  return (
    <div className={toastClasses}>
      <div className="p-4">
        <div className="flex items-start">
          {/* Icône */}
          <div className={`flex-shrink-0 ${config.iconColor}`}>
            {config.icon}
          </div>

          {/* Contenu */}
          <div className="ml-3 w-0 flex-1 pt-0.5">
            <p className={`text-sm font-medium ${config.textColor}`}>
              {toast.title}
            </p>
            {toast.message && (
              <p className={`mt-1 text-sm ${config.textColor} opacity-90`}>
                {toast.message}
              </p>
            )}

            {/* Action */}
            {toast.action && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={toast.action.handler}
                  className={`text-sm font-medium ${config.textColor} hover:${config.textColor} opacity-75 hover:opacity-100 transition-opacity underline`}
                >
                  {toast.action.label}
                </button>
              </div>
            )}
          </div>

          {/* Bouton de fermeture */}
          {toast.dismissible && (
            <div className="ml-4 flex-shrink-0 flex">
              <button
                type="button"
                onClick={handleDismiss}
                className={`rounded-md inline-flex ${config.textColor} hover:${config.textColor} opacity-50 hover:opacity-75 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-${config.bgColor.split('-')[1]}-50 focus:ring-${config.iconColor.split('-')[1]}-600`}
              >
                <span className="sr-only">Fermer</span>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Barre de progression pour l'auto-dismiss */}
      {toast.duration && toast.duration > 0 && (
        <div className={`h-1 ${config.bgColor} opacity-20`}>
          <div
            className={`h-full ${config.iconColor.replace('text-', 'bg-')} transition-all ease-linear`}
            style={{
              width: '100%',
              animation: `shrink ${toast.duration}ms linear`
            }}
          />
        </div>
      )}

      <style jsx>{`
        @keyframes shrink {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  )
}

export default ToastProvider