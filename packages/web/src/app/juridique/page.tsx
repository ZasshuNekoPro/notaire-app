/**
 * Page assistant juridique RAG avec streaming et génération d'actes.
 */
'use client'

import { useState } from 'react'
import { AppLayout } from '@/components/layout'
import {
  Card,
  FullCard,
  Button,
  Input,
  Textarea,
  Badge,
  Spinner,
  LoadingCard
} from '@/components/ui'
import { useAuth } from '@/lib/auth-context'
import { useJuridique } from '@/hooks/useJuridique'

// Types pour les onglets
type TabType = 'questions' | 'actes'

// Composant Navigation Onglets
function TabNavigation({
  activeTab,
  onTabChange
}: {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
}) {
  const tabs = [
    { id: 'questions', label: 'Questions juridiques', icon: '❓' },
    { id: 'actes', label: 'Rédiger un acte', icon: '📝' }
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

// Composant Formulaire Question
function QuestionForm({
  onSubmit,
  isLoading,
  dossiers
}: {
  onSubmit: (data: any) => void
  isLoading: boolean
  dossiers: any[]
}) {
  const [formData, setFormData] = useState({
    question: '',
    dossier_id: ''
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.question.trim()) return

    onSubmit({
      question: formData.question,
      dossier_id: formData.dossier_id || undefined
    })

    setFormData({ question: '', dossier_id: formData.dossier_id })
  }

  return (
    <FullCard title="Poser une question juridique">
      <form onSubmit={handleSubmit} className="space-y-6">
        <Textarea
          label="Votre question"
          value={formData.question}
          onChange={(e) => setFormData({ ...formData, question: e.target.value })}
          rows={4}
          placeholder="Ex: Quel est l'abattement pour un enfant en 2025 ?"
          required
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Contexte dossier (optionnel)
          </label>
          <select
            value={formData.dossier_id}
            onChange={(e) => setFormData({ ...formData, dossier_id: e.target.value })}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Pas de contexte spécifique</option>
            {dossiers.map((dossier) => (
              <option key={dossier.id} value={dossier.id}>
                {dossier.numero} - {dossier.parties?.[0] ?
                  `${dossier.parties[0].prenom} ${dossier.parties[0].nom}` :
                  'Client non renseigné'
                } ({dossier.type_acte})
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end">
          <Button
            type="submit"
            isLoading={isLoading}
            loadingText="Recherche en cours..."
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16l2.879-2.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
          >
            Poser la question
          </Button>
        </div>
      </form>
    </FullCard>
  )
}

// Composant Réponse Juridique
function ReponseJuridique({
  reponse,
  getConfidenceColor
}: {
  reponse: any
  getConfidenceColor: (confiance: string) => string
}) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('fr-FR')
  }

  const openSource = (url: string) => {
    window.open(url, '_blank')
  }

  return (
    <FullCard
      title={`Question: ${reponse.question}`}
      actions={
        <div className="flex items-center space-x-2">
          <Badge variant={getConfidenceColor(reponse.confiance) as any}>
            Confiance: {reponse.confiance}
          </Badge>
          {reponse.dossier_numero && (
            <Badge variant="info" size="sm">
              Dossier {reponse.dossier_numero}
            </Badge>
          )}
        </div>
      }
    >
      <div className="space-y-6">
        {/* Réponse principale */}
        <div>
          <div className="prose prose-sm max-w-none">
            <div
              className="text-gray-700"
              dangerouslySetInnerHTML={{
                __html: reponse.reponse.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              }}
            />
          </div>
        </div>

        {/* Sources citées */}
        {reponse.sources && reponse.sources.length > 0 && (
          <div>
            <h4 className="font-medium text-gray-900 mb-3">Sources citées</h4>
            <div className="space-y-3">
              {reponse.sources.map((source: any, index: number) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer"
                  onClick={() => openSource(source.url)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h5 className="font-medium text-blue-600 hover:text-blue-800">
                        {source.titre}
                      </h5>
                      <p className="text-sm text-gray-600 mt-1">
                        "{source.extrait}"
                      </p>
                    </div>
                    <div className="ml-4">
                      <Badge
                        variant={source.pertinence > 0.9 ? 'success' : source.pertinence > 0.7 ? 'warning' : 'neutral'}
                        size="sm"
                      >
                        {Math.round(source.pertinence * 100)}%
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Métadonnées */}
        <div className="text-xs text-gray-500 pt-4 border-t">
          Répondu le {formatDate(reponse.timestamp)}
        </div>
      </div>
    </FullCard>
  )
}

// Composant Historique Questions
function HistoriqueQuestions({
  historique,
  getConfidenceColor
}: {
  historique: any[]
  getConfidenceColor: (confiance: string) => string
}) {
  if (historique.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-3.582 8-8 8a8.959 8.959 0 01-4.906-1.451c-.905-.545-1.94-.818-3.094-.818H3a1 1 0 01-1-1v-3.5c0-1.105.895-2 2-2h6.5c1.055 0 1.915-.803 1.99-1.842.075-.99-.395-1.88-1.1-2.558a.996.996 0 01-.281-.707c0-.552.448-1 1-1s1 .448 1 1c0 .257-.098.502-.281.707a3.936 3.936 0 00.281 5.551z" />
          </svg>
          <p className="mt-2">Aucune question posée</p>
          <p className="text-sm">Vos questions et réponses apparaîtront ici</p>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {historique.map((reponse) => (
        <ReponseJuridique
          key={reponse.id}
          reponse={reponse}
          getConfidenceColor={getConfidenceColor}
        />
      ))}
    </div>
  )
}

// Composant Génération d'Acte
function GenerationActe({
  onGenerate,
  isGenerating,
  currentGeneration,
  onStopGeneration,
  onExport,
  onCopy
}: {
  onGenerate: (type: string, parametres: any) => void
  isGenerating: boolean
  currentGeneration: any
  onStopGeneration: () => void
  onExport: (generation: any) => void
  onCopy: (generation: any) => void
}) {
  const [formData, setFormData] = useState({
    type_acte: 'vente',
    vendeur_nom: '',
    acquereur_nom: '',
    adresse: '',
    surface: '',
    prix: ''
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const parametres = {
      vendeur_nom: formData.vendeur_nom,
      acquereur_nom: formData.acquereur_nom,
      adresse: formData.adresse,
      surface: formData.surface,
      prix: formData.prix
    }

    onGenerate(formData.type_acte, parametres)
  }

  return (
    <div className="space-y-6">
      {/* Formulaire de génération */}
      {!isGenerating && (
        <FullCard title="Paramètres de l'acte">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Type d'acte
              </label>
              <select
                value={formData.type_acte}
                onChange={(e) => setFormData({ ...formData, type_acte: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="vente">Acte de vente</option>
                <option value="donation">Acte de donation</option>
                <option value="succession">Acte de partage succession</option>
                <option value="hypotheque">Acte d'hypothèque</option>
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Input
                label="Nom du vendeur/donateur"
                value={formData.vendeur_nom}
                onChange={(e) => setFormData({ ...formData, vendeur_nom: e.target.value })}
                placeholder="M. MARTIN Pierre"
              />

              <Input
                label="Nom de l'acquéreur/donataire"
                value={formData.acquereur_nom}
                onChange={(e) => setFormData({ ...formData, acquereur_nom: e.target.value })}
                placeholder="Mme DUPONT Sophie"
              />

              <Input
                label="Adresse du bien"
                value={formData.adresse}
                onChange={(e) => setFormData({ ...formData, adresse: e.target.value })}
                placeholder="123 rue de la Paix, 75001 PARIS"
              />

              <Input
                label="Surface"
                value={formData.surface}
                onChange={(e) => setFormData({ ...formData, surface: e.target.value })}
                placeholder="65"
                rightIcon={<span className="text-gray-500">m²</span>}
              />

              <Input
                label="Prix"
                value={formData.prix}
                onChange={(e) => setFormData({ ...formData, prix: e.target.value })}
                placeholder="450000"
                rightIcon={<span className="text-gray-500">€</span>}
              />
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                leftIcon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                }
              >
                Générer l'acte
              </Button>
            </div>
          </form>
        </FullCard>
      )}

      {/* Génération en cours */}
      {isGenerating && currentGeneration && (
        <FullCard
          title="Génération en cours..."
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={onStopGeneration}
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10l6 6m0-6l-6 6" />
                </svg>
              }
            >
              Arrêter
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Spinner size="sm" />
              <span className="text-sm text-gray-600">
                Rédaction de l'acte avec l'IA...
              </span>
            </div>

            <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm font-mono text-gray-700">
                {currentGeneration.contenu}
              </pre>
              {isGenerating && (
                <div className="inline-block w-2 h-5 bg-blue-600 animate-pulse ml-1" />
              )}
            </div>
          </div>
        </FullCard>
      )}

      {/* Acte généré */}
      {currentGeneration && currentGeneration.statut === 'termine' && (
        <FullCard
          title={`${currentGeneration.type_acte} - Généré avec succès`}
          actions={
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onCopy(currentGeneration)}
                leftIcon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                }
              >
                Copier
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onExport(currentGeneration)}
                leftIcon={
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                }
              >
                Télécharger .docx
              </Button>
            </div>
          }
        >
          <div className="bg-white border rounded-lg p-6 max-h-96 overflow-y-auto">
            <div className="prose prose-sm max-w-none">
              <pre className="whitespace-pre-wrap font-serif text-gray-800 leading-relaxed">
                {currentGeneration.contenu}
              </pre>
            </div>
          </div>
        </FullCard>
      )}
    </div>
  )
}

// Page principale
export default function JuridiquePage() {
  const { user } = useAuth()
  const {
    isAsking,
    historique,
    error,
    isGenerating,
    currentGeneration,
    dossiers,
    poserQuestion,
    genererActe,
    stopGeneration,
    exporterActe,
    copierActe,
    getConfidenceColor,
    clearHistorique
  } = useJuridique()

  const [activeTab, setActiveTab] = useState<TabType>('questions')

  const handleQuestionSubmit = async (data: any) => {
    await poserQuestion(data)
  }

  const handleActeGenerate = async (type: string, parametres: any) => {
    await genererActe(type, parametres)
  }

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Assistant juridique
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Questions juridiques et rédaction d'actes avec l'IA RAG.
            </p>
          </div>

          <div className="flex space-x-3">
            <Button
              onClick={clearHistorique}
              variant="outline"
              size="sm"
              leftIcon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              }
            >
              Effacer l'historique
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}

        {/* Navigation onglets */}
        <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Colonne principale */}
          <div className="lg:col-span-2">
            {activeTab === 'questions' ? (
              <div className="space-y-6">
                <QuestionForm
                  onSubmit={handleQuestionSubmit}
                  isLoading={isAsking}
                  dossiers={dossiers}
                />

                <HistoriqueQuestions
                  historique={historique}
                  getConfidenceColor={getConfidenceColor}
                />
              </div>
            ) : (
              <GenerationActe
                onGenerate={handleActeGenerate}
                isGenerating={isGenerating}
                currentGeneration={currentGeneration}
                onStopGeneration={stopGeneration}
                onExport={exporterActe}
                onCopy={copierActe}
              />
            )}
          </div>

          {/* Colonne droite : Aide et conseils */}
          <div className="space-y-6">
            <FullCard title="Aide & conseils">
              <div className="space-y-4 text-sm">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">💡 Questions suggérées</h4>
                  <div className="space-y-1">
                    <button
                      onClick={() => poserQuestion({ question: "Quel est l'abattement pour un enfant en 2025 ?" })}
                      className="block w-full text-left text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded text-xs"
                    >
                      Abattement enfant 2025
                    </button>
                    <button
                      onClick={() => poserQuestion({ question: "Quels sont les délais pour accepter une succession ?" })}
                      className="block w-full text-left text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded text-xs"
                    >
                      Délais succession
                    </button>
                    <button
                      onClick={() => poserQuestion({ question: "Comment calculer les droits de mutation ?" })}
                      className="block w-full text-left text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded text-xs"
                    >
                      Droits de mutation
                    </button>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-medium text-gray-900 mb-2">📚 Sources disponibles</h4>
                  <div className="space-y-1 text-xs text-gray-600">
                    <div>• Code civil français</div>
                    <div>• Code général des impôts</div>
                    <div>• BOFIP (documentation fiscale)</div>
                    <div>• Jurisprudence récente</div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-medium text-gray-900 mb-2">⚖️ Niveaux de confiance</h4>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <Badge variant="success" size="sm">Élevée</Badge>
                      <span className="text-xs text-gray-600">Sources officielles multiples</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="warning" size="sm">Moyenne</Badge>
                      <span className="text-xs text-gray-600">Sources partielles</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="danger" size="sm">Faible</Badge>
                      <span className="text-xs text-gray-600">À vérifier</span>
                    </div>
                  </div>
                </div>
              </div>
            </FullCard>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}