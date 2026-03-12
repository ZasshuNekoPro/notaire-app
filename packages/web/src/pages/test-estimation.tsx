/**
 * Page de test pour l'estimation immobilière DVF
 * Formulaire + résultats + carte Leaflet avec points DVF
 */
'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { MapPin, TrendingUp, Home, Calculator, AlertCircle, CheckCircle } from 'lucide-react';

// Import dynamique de la carte Leaflet (évite les erreurs SSR)
const EstimationMap = dynamic(() => import('@/components/estimation/EstimationMap'), {
  ssr: false,
  loading: () => <Skeleton className="h-64 w-full" />
});

// Types pour les données d'estimation
interface EstimationStats {
  code_postal: string;
  type_bien: string;
  prix_m2_median: number;
  prix_m2_q1?: number;
  prix_m2_q3?: number;
  nb_transactions: number;
  prix_min?: number;
  prix_max?: number;
  surface_moyenne?: number;
  periode_analysee: string;
}

interface TransactionComparable {
  id: string;
  adresse: string;
  prix_vente: number;
  surface_m2: number;
  prix_m2: number;
  nb_pieces?: number;
  date_vente: string;
  distance_km: number;
  similarite_score: number;
}

interface EstimationAnalyse {
  bien_analyse: any;
  prix_estime_min: number;
  prix_estime_max: number;
  prix_m2_estime: number;
  confiance_score: number;
  transactions_comparables: TransactionComparable[];
  analyse_marche: string;
  facteurs_positifs: string[];
  facteurs_negatifs: string[];
  recommandations: string[];
  date_analyse: string;
  nb_comparables_utilises: number;
  rayon_recherche_km: number;
}

// Formulaire d'estimation
interface EstimationForm {
  adresse: string;
  code_postal: string;
  type_bien: 'Appartement' | 'Maison' | 'Local industriel. commercial ou assimilé' | '';
  surface_m2: string;
  nb_pieces: string;
  surface_terrain_m2: string;
  etage: string;
  annee_construction: string;
}

const initialForm: EstimationForm = {
  adresse: '',
  code_postal: '',
  type_bien: '',
  surface_m2: '',
  nb_pieces: '',
  surface_terrain_m2: '',
  etage: '',
  annee_construction: ''
};

export default function TestEstimationPage() {
  const [form, setForm] = useState<EstimationForm>(initialForm);
  const [stats, setStats] = useState<EstimationStats | null>(null);
  const [analyse, setAnalyse] = useState<EstimationAnalyse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'stats' | 'analyse' | 'carte'>('stats');

  // Mise à jour du formulaire
  const updateForm = (field: keyof EstimationForm, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  // Fonction pour récupérer les statistiques
  const fetchStats = async () => {
    if (!form.code_postal || !form.type_bien) {
      setError('Code postal et type de bien requis');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `/api/estimations/stats?code_postal=${form.code_postal}&type_bien=${form.type_bien}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || 'demo-token'}`
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Erreur API: ${response.status}`);
      }

      const data: EstimationStats = await response.json();
      setStats(data);
      setActiveTab('stats');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la récupération des stats');
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  // Fonction pour lancer l'analyse IA
  const fetchAnalyse = async () => {
    if (!form.adresse || !form.type_bien || !form.surface_m2) {
      setError('Adresse, type de bien et surface requis pour l\'analyse');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const requestBody = {
        adresse: form.adresse,
        type_bien: form.type_bien,
        surface_m2: parseInt(form.surface_m2),
        nb_pieces: form.nb_pieces ? parseInt(form.nb_pieces) : null,
        surface_terrain_m2: form.surface_terrain_m2 ? parseInt(form.surface_terrain_m2) : null,
        etage: form.etage ? parseInt(form.etage) : null,
        annee_construction: form.annee_construction ? parseInt(form.annee_construction) : null
      };

      const response = await fetch('/api/estimations/analyse', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || 'demo-token'}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`Erreur API: ${response.status}`);
      }

      const data: EstimationAnalyse = await response.json();
      setAnalyse(data);
      setActiveTab('analyse');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de l\'analyse IA');
      setAnalyse(null);
    } finally {
      setLoading(false);
    }
  };

  // Formatage des prix
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0
    }).format(price);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* En-tête */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🏠 Test d'Estimation Immobilière DVF
          </h1>
          <p className="text-gray-600">
            Testez l'API d'estimation basée sur les données DVF et l'IA
          </p>
        </div>

        {/* Formulaire */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Home className="w-5 h-5" />
              Informations du bien à estimer
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* Première ligne */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="adresse">Adresse complète *</Label>
                <Input
                  id="adresse"
                  value={form.adresse}
                  onChange={(e) => updateForm('adresse', e.target.value)}
                  placeholder="8 rue de Rivoli, Paris"
                />
              </div>

              <div>
                <Label htmlFor="code_postal">Code postal *</Label>
                <Input
                  id="code_postal"
                  value={form.code_postal}
                  onChange={(e) => updateForm('code_postal', e.target.value)}
                  placeholder="75001"
                  maxLength={5}
                />
              </div>

              <div>
                <Label htmlFor="type_bien">Type de bien *</Label>
                <Select
                  value={form.type_bien}
                  onValueChange={(value) => updateForm('type_bien', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Sélectionnez..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Appartement">Appartement</SelectItem>
                    <SelectItem value="Maison">Maison</SelectItem>
                    <SelectItem value="Local industriel. commercial ou assimilé">Local commercial</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Deuxième ligne */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <Label htmlFor="surface_m2">Surface (m²) *</Label>
                <Input
                  id="surface_m2"
                  type="number"
                  value={form.surface_m2}
                  onChange={(e) => updateForm('surface_m2', e.target.value)}
                  placeholder="65"
                />
              </div>

              <div>
                <Label htmlFor="nb_pieces">Nb pièces</Label>
                <Input
                  id="nb_pieces"
                  type="number"
                  value={form.nb_pieces}
                  onChange={(e) => updateForm('nb_pieces', e.target.value)}
                  placeholder="3"
                />
              </div>

              <div>
                <Label htmlFor="etage">Étage</Label>
                <Input
                  id="etage"
                  type="number"
                  value={form.etage}
                  onChange={(e) => updateForm('etage', e.target.value)}
                  placeholder="2"
                />
              </div>

              <div>
                <Label htmlFor="annee_construction">Année construction</Label>
                <Input
                  id="annee_construction"
                  type="number"
                  value={form.annee_construction}
                  onChange={(e) => updateForm('annee_construction', e.target.value)}
                  placeholder="1990"
                />
              </div>
            </div>

            {/* Terrain (pour maisons) */}
            {form.type_bien === 'Maison' && (
              <div>
                <Label htmlFor="surface_terrain_m2">Surface terrain (m²)</Label>
                <Input
                  id="surface_terrain_m2"
                  type="number"
                  value={form.surface_terrain_m2}
                  onChange={(e) => updateForm('surface_terrain_m2', e.target.value)}
                  placeholder="300"
                />
              </div>
            )}

            {/* Boutons d'action */}
            <div className="flex gap-4 pt-4">
              <Button
                onClick={fetchStats}
                disabled={loading || !form.code_postal || !form.type_bien}
                className="flex items-center gap-2"
              >
                <TrendingUp className="w-4 h-4" />
                {loading ? 'Chargement...' : 'Statistiques Zone'}
              </Button>

              <Button
                onClick={fetchAnalyse}
                disabled={loading || !form.adresse || !form.type_bien || !form.surface_m2}
                variant="secondary"
                className="flex items-center gap-2"
              >
                <Calculator className="w-4 h-4" />
                {loading ? 'Analyse...' : 'Estimation IA'}
              </Button>
            </div>

          </CardContent>
        </Card>

        {/* Affichage des erreurs */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Onglets de résultats */}
        {(stats || analyse) && (
          <div className="space-y-4">

            {/* Navigation onglets */}
            <div className="flex gap-2">
              {stats && (
                <Button
                  variant={activeTab === 'stats' ? 'default' : 'outline'}
                  onClick={() => setActiveTab('stats')}
                >
                  📊 Statistiques
                </Button>
              )}
              {analyse && (
                <Button
                  variant={activeTab === 'analyse' ? 'default' : 'outline'}
                  onClick={() => setActiveTab('analyse')}
                >
                  🤖 Analyse IA
                </Button>
              )}
              <Button
                variant={activeTab === 'carte' ? 'default' : 'outline'}
                onClick={() => setActiveTab('carte')}
              >
                🗺️ Carte
              </Button>
            </div>

            {/* Contenu des onglets */}
            {activeTab === 'stats' && stats && (
              <Card>
                <CardHeader>
                  <CardTitle>📊 Statistiques de marché - {stats.code_postal}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div className="text-center p-4 bg-blue-50 rounded">
                      <div className="text-2xl font-bold text-blue-600">
                        {formatPrice(stats.prix_m2_median)}
                      </div>
                      <div className="text-sm text-gray-600">Prix médian / m²</div>
                    </div>

                    <div className="text-center p-4 bg-green-50 rounded">
                      <div className="text-2xl font-bold text-green-600">
                        {stats.nb_transactions}
                      </div>
                      <div className="text-sm text-gray-600">Transactions (24 mois)</div>
                    </div>

                    <div className="text-center p-4 bg-purple-50 rounded">
                      <div className="text-2xl font-bold text-purple-600">
                        {stats.surface_moyenne?.toFixed(0)} m²
                      </div>
                      <div className="text-sm text-gray-600">Surface moyenne</div>
                    </div>
                  </div>

                  {stats.prix_m2_q1 && stats.prix_m2_q3 && (
                    <div className="mt-4">
                      <h4 className="font-semibold mb-2">Fourchette de prix (quartiles)</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{formatPrice(stats.prix_m2_q1)}/m² (Q1)</Badge>
                        <span>→</span>
                        <Badge>{formatPrice(stats.prix_m2_median)}/m² (Médiane)</Badge>
                        <span>→</span>
                        <Badge variant="outline">{formatPrice(stats.prix_m2_q3)}/m² (Q3)</Badge>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'analyse' && analyse && (
              <div className="space-y-4">

                {/* Estimation principale */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      🤖 Estimation IA
                      <Badge variant={analyse.confiance_score > 0.7 ? 'default' : 'secondary'}>
                        Confiance: {(analyse.confiance_score * 100).toFixed(0)}%
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div className="text-center p-4 bg-emerald-50 rounded">
                        <div className="text-xl font-bold text-emerald-600">
                          {formatPrice(analyse.prix_estime_min)} - {formatPrice(analyse.prix_estime_max)}
                        </div>
                        <div className="text-sm text-gray-600">Fourchette d'estimation</div>
                      </div>

                      <div className="text-center p-4 bg-blue-50 rounded">
                        <div className="text-xl font-bold text-blue-600">
                          {formatPrice(analyse.prix_m2_estime)}/m²
                        </div>
                        <div className="text-sm text-gray-600">Prix estimé / m²</div>
                      </div>

                      <div className="text-center p-4 bg-orange-50 rounded">
                        <div className="text-xl font-bold text-orange-600">
                          {analyse.nb_comparables_utilises}
                        </div>
                        <div className="text-sm text-gray-600">Comparables analysés</div>
                      </div>
                    </div>

                    {/* Analyse textuelle */}
                    <div className="mb-4">
                      <h4 className="font-semibold mb-2">🔍 Analyse de marché</h4>
                      <p className="text-gray-700 bg-gray-50 p-3 rounded">
                        {analyse.analyse_marche}
                      </p>
                    </div>

                    {/* Facteurs */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="font-semibold mb-2 flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          Facteurs positifs
                        </h4>
                        <ul className="space-y-1">
                          {analyse.facteurs_positifs.map((facteur, idx) => (
                            <li key={idx} className="text-sm text-green-700 flex items-start gap-2">
                              <span className="text-green-500 mt-1">+</span>
                              {facteur}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold mb-2 flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 text-orange-500" />
                          Points d'attention
                        </h4>
                        <ul className="space-y-1">
                          {analyse.facteurs_negatifs.map((facteur, idx) => (
                            <li key={idx} className="text-sm text-orange-700 flex items-start gap-2">
                              <span className="text-orange-500 mt-1">-</span>
                              {facteur}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Recommandations */}
                    <div className="mt-4">
                      <h4 className="font-semibold mb-2">💡 Recommandations</h4>
                      <ul className="space-y-2">
                        {analyse.recommandations.map((reco, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                            <span className="text-blue-500 mt-1">→</span>
                            {reco}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                {/* Table des comparables */}
                <Card>
                  <CardHeader>
                    <CardTitle>🏘️ Transactions comparables</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left p-2">Adresse</th>
                            <th className="text-right p-2">Prix</th>
                            <th className="text-right p-2">Surface</th>
                            <th className="text-right p-2">€/m²</th>
                            <th className="text-right p-2">Distance</th>
                            <th className="text-right p-2">Similarité</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analyse.transactions_comparables.slice(0, 10).map((transaction) => (
                            <tr key={transaction.id} className="border-b hover:bg-gray-50">
                              <td className="p-2 max-w-xs truncate">{transaction.adresse}</td>
                              <td className="p-2 text-right font-medium">{formatPrice(transaction.prix_vente)}</td>
                              <td className="p-2 text-right">{transaction.surface_m2.toFixed(0)} m²</td>
                              <td className="p-2 text-right">{formatPrice(transaction.prix_m2)}</td>
                              <td className="p-2 text-right">{transaction.distance_km.toFixed(1)} km</td>
                              <td className="p-2 text-right">
                                <Badge variant={transaction.similarite_score > 0.8 ? 'default' : 'secondary'}>
                                  {(transaction.similarite_score * 100).toFixed(0)}%
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {activeTab === 'carte' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MapPin className="w-5 h-5" />
                    Carte des transactions DVF
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-96">
                    <EstimationMap
                      departement={form.code_postal?.substring(0, 2) || '75'}
                      typeBien={form.type_bien || 'Appartement'}
                      transactions={analyse?.transactions_comparables || []}
                    />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Instructions d'utilisation */}
        <Card className="bg-blue-50">
          <CardHeader>
            <CardTitle className="text-blue-800">💡 Mode d'emploi</CardTitle>
          </CardHeader>
          <CardContent className="text-blue-700 space-y-2">
            <p>1. <strong>Statistiques Zone</strong> : Renseignez code postal + type de bien pour voir les prix du marché</p>
            <p>2. <strong>Estimation IA</strong> : Ajoutez l'adresse et surface pour une analyse complète avec comparables</p>
            <p>3. <strong>Carte</strong> : Visualisez les transactions similaires sur la carte interactive</p>
            <p className="text-sm mt-4">
              <strong>Note</strong> : Cette page utilise des données DVF réelles et l'API d'estimation développée.
              Assurez-vous que l'API est démarrée sur localhost:8000.
            </p>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}