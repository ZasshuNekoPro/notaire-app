/**
 * Page centre de notifications et alertes avec WebSocket temps réel.
 */
'use client'

import { useState } from 'react'
import { AppLayout } from '@/components/layout'
import {
  Card,
  FullCard,
  Button,
  Badge,
  ImpactBadge,
  Spinner,
  LoadingCard
} from '@/components/ui'
import { useAuth } from '@/lib/auth-context'
import { useAlertes } from '@/hooks/useAlertes'

// Composant Filtres
function AlerteFilters({
  filters,
  onFiltersChange,
  stats
}: {
  filters: any
  onFiltersChange: (filters: any) => void
  stats: any
}) {
  const [localFilters, setLocalFilters] = useState(filters)

  const handleApplyFilters = () => {
    onFiltersChange(localFilters)
  }

  const handleResetFilters = () => {
    const emptyFilters = { niveau_impact: '', type: '', non_lues_seulement: false }
    setLocalFilters(emptyFilters)
    onFiltersChange(emptyFilters)
  }

  return (
    <Card className="mb-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Niveau d'impact
          </label>
          <select
            value={localFilters.niveau_impact || ''}
            onChange={(e) => setLocalFilters({...localFilters, niveau_impact: e.target.value})}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Tous les niveaux</option>
            <option value="critique">Critique</option>
            <option value="fort">Fort</option>
            <option value="moyen">Moyen</option>
            <option value="faible">Faible</option>
            <option value="info">Info</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type de source
          </label>
          <select
            value={localFilters.type || ''}
            onChange={(e) => setLocalFilters({...localFilters, type: e.target.value})}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Toutes les sources</option>
            <option value="dvf">DVF (Immobilier)</option>
            <option value="legifrance">Légifrance</option>
            <option value="bofip">BOFIP (Fiscalité)</option>
            <option value="system">Système</option>
          </select>
        </div>

        <div>
          <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mt-6">
            <input
              type="checkbox"
              checked={localFilters.non_lues_seulement || false}
              onChange={(e) => setLocalFilters({...localFilters, non_lues_seulement: e.target.checked})}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Non lues uniquement</span>
          </label>
        </div>

        <div className="flex items-end space-x-2">
          <Button onClick={handleApplyFilters} size="sm">
            Filtrer
          </Button>
          <Button onClick={handleResetFilters} variant="outline" size="sm">
            Reset
          </Button>
        </div>
      </div>

      {/* Statistiques rapides */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-200">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">{stats.total_alertes}</p>
            <p className="text-sm text-gray-500">Total alertes</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-600">{stats.non_lues}</p>
            <p className="text-sm text-gray-500">Non lues</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-700">{stats.critiques_actives}</p>
            <p className="text-sm text-gray-500">Critiques</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-orange-600">{stats.par_impact?.fort || 0}</p>
            <p className="text-sm text-gray-500">Impact fort</p>
          </div>
        </div>
      )}
    </Card>
  )
}

// Composant Modal Analyse IA
function AnalyseModal({
  isOpen,
  onClose,
  alerte
}: {
  isOpen: boolean
  onClose: () => void
  alerte: any
}) {
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analyse, setAnalyse] = useState<string>('')

  const handleAnalyse = async () => {
    setIsAnalyzing(true)
    try {
      // TODO: Appel API analyse IA de l'impact sur le dossier
      console.log('Analyse IA pour alerte:', alerte?.id)

      // Simulation d'analyse
      await new Promise(resolve => setTimeout(resolve, 2000))

      setAnalyse(`
        **Analyse d'impact pour "${alerte?.titre}"**

        Cette alerte concerne une modification juridique qui pourrait affecter vos dossiers en cours.

        **Dossiers potentiellement impactés :**
        • Dossier SUC-2024-001 : Succession Martin (impact fiscal)
        • Dossier VTE-2024-045 : Vente appartement Paris 15e (prix de référence)

        **Actions recommandées :**
        1. Réviser les calculs fiscaux des successions en cours
        2. Informer les clients concernés des nouvelles dispositions
        3. Mettre à jour les modèles d'actes

        **Urgence :** ${alerte?.niveau_impact === 'critique' ? 'IMMÉDIATE' : 'Sous 48h'}
      `)
    } catch (error) {
      console.error('Erreur analyse:', error)
    } finally {
      setIsAnalyzing(false)
    }
  }

  if (!isOpen || !alerte) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Overlay */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Modal */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">
                Analyse d'impact IA
              </h3>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div className="px-6 py-4">
            {/* Informations alerte */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">{alerte.titre}</h4>
                <ImpactBadge impact={alerte.niveau_impact} />
              </div>
              <p className="text-sm text-gray-600">{alerte.contenu}</p>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(alerte.created_at).toLocaleString('fr-FR')}
              </p>
            </div>

            {/* Analyse IA */}
            <div className="border rounded-lg p-4 bg-gray-50">
              <div className="flex items-center justify-between mb-4">
                <h5 className="font-medium text-gray-900">Analyse automatique</h5>
                {!analyse && (
                  <Button
                    onClick={handleAnalyse}
                    size="sm"
                    isLoading={isAnalyzing}
                    loadingText="Analyse en cours..."
                  >
                    Analyser l'impact
                  </Button>
                )}
              </div>

              {isAnalyzing && (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <Spinner size="lg" />
                    <p className="text-sm text-gray-600 mt-2">
                      Analyse en cours par IA...
                    </p>
                  </div>
                </div>
              )}

              {analyse && (
                <div className="prose prose-sm max-w-none">
                  <div className="whitespace-pre-line text-sm text-gray-700">
                    {analyse}
                  </div>
                </div>
              )}

              {!analyse && !isAnalyzing && (
                <div className="text-center py-8 text-gray-500">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <p className="mt-2">Cliquez sur "Analyser l'impact" pour une analyse IA détaillée</p>
                </div>
              )}
            </div>
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
            <Button onClick={onClose} variant="outline">
              Fermer
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Composant Modal Alerte Test
function CreateAlerteTestModal({
  isOpen,
  onClose,
  onSubmit
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: any) => Promise<void>
}) {
  const [formData, setFormData] = useState({
    titre: '',
    niveau_impact: 'info',
    contenu: ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await onSubmit(formData)
      setFormData({ titre: '', niveau_impact: 'info', contenu: '' })
      onClose()
    } catch (error) {
      console.error('Erreur création alerte test:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">
                Créer une alerte de test
              </h3>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Titre *
                </label>
                <input
                  type="text"
                  value={formData.titre}
                  onChange={(e) => setFormData({...formData, titre: e.target.value})}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Titre de l'alerte..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Niveau d'impact *
                </label>
                <select
                  value={formData.niveau_impact}
                  onChange={(e) => setFormData({...formData, niveau_impact: e.target.value})}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="info">Info</option>
                  <option value="faible">Faible</option>
                  <option value="moyen">Moyen</option>
                  <option value="fort">Fort</option>
                  <option value="critique">Critique</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contenu
                </label>
                <textarea
                  value={formData.contenu}
                  onChange={(e) => setFormData({...formData, contenu: e.target.value})}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Description de l'alerte..."
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Annuler
              </Button>
              <Button
                type="submit"
                isLoading={isSubmitting}
                loadingText="Création..."
                disabled={isSubmitting}
              >
                Créer
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// Page principale
export default function AlertesPage() {
  const { user } = useAuth()
  const {
    alertes,
    stats,
    loading,
    isConnected,
    filters,
    setFilters,
    marquerLue,
    marquerToutesLues,
    getNombreNonLues,
    creerAlerteTest
  } = useAlertes()

  const [selectedAlerte, setSelectedAlerte] = useState<any>(null)
  const [isAnalyseModalOpen, setIsAnalyseModalOpen] = useState(false)
  const [isCreateTestModalOpen, setIsCreateTestModalOpen] = useState(false)

  const handleAlerteClick = async (alerte: any) => {
    // Marquer comme lue si pas déjà fait
    if (!alerte.lue) {
      await marquerLue(alerte.id)
    }

    // Ouvrir le modal d'analyse
    setSelectedAlerte(alerte)
    setIsAnalyseModalOpen(true)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'dvf':
        return '🏠'
      case 'legifrance':
        return '⚖️'
      case 'bofip':
        return '💰'
      case 'system':
        return '⚙️'
      default:
        return '📢'
    }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Centre de notifications
            </h1>
            <div className="flex items-center space-x-4 mt-1">
              <p className="text-sm text-gray-600">
                Alertes et veille automatique en temps réel
              </p>
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-gray-500">
                  {isConnected ? 'Connecté' : 'Déconnecté'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex space-x-3">
            <Button
              onClick={marquerToutesLues}
              variant="outline"
              size="sm"
              disabled={getNombreNonLues() === 0}
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              }
            >
              Tout marquer comme lu
            </Button>

            {user?.role === 'admin' && (
              <Button
                onClick={() => setIsCreateTestModalOpen(true)}
                size="sm"
                leftIcon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                }
              >
                Test alerte
              </Button>
            )}
          </div>
        </div>

        {/* Filtres */}
        <AlerteFilters
          filters={filters}
          onFiltersChange={setFilters}
          stats={stats}
        />

        {/* Liste des alertes */}
        {loading ? (
          <LoadingCard lines={8} />
        ) : (
          <FullCard>
            <div className="divide-y divide-gray-200">
              {alertes.map((alerte) => (
                <div
                  key={alerte.id}
                  onClick={() => handleAlerteClick(alerte)}
                  className={`p-6 cursor-pointer hover:bg-gray-50 transition-colors ${
                    !alerte.lue ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-3 mb-2">
                        <span className="text-lg">
                          {getSourceIcon(alerte.type || 'system')}
                        </span>
                        <h3 className={`text-sm font-medium ${alerte.lue ? 'text-gray-900' : 'text-blue-900'}`}>
                          {alerte.titre}
                        </h3>
                        <ImpactBadge impact={alerte.niveau_impact} size="sm" />
                        {!alerte.lue && (
                          <Badge variant="primary" size="sm">Nouvelle</Badge>
                        )}
                      </div>

                      <p className="text-sm text-gray-600 mb-2">
                        {alerte.contenu}
                      </p>

                      <div className="flex items-center space-x-4 text-xs text-gray-500">
                        <span>{formatDate(alerte.created_at)}</span>
                        {alerte.dossier_id && (
                          <span>• Dossier lié: {alerte.dossier_id}</span>
                        )}
                        <span>• {alerte.statut}</span>
                      </div>
                    </div>

                    <div className="flex-shrink-0 ml-4">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </div>
              ))}

              {/* Message si aucune alerte */}
              {alertes.length === 0 && (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5v-5zM4.5 19.5l15-15m0 0H8.5m11 0v11" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    Aucune alerte
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Toutes vos alertes apparaîtront ici.
                  </p>
                </div>
              )}
            </div>
          </FullCard>
        )}

        {/* Modal d'analyse IA */}
        <AnalyseModal
          isOpen={isAnalyseModalOpen}
          onClose={() => setIsAnalyseModalOpen(false)}
          alerte={selectedAlerte}
        />

        {/* Modal création alerte test */}
        {user?.role === 'admin' && (
          <CreateAlerteTestModal
            isOpen={isCreateTestModalOpen}
            onClose={() => setIsCreateTestModalOpen(false)}
            onSubmit={creerAlerteTest}
          />
        )}
      </div>
    </AppLayout>
  )
}