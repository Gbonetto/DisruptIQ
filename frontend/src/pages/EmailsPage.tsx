import React, { useState } from 'react';
import { Mail, Search, Filter, RefreshCw, Eye, Trash2, CheckCircle, Clock, Calendar } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { emailsApi } from '@/lib/api';
import type { Email, EmailFilters } from '@/types/api';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

export const EmailsPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Filters state
  const [filters, setFilters] = useState<EmailFilters>({
    limit: 20,
    offset: 0,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);

  // Fetch emails
  const { data: emailsData, isLoading, refetch } = useQuery({
    queryKey: ['emails', filters],
    queryFn: () => emailsApi.list(filters),
  });

  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['email-stats'],
    queryFn: () => emailsApi.getStats(),
  });

  // Mark as processed mutation
  const markProcessedMutation = useMutation({
    mutationFn: (id: number) => emailsApi.markProcessed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails'] });
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
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['email-stats'] });
      toast.success('Email supprimé');
      setSelectedEmail(null);
    },
    onError: () => {
      toast.error('Erreur lors de la suppression');
    },
  });

  // Handle search
  const handleSearch = () => {
    setFilters(prev => ({ ...prev, search: searchQuery || undefined, offset: 0 }));
  };

  // Handle filter change
  const updateFilter = (key: keyof EmailFilters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value, offset: 0 }));
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({ limit: 20, offset: 0 });
    setSearchQuery('');
  };

  // Pagination
  const handleNextPage = () => {
    if (emailsData?.has_more) {
      setFilters(prev => ({ ...prev, offset: (prev.offset || 0) + (prev.limit || 20) }));
    }
  };

  const handlePrevPage = () => {
    setFilters(prev => ({ ...prev, offset: Math.max(0, (prev.offset || 0) - (prev.limit || 20)) }));
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Mail className="h-8 w-8" />
            Emails
          </h1>
          <p className="text-gray-500 mt-1">
            Consultez et gérez vos emails
          </p>
        </div>

        <Button onClick={() => refetch()} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Actualiser
        </Button>
      </div>

      {/* Stats Cards */}
      {statsData && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-gray-600">Total</CardTitle>
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

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Rechercher par sujet ou expéditeur..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  className="w-full pl-10 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <Button onClick={handleSearch}>
                <Search className="h-4 w-4 mr-2" />
                Rechercher
              </Button>
              <Button variant="outline" onClick={() => setShowFilters(!showFilters)}>
                <Filter className="h-4 w-4 mr-2" />
                Filtres
              </Button>
            </div>

            {/* Advanced Filters */}
            {showFilters && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
                {/* Urgency Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Urgence
                  </label>
                  <select
                    value={filters.urgency || 'all'}
                    onChange={(e) => updateFilter('urgency', e.target.value === 'all' ? undefined : e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="all">Tous</option>
                    <option value="urgent">Urgent</option>
                    <option value="important">Important</option>
                    <option value="routine">Routine</option>
                  </select>
                </div>

                {/* Processed Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Statut
                  </label>
                  <select
                    value={filters.processed === undefined ? 'all' : filters.processed.toString()}
                    onChange={(e) => {
                      const value = e.target.value === 'all' ? undefined : e.target.value === 'true';
                      updateFilter('processed', value);
                    }}
                    className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="all">Tous</option>
                    <option value="false">Non traités</option>
                    <option value="true">Traités</option>
                  </select>
                </div>

                {/* In Digest Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Dans le digest
                  </label>
                  <select
                    value={filters.included_in_digest === undefined ? 'all' : filters.included_in_digest.toString()}
                    onChange={(e) => {
                      const value = e.target.value === 'all' ? undefined : e.target.value === 'true';
                      updateFilter('included_in_digest', value);
                    }}
                    className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="all">Tous</option>
                    <option value="true">Oui</option>
                    <option value="false">Non</option>
                  </select>
                </div>

                {/* Clear Filters Button */}
                <div className="md:col-span-3 flex justify-end">
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    Réinitialiser les filtres
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Email List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              Emails ({emailsData?.data.total || 0})
            </span>
            <Badge variant="outline">
              Page {Math.floor((filters.offset || 0) / (filters.limit || 20)) + 1}
            </Badge>
          </CardTitle>
          <CardDescription>
            Affichage de {(filters.offset || 0) + 1} à {Math.min((filters.offset || 0) + (filters.limit || 20), emailsData?.data.total || 0)} sur {emailsData?.data.total || 0} emails
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
              <span className="ml-2 text-gray-600">Chargement...</span>
            </div>
          ) : emailsData?.data.emails.length === 0 ? (
            <div className="text-center py-12">
              <Mail className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Aucun email trouvé</p>
              <Button variant="outline" className="mt-4" onClick={clearFilters}>
                Réinitialiser les filtres
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {emailsData?.data.emails.map((email) => (
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
                        {email.category && (
                          <Badge variant="outline" className="text-xs">
                            {email.category}
                          </Badge>
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
          )}

          {/* Pagination */}
          {emailsData && emailsData.data.emails.length > 0 && (
            <div className="flex items-center justify-between mt-6 pt-6 border-t">
              <Button
                variant="outline"
                onClick={handlePrevPage}
                disabled={filters.offset === 0}
              >
                ← Précédent
              </Button>

              <span className="text-sm text-gray-600">
                {(filters.offset || 0) + 1} - {Math.min((filters.offset || 0) + (filters.limit || 20), emailsData.data.total)} sur {emailsData.data.total}
              </span>

              <Button
                variant="outline"
                onClick={handleNextPage}
                disabled={!emailsData.data.has_more}
              >
                Suivant →
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
