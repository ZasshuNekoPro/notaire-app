/**
 * Page tableau de bord - Exemple d'utilisation des composants UI
 */
'use client'

import { useEffect } from 'react'
import { AppLayout } from '@/components/layout'
import {
  Card,
  StatCard,
  Button,
  Badge,
  ImpactBadge,
  Spinner,
  FullCard
} from '@/components/ui'
import { useAuth } from '@/lib/auth-context'
import apiClient from '@/lib/api-client'

export default function DashboardPage() {
  const { user } = useAuth()

  // Test de l'API client
  useEffect(() => {
    const testAPI = async () => {
      try {
        const health = await apiClient.health()
        console.log('✅ API Health:', health)
      } catch (error) {
        console.error('❌ API Error:', error)
      }
    }

    testAPI()
  }, [])

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* En-tête */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Tableau de bord
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Bienvenue {user?.prenom}, voici un aperçu de votre activité notariale.
          </p>
        </div>

        {/* Statistiques rapides */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Dossiers actifs"
            value="12"
            change={{ value: "+2", type: "increase" }}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
              </svg>
            }
          />

          <StatCard
            title="Signatures en attente"
            value="5"
            change={{ value: "-1", type: "decrease" }}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            }
          />

          <StatCard
            title="Estimations ce mois"
            value="28"
            change={{ value: "+15%", type: "increase" }}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            }
          />

          <StatCard
            title="Alertes critiques"
            value="3"
            change={{ value: "0", type: "neutral" }}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            }
          />
        </div>

        {/* Contenu principal */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Alertes récentes */}
          <div className="lg:col-span-2">
            <FullCard
              title="Alertes récentes"
              subtitle="Dernières notifications et veilles automatiques"
              actions={
                <Button size="sm" variant="outline">
                  Voir toutes
                </Button>
              }
            >
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <ImpactBadge impact="critique" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      Nouveau texte Légifrance détecté
                    </p>
                    <p className="text-sm text-gray-500">
                      Modification du Code civil article 731 - Succession
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      Il y a 2 heures
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <ImpactBadge impact="moyen" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      Variation prix DVF importante
                    </p>
                    <p className="text-sm text-gray-500">
                      Paris 15e : +12% sur les appartements
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      Il y a 4 heures
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <ImpactBadge impact="info" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      Mise à jour BOFIP
                    </p>
                    <p className="text-sm text-gray-500">
                      Nouvelles instructions fiscales disponibles
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      Hier
                    </p>
                  </div>
                </div>
              </div>
            </FullCard>
          </div>

          {/* Actions rapides */}
          <div className="space-y-6">
            <FullCard
              title="Actions rapides"
            >
              <div className="space-y-3">
                <Button className="w-full justify-start" variant="outline">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Nouveau dossier
                </Button>

                <Button className="w-full justify-start" variant="outline">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  Estimation immobilière
                </Button>

                <Button className="w-full justify-start" variant="outline">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                  Nouvelle signature
                </Button>

                <Button className="w-full justify-start" variant="outline">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  Calcul succession
                </Button>
              </div>
            </FullCard>

            {/* État du système */}
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">
                    État du système
                  </h3>
                  <div className="mt-2 flex items-center space-x-2">
                    <Badge variant="success" dot>
                      API Opérationnelle
                    </Badge>
                  </div>
                  <div className="mt-1 flex items-center space-x-2">
                    <Badge variant="success" dot>
                      Base de données OK
                    </Badge>
                  </div>
                  <div className="mt-1 flex items-center space-x-2">
                    <Badge variant="success" dot>
                      IA disponible
                    </Badge>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}