/**
 * Page liste des dossiers notariaux avec tableau, filtres et pagination.
 */
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AppLayout } from '@/components/layout'
import {
  Card,
  FullCard,
  Button,
  Input,
  Badge,
  StatusBadge,
  Spinner,
  LoadingCard
} from '@/components/ui'
import { useDossiers } from '@/hooks/useDossiers'

// Composant Modal de création de dossier
function CreateDossierModal({
  isOpen,
  onClose,
  onSubmit
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: any) => Promise<void>
}) {
  const [formData, setFormData] = useState({
    type_acte: '',
    client_nom: '',
    client_prenom: '',
    description: ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      await onSubmit({
        type_acte: formData.type_acte,
        parties: [
          {
            type: 'client',
            nom: formData.client_nom,
            prenom: formData.client_prenom
          }
        ],
        description: formData.description
      })

      // Reset form et fermer
      setFormData({ type_acte: '', client_nom: '', client_prenom: '', description: '' })
      onClose()
    } catch (error) {
      console.error('Erreur création:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Overlay */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Modal */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">
                Nouveau dossier
              </h3>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type d'acte *
                </label>
                <select
                  value={formData.type_acte}
                  onChange={(e) => setFormData({...formData, type_acte: e.target.value})}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Sélectionner...</option>
                  <option value="vente">Vente immobilière</option>
                  <option value="succession">Succession</option>
                  <option value="donation">Donation</option>
                  <option value="hypotheque">Hypothèque</option>
                  <option value="sci">Constitution SCI</option>
                  <option value="autre">Autre acte</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Nom client *"
                  value={formData.client_nom}
                  onChange={(e) => setFormData({...formData, client_nom: e.target.value})}
                  required
                />
                <Input
                  label="Prénom client *"
                  value={formData.client_prenom}
                  onChange={(e) => setFormData({...formData, client_prenom: e.target.value})}
                  required
                />
              </div>

              <Input
                label="Description"
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                helperText="Description optionnelle du dossier"
              />
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

// Composant Filtres
function DossierFilters({
  filters,
  onFiltersChange
}: {
  filters: any
  onFiltersChange: (filters: any) => void
}) {
  const [localFilters, setLocalFilters] = useState(filters)

  const handleApplyFilters = () => {
    onFiltersChange(localFilters)
  }

  const handleResetFilters = () => {
    const emptyFilters = { statut: '', type_acte: '', recherche: '' }
    setLocalFilters(emptyFilters)
    onFiltersChange(emptyFilters)
  }

  return (
    <Card className="mb-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Statut
          </label>
          <select
            value={localFilters.statut || ''}
            onChange={(e) => setLocalFilters({...localFilters, statut: e.target.value})}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Tous les statuts</option>
            <option value="nouveau">Nouveau</option>
            <option value="en_cours">En cours</option>
            <option value="en_attente">En attente</option>
            <option value="termine">Terminé</option>
            <option value="annule">Annulé</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type d'acte
          </label>
          <select
            value={localFilters.type_acte || ''}
            onChange={(e) => setLocalFilters({...localFilters, type_acte: e.target.value})}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Tous les types</option>
            <option value="vente">Vente</option>
            <option value="succession">Succession</option>
            <option value="donation">Donation</option>
            <option value="hypotheque">Hypothèque</option>
            <option value="sci">SCI</option>
          </select>
        </div>

        <div>
          <Input
            label="Recherche"
            value={localFilters.recherche || ''}
            onChange={(e) => setLocalFilters({...localFilters, recherche: e.target.value})}
            placeholder="Client, référence..."
          />
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
    </Card>
  )
}

// Composant Pagination
function Pagination({
  currentPage,
  totalPages,
  onPageChange
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}) {
  if (totalPages <= 1) return null

  const pages = []
  const maxVisiblePages = 5

  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2))
  let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1)

  if (endPage - startPage < maxVisiblePages - 1) {
    startPage = Math.max(1, endPage - maxVisiblePages + 1)
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i)
  }

  return (
    <div className="flex items-center justify-between mt-6">
      <div className="text-sm text-gray-700">
        Page {currentPage} sur {totalPages}
      </div>

      <div className="flex items-center space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          Précédent
        </Button>

        {pages.map(page => (
          <Button
            key={page}
            variant={page === currentPage ? "primary" : "outline"}
            size="sm"
            onClick={() => onPageChange(page)}
            className="min-w-[2.5rem]"
          >
            {page}
          </Button>
        ))}

        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
        >
          Suivant
        </Button>
      </div>
    </div>
  )
}

// Page principale
export default function DossiersPage() {
  const router = useRouter()
  const {
    dossiers,
    loading,
    total,
    currentPage,
    totalPages,
    filters,
    setPage,
    setFilters,
    createDossier
  } = useDossiers()

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  const handleRowClick = (dossier: any) => {
    router.push(`/dossiers/${dossier.id}`)
  }

  const handleCreateDossier = async (data: any) => {
    await createDossier(data)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    })
  }

  const getTypeActeLabel = (type: string) => {
    const labels: Record<string, string> = {
      vente: 'Vente',
      succession: 'Succession',
      donation: 'Donation',
      hypotheque: 'Hypothèque',
      sci: 'SCI'
    }
    return labels[type] || type
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Dossiers notariaux
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Gestion de tous vos dossiers clients et actes notariaux.
            </p>
          </div>

          <Button
            onClick={() => setIsCreateModalOpen(true)}
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            }
          >
            Nouveau dossier
          </Button>
        </div>

        {/* Filtres */}
        <DossierFilters
          filters={filters}
          onFiltersChange={setFilters}
        />

        {/* Statistiques rapides */}
        <div className="mb-6 text-sm text-gray-600">
          {loading ? (
            <Spinner size="sm" className="inline mr-2" />
          ) : (
            <>
              <strong>{total}</strong> dossier{total > 1 ? 's' : ''} trouvé{total > 1 ? 's' : ''}
            </>
          )}
        </div>

        {/* Tableau des dossiers */}
        {loading ? (
          <LoadingCard lines={8} />
        ) : (
          <FullCard>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Référence
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Client
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type d'acte
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Statut
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date création
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Notaire
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {dossiers.map((dossier) => (
                    <tr
                      key={dossier.id}
                      onClick={() => handleRowClick(dossier)}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-blue-600">
                          {dossier.numero}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {dossier.parties?.[0] ? (
                            `${dossier.parties[0].prenom} ${dossier.parties[0].nom}`
                          ) : (
                            'Non renseigné'
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {getTypeActeLabel(dossier.type_acte)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <StatusBadge status={dossier.statut as any} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(dossier.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {dossier.notaire_id || 'Non assigné'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Message si aucun résultat */}
              {dossiers.length === 0 && !loading && (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    Aucun dossier trouvé
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Commencez par créer un nouveau dossier.
                  </p>
                  <div className="mt-6">
                    <Button
                      onClick={() => setIsCreateModalOpen(true)}
                      size="sm"
                    >
                      Nouveau dossier
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Pagination */}
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </FullCard>
        )}

        {/* Modal création */}
        <CreateDossierModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSubmit={handleCreateDossier}
        />
      </div>
    </AppLayout>
  )
}