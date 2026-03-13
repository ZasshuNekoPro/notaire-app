/**
 * Page détail d'un dossier notarial avec onglets.
 */
'use client'

// Force dynamic rendering to avoid prerendering errors
export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { AppLayout } from '@/components/layout'
import {
  Card,
  FullCard,
  Button,
  Badge,
  StatusBadge,
  Spinner,
  LoadingCard,
  Input
} from '@/components/ui'
import { useDossier } from '@/hooks/useDossiers'

// Types pour les onglets
type TabType = 'informations' | 'documents' | 'succession' | 'historique'

// Composant Onglets
function TabNavigation({
  activeTab,
  onTabChange,
  dossier
}: {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  dossier: any
}) {
  const tabs = [
    { id: 'informations', label: 'Informations', icon: '📋' },
    { id: 'documents', label: 'Documents', icon: '📄' },
    ...(dossier?.type_acte === 'succession' ? [{ id: 'succession', label: 'Succession', icon: '⚖️' }] : []),
    { id: 'historique', label: 'Historique', icon: '📜' }
  ]

  return (
    <div className="border-b border-gray-200 mb-6">
      <nav className="flex space-x-8">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id as TabType)}
            className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}

// Onglet Informations
function InformationsTab({ dossier }: { dossier: any }) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Informations du dossier */}
      <FullCard title="Détails du dossier">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Référence</label>
              <p className="text-sm text-gray-900 mt-1">{dossier.numero}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Type d'acte</label>
              <p className="text-sm text-gray-900 mt-1">{dossier.type_acte}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Statut</label>
              <div className="mt-1">
                <StatusBadge status={dossier.statut as any} />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Date création</label>
              <p className="text-sm text-gray-900 mt-1">{formatDate(dossier.created_at)}</p>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-500">Description</label>
            <p className="text-sm text-gray-900 mt-1">
              {dossier.description || 'Aucune description'}
            </p>
          </div>
        </div>
      </FullCard>

      {/* Informations client */}
      <FullCard title="Parties">
        <div className="space-y-4">
          {dossier.parties?.map((partie: any, index: number) => (
            <div key={index} className="border-l-4 border-blue-500 pl-4">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-medium text-gray-900">
                    {partie.prenom} {partie.nom}
                  </h4>
                  <p className="text-sm text-gray-500">{partie.type || 'Client'}</p>
                </div>
                <Badge variant="info" size="sm">
                  {partie.type || 'Principal'}
                </Badge>
              </div>
              {partie.email && (
                <p className="text-sm text-gray-600 mt-1">
                  📧 {partie.email}
                </p>
              )}
              {partie.telephone && (
                <p className="text-sm text-gray-600">
                  📞 {partie.telephone}
                </p>
              )}
            </div>
          ))}

          {!dossier.parties?.length && (
            <div className="text-center py-8 text-gray-500">
              <p>Aucune partie renseignée</p>
            </div>
          )}
        </div>
      </FullCard>

      {/* Timeline des statuts */}
      <div className="lg:col-span-2">
        <FullCard title="Timeline du dossier">
          <div className="space-y-4">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="ml-4 flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  Dossier créé
                </p>
                <p className="text-sm text-gray-500">
                  {formatDate(dossier.created_at)}
                </p>
              </div>
            </div>

            {/* TODO: Ajouter d'autres événements de timeline */}
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="ml-4 flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  Statut actuel: {dossier.statut}
                </p>
                <p className="text-sm text-gray-500">
                  En cours de traitement
                </p>
              </div>
            </div>
          </div>
        </FullCard>
      </div>
    </div>
  )
}

// Onglet Documents
function DocumentsTab({ dossier }: { dossier: any }) {
  const [isUploading, setIsUploading] = useState(false)

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    try {
      // TODO: Implémenter l'upload via apiClient
      console.log('Upload fichier:', file.name)

      // Simulation
      await new Promise(resolve => setTimeout(resolve, 2000))
    } catch (error) {
      console.error('Erreur upload:', error)
    } finally {
      setIsUploading(false)
    }
  }

  const mockDocuments = [
    { id: 1, nom: 'Acte de vente.pdf', type: 'acte', taille: '245 KB', date: '2024-03-10' },
    { id: 2, nom: 'Pièce identité client.pdf', type: 'identite', taille: '1.2 MB', date: '2024-03-08' },
    { id: 3, nom: 'Compromis signé.pdf', type: 'compromis', taille: '856 KB', date: '2024-03-05' }
  ]

  return (
    <div className="space-y-6">
      {/* Zone d'upload */}
      <FullCard
        title="Ajouter des documents"
        actions={
          <div className="relative">
            <input
              type="file"
              onChange={handleFileUpload}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              accept=".pdf,.doc,.docx,.jpg,.png"
            />
            <Button
              size="sm"
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              }
              isLoading={isUploading}
              loadingText="Upload..."
            >
              Choisir un fichier
            </Button>
          </div>
        }
      >
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="mt-2 text-sm text-gray-600">
            Glissez-déposez vos fichiers ici ou cliquez pour sélectionner
          </p>
          <p className="text-xs text-gray-500">
            PDF, DOC, DOCX, JPG, PNG jusqu'à 10MB
          </p>
        </div>
      </FullCard>

      {/* Liste des documents */}
      <FullCard title="Documents du dossier">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Taille
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {mockDocuments.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <svg className="flex-shrink-0 h-5 w-5 text-red-500 mr-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                      </svg>
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {doc.nom}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant="info" size="sm">
                      {doc.type}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {doc.taille}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {doc.date}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button className="text-blue-600 hover:text-blue-900">
                      Voir
                    </button>
                    <button className="text-blue-600 hover:text-blue-900">
                      Télécharger
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {mockDocuments.length === 0 && (
            <div className="text-center py-12">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                Aucun document
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Commencez par uploader des documents pour ce dossier.
              </p>
            </div>
          )}
        </div>
      </FullCard>
    </div>
  )
}

// Onglet Succession
function SuccessionTab({ dossier }: { dossier: any }) {
  const [isCalculating, setIsCalculating] = useState(false)

  const handleRecalculate = async () => {
    setIsCalculating(true)
    try {
      // TODO: Appel API recalcul succession
      console.log('Recalcul succession pour dossier:', dossier.id)
      await new Promise(resolve => setTimeout(resolve, 3000))
    } catch (error) {
      console.error('Erreur recalcul:', error)
    } finally {
      setIsCalculating(false)
    }
  }

  // Données mock pour la succession
  const mockSuccession = {
    heritiers: [
      { nom: 'Martin Pierre', relation: 'Fils', part: '50%', droits: '15,500 €' },
      { nom: 'Martin Sophie', relation: 'Fille', part: '50%', droits: '15,500 €' }
    ],
    actifs: [
      { type: 'Immobilier', description: 'Maison principale', valeur: '350,000 €' },
      { type: 'Comptes bancaires', description: 'Livrets et comptes', valeur: '45,000 €' },
      { type: 'Véhicule', description: 'Voiture', valeur: '15,000 €' }
    ],
    total_actifs: '410,000 €',
    total_passifs: '25,000 €',
    net_successoral: '385,000 €',
    total_droits: '31,000 €'
  }

  return (
    <div className="space-y-6">
      {/* En-tête avec bouton recalcul */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">
          Calcul de succession
        </h3>
        <Button
          onClick={handleRecalculate}
          isLoading={isCalculating}
          loadingText="Recalcul..."
          leftIcon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          }
        >
          Recalculer les droits
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Héritiers */}
        <FullCard title="Héritiers">
          <div className="space-y-4">
            {mockSuccession.heritiers.map((heritier, index) => (
              <div key={index} className="border rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-medium text-gray-900">{heritier.nom}</h4>
                    <p className="text-sm text-gray-500">{heritier.relation}</p>
                  </div>
                  <Badge variant="info" size="sm">
                    {heritier.part}
                  </Badge>
                </div>
                <div className="mt-2">
                  <p className="text-sm font-medium text-gray-900">
                    Droits à payer: {heritier.droits}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </FullCard>

        {/* Actifs */}
        <FullCard title="Actifs successoraux">
          <div className="space-y-3">
            {mockSuccession.actifs.map((actif, index) => (
              <div key={index} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{actif.type}</p>
                  <p className="text-xs text-gray-500">{actif.description}</p>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {actif.valeur}
                </span>
              </div>
            ))}

            <div className="pt-3 mt-3 border-t border-gray-200">
              <div className="flex justify-between items-center">
                <span className="font-medium text-gray-900">Total actifs:</span>
                <span className="font-bold text-green-600">{mockSuccession.total_actifs}</span>
              </div>
              <div className="flex justify-between items-center mt-1">
                <span className="font-medium text-gray-900">Total passifs:</span>
                <span className="font-bold text-red-600">{mockSuccession.total_passifs}</span>
              </div>
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-200">
                <span className="font-bold text-gray-900">Actif net:</span>
                <span className="font-bold text-blue-600">{mockSuccession.net_successoral}</span>
              </div>
            </div>
          </div>
        </FullCard>

        {/* Résumé fiscal */}
        <FullCard title="Résumé fiscal">
          <div className="space-y-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-2">
                Total des droits de succession
              </h4>
              <p className="text-2xl font-bold text-blue-600">
                {mockSuccession.total_droits}
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Barème applicable:</span>
                <span className="font-medium">2025</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Abattement enfant:</span>
                <span className="font-medium">100,000 €</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Taux moyen:</span>
                <span className="font-medium">8.05%</span>
              </div>
            </div>

            <div className="pt-4">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                leftIcon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                }
              >
                Exporter le rapport
              </Button>
            </div>
          </div>
        </FullCard>
      </div>
    </div>
  )
}

// Onglet Historique
function HistoriqueTab({ dossier }: { dossier: any }) {
  const mockHistorique = [
    {
      id: 1,
      action: 'Création du dossier',
      utilisateur: 'Me. Dupont',
      date: '2024-03-10 14:30',
      details: 'Nouveau dossier de succession créé'
    },
    {
      id: 2,
      action: 'Upload document',
      utilisateur: 'Clerc Martin',
      date: '2024-03-11 09:15',
      details: 'Ajout de l\'acte de décès'
    },
    {
      id: 3,
      action: 'Calcul fiscal',
      utilisateur: 'Me. Dupont',
      date: '2024-03-11 16:45',
      details: 'Calcul automatique des droits de succession'
    }
  ]

  return (
    <FullCard title="Historique des actions">
      <div className="flow-root">
        <ul className="-mb-8">
          {mockHistorique.map((event, eventIdx) => (
            <li key={event.id}>
              <div className="relative pb-8">
                {eventIdx !== mockHistorique.length - 1 ? (
                  <span className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200" />
                ) : null}
                <div className="relative flex space-x-3">
                  <div>
                    <span className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center ring-8 ring-white">
                      <svg className="h-5 w-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                      </svg>
                    </span>
                  </div>
                  <div className="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {event.action}
                      </p>
                      <p className="text-sm text-gray-500">
                        par {event.utilisateur}
                      </p>
                      <p className="text-sm text-gray-500 mt-1">
                        {event.details}
                      </p>
                    </div>
                    <div className="text-right text-sm whitespace-nowrap text-gray-500">
                      {event.date}
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>

        {mockHistorique.length === 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">
              Aucun historique
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              L'historique des actions apparaîtra ici.
            </p>
          </div>
        )}
      </div>
    </FullCard>
  )
}

// Page principale
export default function DossierDetailPage() {
  const params = useParams()
  const router = useRouter()
  const dossierId = params.id as string

  const [activeTab, setActiveTab] = useState<TabType>('informations')

  const { dossier, loading, error } = useDossier(dossierId)

  if (loading) {
    return (
      <AppLayout>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <LoadingCard lines={10} />
        </div>
      </AppLayout>
    )
  }

  if (error || !dossier) {
    return (
      <AppLayout>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Card>
            <div className="text-center py-12">
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Dossier introuvable
              </h3>
              <p className="text-gray-500 mb-4">
                Le dossier demandé n'existe pas ou vous n'avez pas les droits pour y accéder.
              </p>
              <Button onClick={() => router.push('/dossiers')}>
                Retour à la liste
              </Button>
            </div>
          </Card>
        </div>
      </AppLayout>
    )
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'informations':
        return <InformationsTab dossier={dossier} />
      case 'documents':
        return <DocumentsTab dossier={dossier} />
      case 'succession':
        return <SuccessionTab dossier={dossier} />
      case 'historique':
        return <HistoriqueTab dossier={dossier} />
      default:
        return <InformationsTab dossier={dossier} />
    }
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              onClick={() => router.push('/dossiers')}
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              }
            >
              Retour
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Dossier {dossier.numero}
              </h1>
              <div className="flex items-center space-x-2 mt-1">
                <StatusBadge status={dossier.statut as any} />
                <span className="text-sm text-gray-500">
                  • {dossier.type_acte}
                </span>
              </div>
            </div>
          </div>

          <div className="flex space-x-2">
            <Button variant="outline" size="sm">
              Modifier
            </Button>
            <Button size="sm">
              Actions
            </Button>
          </div>
        </div>

        {/* Navigation onglets */}
        <TabNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
          dossier={dossier}
        />

        {/* Contenu onglet */}
        {renderTabContent()}
      </div>
    </AppLayout>
  )
}