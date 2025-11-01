/**
 * DigestPage - Daily email digest management
 * View and generate daily digests
 */

import React, { useState, useEffect } from 'react';
import { Newspaper, RefreshCcw, Send, Clock, CheckCircle2, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';

interface Digest {
  id: string;
  subject: string;
  content: string;
  created_at: string;
  sent_at?: string;
  status: 'draft' | 'sent' | 'failed';
}

export const DigestPage: React.FC = () => {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    fetchDigests();
  }, []);

  const fetchDigests = async () => {
    setIsLoading(true);
    try {
      // TODO: Implement actual API call
      // Simulating empty list for now
      setDigests([]);
    } catch (error) {
      console.error('Error fetching digests:', error);
      toast.error('Erreur lors du chargement des digests');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateDigest = async () => {
    setIsGenerating(true);
    toast.info('Génération en cours... Cela peut prendre 1-2 minutes', { duration: 5000 });

    try {
      // Create an AbortController with a 5 minute timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes

      const response = await fetch('http://localhost:8000/api/digest/generate', {
        method: 'POST',
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) throw new Error('Failed to generate digest');

      await response.json();
      toast.success('Digest généré avec succès !');

      // Refresh the list
      await fetchDigests();
    } catch (error: any) {
      console.error('Error generating digest:', error);
      if (error.name === 'AbortError') {
        toast.error('La génération a pris trop de temps. Veuillez réessayer.');
      } else {
        toast.error('Erreur lors de la génération du digest');
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Newspaper className="h-8 w-8" />
            Digest Quotidien
          </h1>
          <p className="text-gray-500 mt-1">
            Générez et consultez les résumés quotidiens des emails importants
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDigests}
            disabled={isLoading}
          >
            <RefreshCcw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Actualiser
          </Button>
          <Button
            onClick={handleGenerateDigest}
            disabled={isGenerating}
          >
            <Send className={`h-4 w-4 mr-2 ${isGenerating ? 'animate-pulse' : ''}`} />
            {isGenerating ? 'Génération...' : 'Générer Digest'}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Digests générés</CardDescription>
            <CardTitle className="text-3xl">{digests.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Dernière génération</CardDescription>
            <CardTitle className="text-xl text-gray-600">
              {digests.length > 0 ? 'Aujourd\'hui' : 'Aucun'}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Statut</CardDescription>
            <CardTitle className="text-xl">
              <Badge variant="success" className="flex items-center gap-1 w-fit">
                <CheckCircle2 className="h-3 w-3" />
                Actif
              </Badge>
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Info Card */}
      <Card className="border-blue-200 bg-blue-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-blue-900">
            <Clock className="h-5 w-5" />
            À propos du Digest Quotidien
          </CardTitle>
        </CardHeader>
        <CardContent className="text-blue-800">
          <p className="mb-2">
            Le système génère automatiquement un résumé quotidien des emails importants et urgents.
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li>Analyse des emails reçus dans les dernières 24h</li>
            <li>Identification des emails urgents et importants</li>
            <li>Génération d'un résumé structuré avec l'IA</li>
            <li>Envoi automatique aux destinataires configurés</li>
          </ul>
        </CardContent>
      </Card>

      {/* Digests List */}
      <Card>
        <CardHeader>
          <CardTitle>Historique des digests</CardTitle>
          <CardDescription>
            Liste des digests générés récemment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
          ) : digests.length === 0 ? (
            <div className="text-center py-12">
              <Newspaper className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Aucun digest disponible
              </h3>
              <p className="text-gray-500 mb-4">
                Cliquez sur "Générer Digest" pour créer votre premier résumé quotidien
              </p>
              <Button onClick={handleGenerateDigest} disabled={isGenerating}>
                <Send className="h-4 w-4 mr-2" />
                Générer mon premier digest
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {digests.map((digest) => (
                <div
                  key={digest.id}
                  className="p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{digest.subject}</h4>
                      <p className="text-sm text-gray-500 mt-1">
                        Créé le {new Date(digest.created_at).toLocaleDateString('fr-FR', {
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                    <Badge
                      variant={
                        digest.status === 'sent'
                          ? 'success'
                          : digest.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                      }
                    >
                      {digest.status === 'sent' && 'Envoyé'}
                      {digest.status === 'draft' && 'Brouillon'}
                      {digest.status === 'failed' && 'Échec'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configuration Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500" />
            Configuration requise
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600 mb-3">
            Pour recevoir les digests par email, veuillez configurer les destinataires dans les paramètres.
          </p>
          <Button variant="outline" onClick={() => window.location.href = '/admin/settings'}>
            Configurer les destinataires
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
