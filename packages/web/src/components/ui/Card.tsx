/**
 * Composant Card modulaire avec header, body et footer optionnels.
 * Base pour structurer le contenu avec un design consistant.
 */
import React, { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: boolean
  shadow?: 'none' | 'sm' | 'md' | 'lg'
  border?: boolean
  hover?: boolean
}

/**
 * Classes pour les différentes intensités d'ombre
 */
const shadowClasses = {
  none: '',
  sm: 'shadow-sm',
  md: 'shadow-md',
  lg: 'shadow-lg'
}

/**
 * Composant Card principal
 */
export function Card({
  children,
  className = '',
  padding = true,
  shadow = 'sm',
  border = true,
  hover = false
}: CardProps) {
  const cardClasses = [
    'bg-white rounded-lg',
    border ? 'border border-gray-200' : '',
    shadowClasses[shadow],
    hover ? 'hover:shadow-md transition-shadow duration-200' : '',
    padding ? 'p-6' : '',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={cardClasses}>
      {children}
    </div>
  )
}

/**
 * Header de card avec titre et actions optionnelles
 */
interface CardHeaderProps {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children?: ReactNode
  className?: string
  divider?: boolean
}

export function CardHeader({
  title,
  subtitle,
  actions,
  children,
  className = '',
  divider = true
}: CardHeaderProps) {
  const headerClasses = [
    'flex items-start justify-between',
    divider ? 'pb-4 border-b border-gray-200' : 'pb-4',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={headerClasses}>
      <div className="flex-1 min-w-0">
        {/* Contenu custom ou titre/subtitle */}
        {children || (
          <div>
            {title && (
              <h3 className="text-lg font-medium text-gray-900 truncate">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-1 text-sm text-gray-500 truncate">
                {subtitle}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      {actions && (
        <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  )
}

/**
 * Body de card avec contenu principal
 */
interface CardBodyProps {
  children: ReactNode
  className?: string
  padding?: boolean
}

export function CardBody({
  children,
  className = '',
  padding = true
}: CardBodyProps) {
  const bodyClasses = [
    padding ? 'py-4' : '',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={bodyClasses}>
      {children}
    </div>
  )
}

/**
 * Footer de card avec actions ou informations
 */
interface CardFooterProps {
  children: ReactNode
  className?: string
  divider?: boolean
  justify?: 'start' | 'center' | 'end' | 'between'
}

export function CardFooter({
  children,
  className = '',
  divider = true,
  justify = 'end'
}: CardFooterProps) {
  const justifyClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between'
  }

  const footerClasses = [
    'flex items-center',
    justifyClasses[justify],
    divider ? 'pt-4 border-t border-gray-200' : 'pt-4',
    className
  ].filter(Boolean).join(' ')

  return (
    <div className={footerClasses}>
      {children}
    </div>
  )
}

/**
 * Card avec layout complet
 */
interface FullCardProps {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  bodyClassName?: string
  shadow?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
}

export function FullCard({
  title,
  subtitle,
  actions,
  children,
  footer,
  className = '',
  bodyClassName = '',
  shadow = 'sm',
  hover = false
}: FullCardProps) {
  return (
    <Card className={className} padding={false} shadow={shadow} hover={hover}>
      {/* Header si titre ou actions présents */}
      {(title || subtitle || actions) && (
        <div className="px-6 pt-6">
          <CardHeader
            title={title}
            subtitle={subtitle}
            actions={actions}
            divider={!!children || !!footer}
          />
        </div>
      )}

      {/* Body avec contenu */}
      {children && (
        <div className={`px-6 ${bodyClassName}`}>
          <CardBody>
            {children}
          </CardBody>
        </div>
      )}

      {/* Footer si présent */}
      {footer && (
        <div className="px-6 pb-6">
          <CardFooter>
            {footer}
          </CardFooter>
        </div>
      )}
    </Card>
  )
}

/**
 * Card simple avec juste contenu et titre
 */
interface SimpleCardProps {
  title?: string
  children: ReactNode
  className?: string
  titleClassName?: string
}

export function SimpleCard({
  title,
  children,
  className = '',
  titleClassName = ''
}: SimpleCardProps) {
  return (
    <Card className={className}>
      {title && (
        <h3 className={`text-lg font-medium text-gray-900 mb-4 ${titleClassName}`}>
          {title}
        </h3>
      )}
      {children}
    </Card>
  )
}

/**
 * Card statistique avec métriques
 */
interface StatCardProps {
  title: string
  value: string | number
  change?: {
    value: string | number
    type: 'increase' | 'decrease' | 'neutral'
  }
  icon?: ReactNode
  className?: string
}

export function StatCard({
  title,
  value,
  change,
  icon,
  className = ''
}: StatCardProps) {
  const changeColors = {
    increase: 'text-green-600',
    decrease: 'text-red-600',
    neutral: 'text-gray-600'
  }

  return (
    <Card className={className} hover>
      <div className="flex items-center">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 truncate">
            {title}
          </p>
          <p className="text-2xl font-semibold text-gray-900">
            {value}
          </p>
          {change && (
            <div className={`flex items-center text-sm ${changeColors[change.type]}`}>
              <span>
                {change.type === 'increase' ? '↗' : change.type === 'decrease' ? '↘' : '→'}
              </span>
              <span className="ml-1">{change.value}</span>
            </div>
          )}
        </div>

        {icon && (
          <div className="flex-shrink-0 ml-4">
            <div className="w-8 h-8 text-gray-400">
              {icon}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

/**
 * Card avec état de chargement
 */
interface LoadingCardProps {
  title?: string
  lines?: number
  className?: string
}

export function LoadingCard({
  title,
  lines = 3,
  className = ''
}: LoadingCardProps) {
  return (
    <Card className={className}>
      {title && (
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
        </div>
      )}
      <div className="animate-pulse space-y-3">
        {Array.from({ length: lines }, (_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 bg-gray-200 rounded"></div>
            {i % 2 === 0 && <div className="h-4 bg-gray-200 rounded w-5/6"></div>}
          </div>
        ))}
      </div>
    </Card>
  )
}

export default Card