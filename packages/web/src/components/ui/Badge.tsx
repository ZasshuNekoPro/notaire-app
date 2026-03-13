/**
 * Composant Badge pour afficher des statuts, labels et métriques.
 * Couleurs adaptées aux niveaux d'impact (alertes, statuts, etc.).
 */
import React, { ReactNode } from 'react'

type BadgeVariant = 'info' | 'success' | 'warning' | 'danger' | 'neutral' | 'primary'
type BadgeSize = 'sm' | 'md' | 'lg'

interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  size?: BadgeSize
  className?: string
  dot?: boolean
  icon?: ReactNode
  pulse?: boolean
}

/**
 * Classes Tailwind pour chaque variante de couleur
 */
const variantClasses: Record<BadgeVariant, string> = {
  info: 'bg-blue-100 text-blue-800 border-blue-200',
  success: 'bg-green-100 text-green-800 border-green-200',
  warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  danger: 'bg-red-100 text-red-800 border-red-200',
  neutral: 'bg-gray-100 text-gray-800 border-gray-200',
  primary: 'bg-indigo-100 text-indigo-800 border-indigo-200'
}

/**
 * Classes pour dots pulsants selon la variante
 */
const dotClasses: Record<BadgeVariant, string> = {
  info: 'bg-blue-400',
  success: 'bg-green-400',
  warning: 'bg-yellow-400',
  danger: 'bg-red-400',
  neutral: 'bg-gray-400',
  primary: 'bg-indigo-400'
}

/**
 * Classes pour les tailles
 */
const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-2.5 py-1.5 text-sm',
  lg: 'px-3 py-2 text-base'
}

/**
 * Composant Badge principal
 */
export function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
  dot = false,
  icon,
  pulse = false
}: BadgeProps) {
  const baseClasses = 'inline-flex items-center font-medium border rounded-full'

  const badgeClasses = [
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    className
  ].filter(Boolean).join(' ')

  return (
    <span className={badgeClasses}>
      {/* Dot indicateur */}
      {dot && (
        <span className={`w-2 h-2 rounded-full mr-1.5 ${dotClasses[variant]} ${pulse ? 'animate-pulse' : ''}`} />
      )}

      {/* Icône */}
      {icon && (
        <span className="w-3 h-3 mr-1">
          {icon}
        </span>
      )}

      {children}
    </span>
  )
}

/**
 * Badge pour niveau d'impact des alertes (mapping spécifique métier)
 */
interface ImpactBadgeProps {
  impact: 'info' | 'faible' | 'moyen' | 'fort' | 'critique'
  showDot?: boolean
  size?: BadgeSize
  className?: string
}

export function ImpactBadge({
  impact,
  showDot = true,
  size = 'sm',
  className = ''
}: ImpactBadgeProps) {
  const impactConfig = {
    info: {
      variant: 'info' as BadgeVariant,
      label: 'Info',
      pulse: false
    },
    faible: {
      variant: 'neutral' as BadgeVariant,
      label: 'Faible',
      pulse: false
    },
    moyen: {
      variant: 'warning' as BadgeVariant,
      label: 'Moyen',
      pulse: false
    },
    fort: {
      variant: 'warning' as BadgeVariant,
      label: 'Fort',
      pulse: true
    },
    critique: {
      variant: 'danger' as BadgeVariant,
      label: 'Critique',
      pulse: true
    }
  }

  const config = impactConfig[impact]

  return (
    <Badge
      variant={config.variant}
      size={size}
      dot={showDot}
      pulse={config.pulse}
      className={className}
    >
      {config.label}
    </Badge>
  )
}

/**
 * Badge pour statuts de dossiers
 */
interface StatusBadgeProps {
  status: 'nouveau' | 'en_cours' | 'en_attente' | 'termine' | 'annule'
  size?: BadgeSize
  className?: string
}

export function StatusBadge({
  status,
  size = 'sm',
  className = ''
}: StatusBadgeProps) {
  const statusConfig = {
    nouveau: {
      variant: 'primary' as BadgeVariant,
      label: 'Nouveau'
    },
    en_cours: {
      variant: 'warning' as BadgeVariant,
      label: 'En cours'
    },
    en_attente: {
      variant: 'neutral' as BadgeVariant,
      label: 'En attente'
    },
    termine: {
      variant: 'success' as BadgeVariant,
      label: 'Terminé'
    },
    annule: {
      variant: 'danger' as BadgeVariant,
      label: 'Annulé'
    }
  }

  const config = statusConfig[status]

  return (
    <Badge
      variant={config.variant}
      size={size}
      className={className}
    >
      {config.label}
    </Badge>
  )
}

/**
 * Badge numérique avec compteur (ex: nombre d'alertes)
 */
interface CountBadgeProps {
  count: number
  variant?: BadgeVariant
  max?: number
  showZero?: boolean
  className?: string
  pulse?: boolean
}

export function CountBadge({
  count,
  variant = 'danger',
  max = 99,
  showZero = false,
  className = '',
  pulse = false
}: CountBadgeProps) {
  // Ne pas afficher si count = 0 et showZero = false
  if (count === 0 && !showZero) {
    return null
  }

  const displayCount = count > max ? `${max}+` : count.toString()

  return (
    <Badge
      variant={variant}
      size="sm"
      className={`${className} min-w-[1.25rem] justify-center`}
      pulse={pulse && count > 0}
    >
      {displayCount}
    </Badge>
  )
}

/**
 * Badge avec icône prédéfinie
 */
interface IconBadgeProps {
  type: 'success' | 'error' | 'warning' | 'info'
  children: ReactNode
  size?: BadgeSize
  className?: string
}

export function IconBadge({
  type,
  children,
  size = 'md',
  className = ''
}: IconBadgeProps) {
  const icons = {
    success: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
      </svg>
    ),
    error: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
      </svg>
    ),
    warning: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
    ),
    info: (
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
      </svg>
    )
  }

  const variants: Record<string, BadgeVariant> = {
    success: 'success',
    error: 'danger',
    warning: 'warning',
    info: 'info'
  }

  return (
    <Badge
      variant={variants[type]}
      size={size}
      icon={icons[type]}
      className={className}
    >
      {children}
    </Badge>
  )
}

/**
 * Badge personnalisé pour rôles utilisateur
 */
interface RoleBadgeProps {
  role: 'admin' | 'notaire' | 'clerc' | 'client'
  size?: BadgeSize
  className?: string
}

export function RoleBadge({
  role,
  size = 'sm',
  className = ''
}: RoleBadgeProps) {
  const roleConfig = {
    admin: {
      variant: 'danger' as BadgeVariant,
      label: 'Administrateur'
    },
    notaire: {
      variant: 'primary' as BadgeVariant,
      label: 'Notaire'
    },
    clerc: {
      variant: 'info' as BadgeVariant,
      label: 'Clerc'
    },
    client: {
      variant: 'neutral' as BadgeVariant,
      label: 'Client'
    }
  }

  const config = roleConfig[role]

  return (
    <Badge
      variant={config.variant}
      size={size}
      className={className}
    >
      {config.label}
    </Badge>
  )
}

export default Badge