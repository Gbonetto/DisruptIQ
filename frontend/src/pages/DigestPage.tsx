/**
 * DigestPage - Email digest management with organized view
 * View emails organized by categories/priority + generate AI digests
 */

import React, { useState } from 'react';
import { Newspaper, Send, Trash2, CheckCircle, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { digestApi, emailsApi } from '@/lib/api';
import type { Email } from '@/types/api';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

export const DigestPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [autoGenerate, setAutoGenerate] = useState(false);

  // Fetch latest digest (list of emails organized by AI)
  const { data: digestData, isLoading: isLoadingDigest, refetch: refetchDigest } = useQuery({
    queryKey: ['digest-latest'],
    queryFn: () => digestApi.getLatest(),
    retry: 1,
  });

  // Fetch email stats
  const { data: statsData, refetch: refetchStats } = useQuery({
    queryKey: ['email-stats'],
    queryFn: () => emailsApi.getStats(),
  });

  // Fetch all emails as fallback if no digest
  const { data: emailsData, isLoading: isLoadingEmails, refetch: refetchEmails } = useQuery({
    queryKey: ['emails-all', { limit: 100, offset: 0 }],
    queryFn: () => emailsApi.list({ limit: 100, offset: 0, processed: false }),
    enabled: !digestData, // Only fetch if no digest available
  });

  // Mark as processed mutation
  const markProcessedMutation = useMutation({
    mutationFn: (id: number) => emailsApi.markProcessed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['digest-latest'] });
      queryClient.invalidateQueries({ queryKey: ['emails-all'] });
      queryClient.invalidateQueries({ queryKey: ['email-stats'] });
      toast.success('Email marqué comme traité');
    },
    onError: () => {
      toast.error('Erreur lors du marquage');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => emailsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['digest-latest'] });
      queryClient.invalidateQueries({ queryKey: ['emails-all'] });
      queryClient.invalidateQueries({ queryKey: ['email-stats'] });
      toast.success('Email supprimé');
      setSelectedEmail(null);
    },
    onError: () => {
      toast.error('Erreur lors de la suppression');
    },
  });

  // Generate digest function
  const handleGenerateDigest = async () => {
    setIsGenerating(true);
    toast.info('Génération en cours... Cela peut prendre 1-2 minutes', { duration: 5000 });

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes

      await digestApi.generate();
      clearTimeout(timeoutId);

      toast.success('Digest généré avec succès !');
      await refetchDigest();
      await refetchStats();
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

  // Refresh all data
  const handleRefresh = () => {
    refetchDigest();
    refetchStats();
    refetchEmails();
    toast.success('Données actualisées');
  };

  // Get urgency badge
  const getUrgencyBadge = (urgency: string) => {
    const config = {
      urgent: { color: 'bg-red-100 text-red-700 border-red-300', label: '🔴 Urgent' },
      important: { color: 'bg-orange-100 text-orange-700 border-orange-300', label: '🟠 Important' },
      routine: { color: 'bg-green-100 text-green-700 border-green-300', label: '🟢 Routine' },
    };
    const { color, label } = config[urgency as keyof typeof config] || config.routine;
    return <Badge className={color}>{label}</Badge>;
  };

  // Organize emails by category
  const organizeByCategory = (emails: Email[]) => {
    const categories: Record<string, Email[]> = {};
    emails.forEach((email) => {
      const cat = email.category || 'Autre';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(email);
    });
    return categories;
  };

  // Get emails to display
  const getEmailsToDisplay = (): Email[] => {
    if (digestData?.data?.digest?.sections) {
      // Extract emails from digest sections
      const allEmails: Email[] = [];
      digestData.data.digest.sections.forEach(section => {
        section.emails.forEach(digestEmail => {
          // Convert DigestEmail to Email format
          allEmails.push({
            id: digestEmail.id,
            message_id: '',
            sender: digestEmail.sender,
            subject: digestEmail.subject,
            snippet: digestEmail.summary,
            urgency: digestEmail.priority as any || 'routine',
            category: digestEmail.category,
            attachments: [],
            processed: false,
            included_in_digest: true,
            received_at: digestEmail.received_at,
          });
        });
      });
      return allEmails;
    } else if (emailsData?.data?.emails) {
      return emailsData.data.emails;
    }
    return [];
  };

  const emails = getEmailsToDisplay();
  const categorizedEmails = organizeByCategory(emails);
  const isLoading = isLoadingDigest || isLoadingEmails;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Newspaper className="h-8 w-8" />
            Digest Quotidien
          </h1>
          <p className="text-gray-500 mt-1">
            Emails organisés par catégories et priorités
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={handleRefresh} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Actualiser
          </Button>
          <Button onClick={handleGenerateDigest} disabled={isGenerating}>
            <Send className={`h-4 w-4 mr-2 ${isGenerating ? 'animate-pulse' : ''}`} />
            {isGenerating ? 'Génération...' : 'Générer Digest IA'}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {statsData && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Total Emails</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{statsData.data.total}</p>
            </CardContent>
          </Card>

          <Card className="bg-red-50 border-red-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-red-900">Urgents</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-700">{statsData.data.by_urgency.urgent}</p>
            </CardContent>
          </Card>

          <Card className="bg-orange-50 border-orange-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-orange-900">Importants</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-orange-700">{statsData.data.by_urgency.important}</p>
            </CardContent>
          </Card>

          <Card className="bg-blue-50 border-blue-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-blue-900">Non traités</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-blue-700">{statsData.data.by_status.unprocessed}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Auto-generation option */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-blue-700" />
              <div>
                <p className="font-medium text-blue-900">Génération automatique</p>
                <p className="text-sm text-blue-700">Générer un digest chaque jour à 9h00</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoGenerate}
                onChange={(e) => {
                  setAutoGenerate(e.target.checked);
                  toast.success(e.target.checked ? 'Auto-génération activée' : 'Auto-génération désactivée');
                }}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Emails organized by categories */}
      {isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
              <span className="ml-2 text-gray-600">Chargement...</span>
            </div>
          </CardContent>
        </Card>
      ) : emails.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <Newspaper className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Aucun email à afficher
              </h3>
              <p className="text-gray-500 mb-4">
                Cliquez sur "Générer Digest IA" pour analyser vos emails
              </p>
              <Button onClick={handleGenerateDigest} disabled={isGenerating}>
                <Send className="h-4 w-4 mr-2" />
                Générer mon premier digest
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(categorizedEmails).map(([category, categoryEmails]) => (
            <Card key={category}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{category} ({categoryEmails.length})</span>
                  <Badge variant="outline">{categoryEmails.length} email(s)</Badge>
                </CardTitle>
                <CardDescription>
                  Emails classés dans cette catégorie
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {categoryEmails.map((email) => (
                    <div
                      key={email.id}
                      className={`border rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer ${
                        selectedEmail?.id === email.id ? 'bg-blue-50 border-blue-300' : ''
                      }`}
                      onClick={() => setSelectedEmail(selectedEmail?.id === email.id ? null : email)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            {getUrgencyBadge(email.urgency)}
                            {email.processed && (
                              <Badge className="bg-green-100 text-green-700">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Traité
                              </Badge>
                            )}
                            {email.included_in_digest && (
                              <Badge className="bg-purple-100 text-purple-700">
                                Dans le digest
                              </Badge>
                            )}
                          </div>

                          <h3 className="font-semibold text-gray-900 truncate mb-1">
                            {email.subject}
                          </h3>

                          <p className="text-sm text-gray-600 mb-2">
                            De: <span className="font-medium">{email.sender}</span>
                          </p>

                          {email.snippet && (
                            <p className="text-sm text-gray-500 line-clamp-2">
                              {email.snippet}
                            </p>
                          )}

                          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                            {email.received_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {formatDistanceToNow(new Date(email.received_at), { locale: fr, addSuffix: true })}
                              </span>
                            )}
                            {email.attachments?.length > 0 && (
                              <span>
                                📎 {email.attachments.length} pièce(s) jointe(s)
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 ml-4">
                          {!email.processed && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                markProcessedMutation.mutate(email.id);
                              }}
                              disabled={markProcessedMutation.isPending}
                            >
                              <CheckCircle className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm('Êtes-vous sûr de vouloir supprimer cet email ?')) {
                                deleteMutation.mutate(email.id);
                              }
                            }}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      </div>

                      {/* Expanded view */}
                      {selectedEmail?.id === email.id && email.body && (
                        <div className="mt-4 pt-4 border-t">
                          <h4 className="font-medium text-sm text-gray-700 mb-2">Corps du message:</h4>
                          <div className="bg-white p-4 rounded border text-sm whitespace-pre-wrap max-h-96 overflow-y-auto">
                            {email.body}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-blue-500" />
            À propos du Digest Quotidien
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600 mb-3">
            Le système analyse vos emails et les organise automatiquement par catégories et priorités.
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
            <li>Analyse des emails reçus avec l'IA</li>
            <li>Classification par urgence et catégorie</li>
            <li>Organisation intelligente pour une meilleure visibilité</li>
            <li>Actions rapides : marquer traité, supprimer</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
};
