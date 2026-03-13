/**
 * Composant Button réutilisable avec variants et tailles.
 * Supporte les états loading, disabled et différents types.
 */
import React, { ButtonHTMLAttributes, ReactNode } from 'react'
import { Spinner } from './Spinner'

// Types des variants et tailles
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'size'> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  loadingText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  children: ReactNode
}

/**
 * Classes Tailwind pour chaque variant
 */
const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 disabled:bg-blue-300',
  secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500 disabled:bg-gray-300',
  danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 disabled:bg-red-300',
  ghost: 'bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-400 disabled:text-gray-400',
  outline: 'bg-transparent border border-gray-300 text-gray-700 hover:bg-gray-50 focus:ring-gray-400 disabled:border-gray-200 disabled:text-gray-400'
}

/**
 * Classes Tailwind pour chaque taille
 */
const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg'
}

/**
 * Composant Button principal
 */
export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loadingText,
  leftIcon,
  rightIcon,
  disabled,
  className = '',
  children,
  ...props
}: ButtonProps) {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed'

  const buttonClasses = [
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    className
  ].filter(Boolean).join(' ')

  const isDisabled = disabled || isLoading

  return (
    <button
      className={buttonClasses}
      disabled={isDisabled}
      {...props}
    >
      {/* Icon gauche */}
      {leftIcon && !isLoading && (
        <span className="mr-2 -ml-1">
          {leftIcon}
        </span>
      )}

      {/* Spinner de loading */}
      {isLoading && (
        <span className="mr-2 -ml-1">
          <Spinner size="sm" />
        </span>
      )}

      {/* Texte */}
      <span>
        {isLoading && loadingText ? loadingText : children}
      </span>

      {/* Icon droite */}
      {rightIcon && !isLoading && (
        <span className="ml-2 -mr-1">
          {rightIcon}
        </span>
      )}
    </button>
  )
}

/**
 * Variantes prédéfinies du Button pour usage fréquent
 */

export function PrimaryButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button variant="primary" {...props} />
}

export function SecondaryButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button variant="secondary" {...props} />
}

export function DangerButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button variant="danger" {...props} />
}

export function GhostButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button variant="ghost" {...props} />
}

export function OutlineButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button variant="outline" {...props} />
}

/**
 * IconButton — pour boutons avec icône uniquement
 */
interface IconButtonProps extends Omit<ButtonProps, 'children' | 'leftIcon' | 'rightIcon'> {
  icon: ReactNode
  'aria-label': string
}

export function IconButton({ icon, ...props }: IconButtonProps) {
  return (
    <Button {...props}>
      {icon}
    </Button>
  )
}

export default Button