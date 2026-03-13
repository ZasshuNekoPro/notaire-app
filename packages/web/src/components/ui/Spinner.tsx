/**
 * Composant Spinner pour les états de chargement.
 * Différentes tailles et variantes disponibles.
 */
import React from 'react'

type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'
type SpinnerVariant = 'primary' | 'secondary' | 'white'

interface SpinnerProps {
  size?: SpinnerSize
  variant?: SpinnerVariant
  className?: string
  label?: string
}

/**
 * Classes Tailwind pour chaque taille
 */
const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'w-3 h-3',
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
  xl: 'w-12 h-12'
}

/**
 * Classes Tailwind pour chaque variante de couleur
 */
const variantClasses: Record<SpinnerVariant, string> = {
  primary: 'text-blue-600',
  secondary: 'text-gray-600',
  white: 'text-white'
}

/**
 * Composant Spinner principal
 */
export function Spinner({
  size = 'md',
  variant = 'primary',
  className = '',
  label = 'Chargement...'
}: SpinnerProps) {
  const spinnerClasses = [
    'animate-spin',
    sizeClasses[size],
    variantClasses[variant],
    className
  ].filter(Boolean).join(' ')

  return (
    <svg
      className={spinnerClasses}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      role="status"
      aria-label={label}
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
      <span className="sr-only">{label}</span>
    </svg>
  )
}

/**
 * Spinner centré avec overlay pour couvrir une zone
 */
interface SpinnerOverlayProps {
  size?: SpinnerSize
  variant?: SpinnerVariant
  label?: string
  className?: string
  transparent?: boolean
}

export function SpinnerOverlay({
  size = 'lg',
  variant = 'primary',
  label = 'Chargement...',
  className = '',
  transparent = false
}: SpinnerOverlayProps) {
  const overlayClasses = [
    'absolute inset-0 flex items-center justify-center z-10',
    transparent ? 'bg-transparent' : 'bg-white bg-opacity-90',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={overlayClasses}>
      <div className="flex flex-col items-center space-y-2">
        <Spinner size={size} variant={variant} label={label} />
        <p className="text-sm text-gray-600">{label}</p>
      </div>
    </div>
  )
}

/**
 * Spinner en pleine page
 */
export function PageSpinner({
  label = 'Chargement de la page...'
}: {
  label?: string
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center space-y-4">
        <Spinner size="xl" variant="primary" label={label} />
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-900">
            Chargement
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            {label}
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Spinner inline pour boutons ou texte
 */
interface InlineSpinnerProps {
  size?: SpinnerSize
  variant?: SpinnerVariant
  className?: string
}

export function InlineSpinner({
  size = 'sm',
  variant = 'primary',
  className = ''
}: InlineSpinnerProps) {
  return (
    <span className={`inline-block ${className}`}>
      <Spinner size={size} variant={variant} />
    </span>
  )
}

/**
 * Composant Loading dots (alternative au spinner)
 */
interface LoadingDotsProps {
  variant?: SpinnerVariant
  className?: string
}

export function LoadingDots({
  variant = 'primary',
  className = ''
}: LoadingDotsProps) {
  const dotClasses = [
    'w-2 h-2 rounded-full animate-pulse',
    variantClasses[variant].replace('text-', 'bg-'),
    className
  ].filter(Boolean).join(' ')

  return (
    <div className="flex space-x-1" role="status" aria-label="Chargement">
      <div
        className={dotClasses}
        style={{ animationDelay: '0ms' }}
      />
      <div
        className={dotClasses}
        style={{ animationDelay: '150ms' }}
      />
      <div
        className={dotClasses}
        style={{ animationDelay: '300ms' }}
      />
      <span className="sr-only">Chargement</span>
    </div>
  )
}

/**
 * Skeleton loader pour contenu en cours de chargement
 */
interface SkeletonProps {
  className?: string
  width?: string
  height?: string
  rounded?: boolean
}

export function Skeleton({
  className = '',
  width = 'w-full',
  height = 'h-4',
  rounded = true
}: SkeletonProps) {
  const skeletonClasses = [
    'animate-pulse bg-gray-200',
    rounded ? 'rounded' : '',
    width,
    height,
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={skeletonClasses} role="status" aria-label="Chargement du contenu">
      <span className="sr-only">Chargement...</span>
    </div>
  )
}

export default Spinner