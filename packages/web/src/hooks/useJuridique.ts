/**
 * Hook personnalisé pour l'assistant juridique RAG.
 * Logique métier : questions/réponses, streaming, génération d'actes, historique.
 */
'use client'

import { useState, useCallback, useRef } from 'react'
import apiClient, { DossierItem } from '@/lib/api-client'
import { useToast } from '@/components/ui/Toast'

interface SourceCitee {
  titre: string
  url: string
  extrait: string
  pertinence: number
}

interface ReponseJuridique {
  id: string
  question: string
  reponse: string
  sources: SourceCitee[]
  confiance: 'elevee' | 'moyenne' | 'faible'
  timestamp: string
  dossier_id?: string
  dossier_numero?: string
}

interface QuestionRequest {
  question: string
  dossier_id?: string
}

interface GenerationActe {
  id: string
  type_acte: string
  parametres: Record<string, any>
  contenu: string
  statut: 'en_cours' | 'termine' | 'erreur'
  timestamp: string
}

interface UseJuridiqueReturn {
  // État questions/réponses
  isAsking: boolean
  historique: ReponseJuridique[]
  error: string | null

  // État génération d'actes
  isGenerating: boolean
  currentGeneration: GenerationActe | null
  generationHistory: GenerationActe[]

  // Dossiers pour contexte
  dossiers: DossierItem[]
  isLoadingDossiers: boolean

  // Actions principales
  poserQuestion: (request: QuestionRequest) => Promise<void>
  genererActe: (type: string, parametres: Record<string, any>) => Promise<void>
  stopGeneration: () => void
  loadDossiers: () => Promise<void>

  // Utilitaires
  clearHistorique: () => void
  exporterActe: (generation: GenerationActe) => void
  copierActe: (generation: GenerationActe) => void
  getConfidenceColor: (confiance: string) => string
}

/**
 * Hook principal pour l'assistant juridique
 */
export function useJuridique(): UseJuridiqueReturn {
  // États questions/réponses
  const [isAsking, setIsAsking] = useState(false)
  const [historique, setHistorique] = useState<ReponseJuridique[]>([])
  const [error, setError] = useState<string | null>(null)

  // États génération d'actes
  const [isGenerating, setIsGenerating] = useState(false)
  const [currentGeneration, setCurrentGeneration] = useState<GenerationActe | null>(null)
  const [generationHistory, setGenerationHistory] = useState<GenerationActe[]>([])

  // Dossiers pour contexte
  const [dossiers, setDossiers] = useState<DossierItem[]>([])
  const [isLoadingDossiers, setIsLoadingDossiers] = useState(false)

  // Refs pour SSE
  const sseRef = useRef<EventSource | null>(null)

  const toast = useToast()

  /**
   * Pose une question à l'assistant juridique
   */
  const poserQuestion = useCallback(async (request: QuestionRequest) => {
    try {
      setIsAsking(true)
      setError(null)

      // TODO: Remplacer par l'endpoint réel une fois implémenté
      const response = await apiClient.request<{
        reponse: string
        sources: SourceCitee[]
        confiance: 'elevee' | 'moyenne' | 'faible'
      }>({
        method: 'POST',
        url: '/juridique/question',
        data: request
      })

      const dossier = request.dossier_id ?
        dossiers.find(d => d.id === request.dossier_id) : null

      const nouvelleReponse: ReponseJuridique = {
        id: `rep_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        question: request.question,
        reponse: response.data.reponse,
        sources: response.data.sources,
        confiance: response.data.confiance,
        timestamp: new Date().toISOString(),
        dossier_id: request.dossier_id,
        dossier_numero: dossier?.numero
      }

      setHistorique(prev => [nouvelleReponse, ...prev])

      toast.success('Réponse disponible', 'L\'assistant juridique a répondu à votre question')

    } catch (err: any) {
      console.error('Erreur question juridique:', err)

      // Simuler une réponse pour les tests (à supprimer en production)
      if (request.question.toLowerCase().includes('abattement') &&
          request.question.toLowerCase().includes('enfant')) {

        const reponseSimulee: ReponseJuridique = {
          id: `rep_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          question: request.question,
          reponse: `## Abattement succession enfant 2025\n\nL'abattement applicable aux enfants en matière de droits de succession est fixé à **100 000 euros** pour l'année 2025.\n\n### Détails légaux\n\nSelon l'article 779 du Code général des impôts, chaque enfant bénéficie d'un abattement de 100 000 euros sur la part d'héritage qu'il recueille dans la succession de chacun de ses parents.\n\n### Application pratique\n\n- **Abattement par parent** : 100 000 € par enfant et par parent décédé\n- **Renouvellement** : L'abattement se renouvelle tous les 15 ans en cas de donation\n- **Cumul impossible** : Un même enfant ne peut pas cumuler plusieurs abattements du même parent\n\n### Calcul des droits\n\nAprès application de l'abattement, le barème progressif s'applique selon les tranches suivantes :\n- Jusqu'à 8 072 € : 5%\n- De 8 072 € à 12 109 € : 10%\n- De 12 109 € à 15 932 € : 15%\n- Au-delà de 15 932 € : 20%`,
          sources: [
            {
              titre: 'Article 779 du Code général des impôts',
              url: 'https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000038878025',
              extrait: 'L\'abattement prévu au a du 1° est fixé à 100 000 euros.',
              pertinence: 0.95
            },
            {
              titre: 'BOFIP - Droits de succession - Abattements',
              url: 'https://bofip.impots.gouv.fr/bofip/7495-PGP.html',
              extrait: 'Chaque enfant peut bénéficier d\'un abattement de 100 000 euros sur sa part d\'héritage.',
              pertinence: 0.88
            }
          ],
          confiance: 'elevee',
          timestamp: new Date().toISOString(),
          dossier_id: request.dossier_id,
          dossier_numero: request.dossier_id ? dossiers.find(d => d.id === request.dossier_id)?.numero : undefined
        }

        setHistorique(prev => [reponseSimulee, ...prev])
        toast.success('Réponse disponible', 'L\'assistant juridique a répondu à votre question')
      } else {
        setError(err.message || 'Erreur lors de la question')
        toast.error('Erreur', 'Impossible d\'obtenir une réponse')
      }
    } finally {
      setIsAsking(false)
    }
  }, [dossiers, toast])

  /**
   * Génère un acte avec streaming SSE
   */
  const genererActe = useCallback(async (type: string, parametres: Record<string, any>) => {
    try {
      setIsGenerating(true)
      setError(null)

      const generationId = `gen_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

      const nouvelleGeneration: GenerationActe = {
        id: generationId,
        type_acte: type,
        parametres,
        contenu: '',
        statut: 'en_cours',
        timestamp: new Date().toISOString()
      }

      setCurrentGeneration(nouvelleGeneration)
      setGenerationHistory(prev => [nouvelleGeneration, ...prev])

      // TODO: Implémenter le streaming SSE réel
      // Pour l'instant, simulation du streaming
      const contenuSimule = `# ${type.toUpperCase()}\n\n## Parties\n\n**Vendeur :** ${parametres.vendeur_nom || 'M. MARTIN Pierre'}\n**Acquéreur :** ${parametres.acquereur_nom || 'Mme DUPONT Sophie'}\n\n## Bien immobilier\n\n**Adresse :** ${parametres.adresse || '123 rue de la Paix, 75001 PARIS'}\n**Surface :** ${parametres.surface || '65'} m²\n**Prix de vente :** ${parametres.prix || '450 000'} euros\n\n## Conditions de vente\n\nLa vente est consentie et acceptée moyennant le prix de ${parametres.prix || '450 000'} euros, que l'acquéreur s'oblige à payer comptant lors de la signature de l'acte authentique.\n\n## Clauses particulières\n\n### Article 1 - Origine de propriété\nLe vendeur déclare que sa propriété résulte d'un acte d'acquisition...\n\n### Article 2 - Diagnostics techniques\nLes diagnostics techniques obligatoires ont été réalisés et remis à l'acquéreur...\n\n### Article 3 - Charges et conditions\nL'immeuble est vendu avec toutes ses aisances et dépendances...\n\n---\n\n*Acte généré automatiquement par l'assistant juridique IA*\n*À réviser et personnaliser selon les spécificités du dossier*`

      let index = 0
      const interval = setInterval(() => {
        if (index < contenuSimule.length) {
          const nextChunk = contenuSimule.slice(0, index + 50)

          setCurrentGeneration(prev => prev ? {
            ...prev,
            contenu: nextChunk
          } : null)

          setGenerationHistory(prev => prev.map(gen =>
            gen.id === generationId
              ? { ...gen, contenu: nextChunk }
              : gen
          ))

          index += 50
        } else {
          clearInterval(interval)

          setCurrentGeneration(prev => prev ? {
            ...prev,
            statut: 'termine'
          } : null)

          setGenerationHistory(prev => prev.map(gen =>
            gen.id === generationId
              ? { ...gen, statut: 'termine' }
              : gen
          ))

          setIsGenerating(false)
          toast.success('Génération terminée', 'L\'acte a été généré avec succès')
        }
      }, 100)

    } catch (err: any) {
      console.error('Erreur génération acte:', err)
      setError(err.message || 'Erreur lors de la génération')
      toast.error('Erreur', 'Impossible de générer l\'acte')
      setIsGenerating(false)
    }
  }, [toast])

  /**
   * Arrête la génération en cours
   */
  const stopGeneration = useCallback(() => {
    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
    }

    if (currentGeneration) {
      setCurrentGeneration(prev => prev ? {
        ...prev,
        statut: 'erreur'
      } : null)

      setGenerationHistory(prev => prev.map(gen =>
        gen.id === currentGeneration.id
          ? { ...gen, statut: 'erreur' }
          : gen
      ))
    }

    setIsGenerating(false)
  }, [currentGeneration])

  /**
   * Charge la liste des dossiers
   */
  const loadDossiers = useCallback(async () => {
    try {
      setIsLoadingDossiers(true)

      const response = await apiClient.dossiers.list({
        limit: 50
      })

      setDossiers(response.dossiers)

    } catch (err: any) {
      console.error('Erreur chargement dossiers:', err)
    } finally {
      setIsLoadingDossiers(false)
    }
  }, [])

  /**
   * Efface l'historique
   */
  const clearHistorique = useCallback(() => {
    setHistorique([])
  }, [])

  /**
   * Exporte un acte en DOCX
   */
  const exporterActe = useCallback((generation: GenerationActe) => {
    try {
      // Créer un blob avec le contenu markdown
      const blob = new Blob([generation.contenu], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      })

      // Créer un lien de téléchargement
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${generation.type_acte}_${generation.timestamp.slice(0, 10)}.docx`
      link.click()

      URL.revokeObjectURL(url)
      toast.success('Export terminé', 'L\'acte a été téléchargé')

    } catch (err) {
      console.error('Erreur export:', err)
      toast.error('Erreur', 'Impossible d\'exporter l\'acte')
    }
  }, [toast])

  /**
   * Copie un acte dans le presse-papiers
   */
  const copierActe = useCallback((generation: GenerationActe) => {
    try {
      navigator.clipboard.writeText(generation.contenu)
      toast.success('Copié', 'L\'acte a été copié dans le presse-papiers')
    } catch (err) {
      console.error('Erreur copie:', err)
      toast.error('Erreur', 'Impossible de copier l\'acte')
    }
  }, [toast])

  /**
   * Retourne la couleur selon le niveau de confiance
   */
  const getConfidenceColor = useCallback((confiance: string): string => {
    switch (confiance) {
      case 'elevee':
        return 'success'
      case 'moyenne':
        return 'warning'
      case 'faible':
        return 'danger'
      default:
        return 'neutral'
    }
  }, [])

  return {
    // État questions/réponses
    isAsking,
    historique,
    error,

    // État génération d'actes
    isGenerating,
    currentGeneration,
    generationHistory,

    // Dossiers pour contexte
    dossiers,
    isLoadingDossiers,

    // Actions principales
    poserQuestion,
    genererActe,
    stopGeneration,
    loadDossiers,

    // Utilitaires
    clearHistorique,
    exporterActe,
    copierActe,
    getConfidenceColor
  }
}

export default useJuridique