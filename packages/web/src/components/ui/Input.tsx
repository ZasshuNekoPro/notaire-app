/**
 * Composant Input avec label, message d'erreur et validation visuelle.
 * Supporte différents types d'inputs avec styling consistant.
 */
import React, { InputHTMLAttributes, ReactNode, forwardRef } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  isInvalid?: boolean
  containerClassName?: string
}

/**
 * Composant Input principal avec forwardRef pour react-hook-form
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  helperText,
  leftIcon,
  rightIcon,
  isInvalid,
  required,
  disabled,
  className = '',
  containerClassName = '',
  id,
  ...props
}, ref) => {
  // Générer un ID unique si pas fourni
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`

  // Determiner l'état d'erreur
  const hasError = isInvalid || !!error

  // Classes CSS pour l'input
  const inputClasses = [
    'block w-full rounded-lg border transition-all duration-200',
    'focus:outline-none focus:ring-2 focus:ring-offset-1',
    'disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed',
    // Padding selon les icônes
    leftIcon ? 'pl-10' : 'pl-3',
    rightIcon ? 'pr-10' : 'pr-3',
    'py-2',
    // États de validation
    hasError
      ? 'border-red-300 text-red-900 placeholder-red-300 focus:ring-red-500 focus:border-red-500'
      : 'border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-blue-500 focus:border-blue-500',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={`space-y-1 ${containerClassName}`}>
      {/* Label */}
      {label && (
        <label
          htmlFor={inputId}
          className={`block text-sm font-medium ${hasError ? 'text-red-700' : 'text-gray-700'}`}
        >
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}

      {/* Container input avec icônes */}
      <div className="relative">
        {/* Icône gauche */}
        {leftIcon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <div className={`w-4 h-4 ${hasError ? 'text-red-400' : 'text-gray-400'}`}>
              {leftIcon}
            </div>
          </div>
        )}

        {/* Input principal */}
        <input
          ref={ref}
          id={inputId}
          className={inputClasses}
          disabled={disabled}
          aria-invalid={hasError}
          aria-describedby={
            error ? `${inputId}-error` :
            helperText ? `${inputId}-helper` : undefined
          }
          {...props}
        />

        {/* Icône droite */}
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <div className={`w-4 h-4 ${hasError ? 'text-red-400' : 'text-gray-400'}`}>
              {rightIcon}
            </div>
          </div>
        )}
      </div>

      {/* Message d'erreur */}
      {error && (
        <p
          id={`${inputId}-error`}
          className="text-sm text-red-600"
          role="alert"
        >
          {error}
        </p>
      )}

      {/* Texte d'aide */}
      {helperText && !error && (
        <p
          id={`${inputId}-helper`}
          className="text-sm text-gray-500"
        >
          {helperText}
        </p>
      )}
    </div>
  )
})

Input.displayName = 'Input'

/**
 * Variantes spécialisées
 */

interface TextareaProps extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'className'> {
  label?: string
  error?: string
  helperText?: string
  isInvalid?: boolean
  containerClassName?: string
  className?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({
  label,
  error,
  helperText,
  isInvalid,
  required,
  disabled,
  className = '',
  containerClassName = '',
  id,
  rows = 3,
  ...props
}, ref) => {
  const textareaId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`
  const hasError = isInvalid || !!error

  const textareaClasses = [
    'block w-full rounded-lg border px-3 py-2 transition-all duration-200',
    'focus:outline-none focus:ring-2 focus:ring-offset-1',
    'disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed',
    'resize-vertical',
    hasError
      ? 'border-red-300 text-red-900 placeholder-red-300 focus:ring-red-500 focus:border-red-500'
      : 'border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-blue-500 focus:border-blue-500',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={`space-y-1 ${containerClassName}`}>
      {label && (
        <label
          htmlFor={textareaId}
          className={`block text-sm font-medium ${hasError ? 'text-red-700' : 'text-gray-700'}`}
        >
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}

      <textarea
        ref={ref}
        id={textareaId}
        className={textareaClasses}
        disabled={disabled}
        rows={rows}
        aria-invalid={hasError}
        aria-describedby={
          error ? `${textareaId}-error` :
          helperText ? `${textareaId}-helper` : undefined
        }
        {...props}
      />

      {error && (
        <p
          id={`${textareaId}-error`}
          className="text-sm text-red-600"
          role="alert"
        >
          {error}
        </p>
      )}

      {helperText && !error && (
        <p
          id={`${textareaId}-helper`}
          className="text-sm text-gray-500"
        >
          {helperText}
        </p>
      )}
    </div>
  )
})

Textarea.displayName = 'Textarea'

/**
 * Input pour email avec icône intégrée
 */
export function EmailInput(props: Omit<InputProps, 'type' | 'leftIcon'>) {
  return (
    <Input
      type="email"
      leftIcon={
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
        </svg>
      }
      {...props}
    />
  )
}

/**
 * Input pour mot de passe avec toggle visibilité
 */
export function PasswordInput(props: Omit<InputProps, 'type' | 'rightIcon'>) {
  const [showPassword, setShowPassword] = React.useState(false)

  return (
    <Input
      type={showPassword ? 'text' : 'password'}
      rightIcon={
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="text-gray-400 hover:text-gray-600 focus:outline-none"
        >
          {showPassword ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          )}
        </button>
      }
      {...props}
    />
  )
}

/**
 * Input pour montant avec symbole €
 */
export function CurrencyInput(props: Omit<InputProps, 'type' | 'rightIcon'>) {
  return (
    <Input
      type="number"
      step="0.01"
      min="0"
      rightIcon={
        <span className="text-gray-500 font-medium">€</span>
      }
      {...props}
    />
  )
}

export default Input