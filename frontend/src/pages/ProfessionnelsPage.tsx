/**
 * ProfessionnelsPage - Manage professionals/vendors
 * Premium data table with search, filters, and quick actions
 */

import React, { useState, useEffect } from 'react';
import {
  Users,
  Plus,
  Search,
  Download,
  Upload,
  Trash2,
  CheckCircle2,
  XCircle,
  MoreVertical,
  RefreshCcw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { EntityDrawer } from '@/components/drawer/EntityDrawer';
import { toast } from 'sonner';

interface Professionnel {
  id: number;
  name: string;
  email: string;
  phone?: string;
  company_name?: string;
  category?: string;
  city?: string;
  postal_code?: string;
  is_indexed: boolean;
  created_at: string;
}

export const ProfessionnelsPage: React.FC = () => {
  const [professionnels, setProfessionnels] = useState<Professionnel[]>([]);
  const [filteredData, setFilteredData] = useState<Professionnel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [indexedFilter, setIndexedFilter] = useState<string>('all');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit' | 'view'>('view');
  const [selectedProfessionnel, setSelectedProfessionnel] = useState<Professionnel | null>(null);

  // Import file handler
  const handleImportCSV = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    input.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;

      toast.info('Import CSV - Fonctionnalité en développement');
      // TODO: Implement CSV import with ImportWizard
    };
    input.click();
  };

  useEffect(() => {
    fetchProfessionnels();
  }, []);

  useEffect(() => {
    filterData();
  }, [professionnels, searchQuery, categoryFilter, indexedFilter]);

  const fetchProfessionnels = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/admin/vendors');
      const data = await response.json();
      setProfessionnels(data);
    } catch (error) {
      console.error('Error fetching professionnels:', error);
      toast.error('Erreur lors du chargement des professionnels');
    } finally {
      setIsLoading(false);
    }
  };

  const filterData = () => {
    let filtered = [...professionnels];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.email.toLowerCase().includes(query) ||
          p.company_name?.toLowerCase().includes(query) ||
          p.city?.toLowerCase().includes(query)
      );
    }

    // Category filter
    if (categoryFilter !== 'all') {
      filtered = filtered.filter((p) => p.category === categoryFilter);
    }

    // Indexed filter
    if (indexedFilter !== 'all') {
      const isIndexed = indexedFilter === 'indexed';
      filtered = filtered.filter((p) => p.is_indexed === isIndexed);
    }

    setFilteredData(filtered);
  };

  const handleViewProfessionnel = (professionnel: Professionnel) => {
    setSelectedProfessionnel(professionnel);
    setDrawerMode('view');
    setDrawerOpen(true);
  };

  const handleEditProfessionnel = (professionnel: Professionnel) => {
    setSelectedProfessionnel(professionnel);
    setDrawerMode('edit');
    setDrawerOpen(true);
  };

  const handleCreateProfessionnel = () => {
    setSelectedProfessionnel(null);
    setDrawerMode('create');
    setDrawerOpen(true);
  };

  const handleSaveProfessionnel = async (data: any) => {
    try {
      const url = drawerMode === 'create'
        ? 'http://localhost:8000/api/admin/vendors'
        : `http://localhost:8000/api/admin/vendors/${selectedProfessionnel?.id}`;

      const method = drawerMode === 'create' ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) throw new Error('Failed to save');

      await fetchProfessionnels();
      toast.success(
        drawerMode === 'create'
          ? 'Professionnel créé avec succès'
          : 'Professionnel modifié avec succès'
      );
    } catch (error) {
      toast.error('Erreur lors de la sauvegarde');
      throw error;
    }
  };

  const handleDeleteProfessionnel = async () => {
    if (!selectedProfessionnel) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/vendors/${selectedProfessionnel.id}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete');

      await fetchProfessionnels();
      toast.success('Professionnel supprimé avec succès');
    } catch (error) {
      toast.error('Erreur lors de la suppression');
      throw error;
    }
  };

  const handleReindexProfessionnel = async (id: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/vendors/${id}/index`,
        { method: 'POST' }
      );

      if (!response.ok) throw new Error('Failed to index');

      await fetchProfessionnels();
      toast.success('Professionnel réindexé avec succès');
    } catch (error) {
      toast.error('Erreur lors de la réindexation');
    }
  };

  const handleExportCSV = () => {
    const headers = ['ID', 'Nom', 'Email', 'Téléphone', 'Entreprise', 'Catégorie', 'Ville', 'Indexé'];
    const csvData = filteredData.map((p) => [
      p.id,
      p.name,
      p.email,
      p.phone || '',
      p.company_name || '',
      p.category || '',
      p.city || '',
      p.is_indexed ? 'Oui' : 'Non',
    ]);

    const csvContent = [
      headers.join(','),
      ...csvData.map((row) => row.map((cell) => `"${cell}"`).join(',')),
    ].join('\n');

    // Add UTF-8 BOM for proper Excel compatibility
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `professionnels_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();

    toast.success('Export CSV réussi');
  };

  const categories = Array.from(new Set(professionnels.map((p) => p.category).filter(Boolean)));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Users className="h-8 w-8" />
          Professionnels
        </h1>
        <p className="text-gray-500 mt-1">
          Gérez vos prestataires et fournisseurs
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total</CardDescription>
            <CardTitle className="text-3xl">{professionnels.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Indexés</CardDescription>
            <CardTitle className="text-3xl text-green-600">
              {professionnels.filter((p) => p.is_indexed).length}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Non indexés</CardDescription>
            <CardTitle className="text-3xl text-orange-600">
              {professionnels.filter((p) => !p.is_indexed).length}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Liste des professionnels</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchProfessionnels}>
                <RefreshCcw className="h-4 w-4 mr-2" />
                Actualiser
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  if (!confirm('Réindexer tous les professionnels dans le RAG ?')) return;
                  try {
                    for (const prof of professionnels) {
                      if (!prof.is_indexed) {
                        await fetch(`http://localhost:8000/api/admin/vendors/${prof.id}/index`, {
                          method: 'POST'
                        });
                      }
                    }
                    await fetchProfessionnels();
                    toast.success('Réindexation terminée');
                  } catch (error) {
                    toast.error('Erreur lors de la réindexation');
                  }
                }}
              >
                <RefreshCcw className="h-4 w-4 mr-2" />
                Réindexer tout
              </Button>
              <Button variant="outline" size="sm" onClick={handleImportCSV}>
                <Upload className="h-4 w-4 mr-2" />
                Importer CSV
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportCSV}>
                <Download className="h-4 w-4 mr-2" />
                Exporter CSV
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={async () => {
                  if (!confirm('Êtes-vous sûr de vouloir supprimer TOUS les professionnels ? Cette action est irréversible !')) return;
                  try {
                    await Promise.all(
                      professionnels.map(p =>
                        fetch(`http://localhost:8000/api/admin/vendors/${p.id}`, {
                          method: 'DELETE'
                        })
                      )
                    );
                    await fetchProfessionnels();
                    toast.success('Tous les professionnels ont été supprimés');
                  } catch (error) {
                    toast.error('Erreur lors de la suppression');
                  }
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Tout supprimer
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Rechercher par nom, email, entreprise, ville..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Category Filter */}
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Catégorie" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes catégories</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat} value={cat!}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Indexed Filter */}
            <Select value={indexedFilter} onValueChange={setIndexedFilter}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Indexation" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                <SelectItem value="indexed">Indexés</SelectItem>
                <SelectItem value="not-indexed">Non indexés</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : filteredData.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Aucun professionnel trouvé
              </h3>
              <p className="text-gray-500 mb-4">
                {searchQuery || categoryFilter !== 'all'
                  ? 'Essayez de modifier vos filtres'
                  : 'Commencez par ajouter votre premier professionnel'}
              </p>
              {!searchQuery && categoryFilter === 'all' && (
                <Button onClick={handleCreateProfessionnel}>
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter un professionnel
                </Button>
              )}
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Entreprise</TableHead>
                    <TableHead>Catégorie</TableHead>
                    <TableHead>Ville</TableHead>
                    <TableHead>Indexé</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredData.map((professionnel) => (
                    <TableRow
                      key={professionnel.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => handleViewProfessionnel(professionnel)}
                    >
                      <TableCell className="font-medium">{professionnel.name}</TableCell>
                      <TableCell className="text-gray-600">{professionnel.email}</TableCell>
                      <TableCell className="text-gray-600">
                        {professionnel.company_name || '-'}
                      </TableCell>
                      <TableCell>
                        {professionnel.category ? (
                          <Badge variant="outline" className="capitalize">
                            {professionnel.category}
                          </Badge>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                      <TableCell className="text-gray-600">{professionnel.city || '-'}</TableCell>
                      <TableCell>
                        {professionnel.is_indexed ? (
                          <Badge variant="success" className="flex items-center gap-1 w-fit">
                            <CheckCircle2 className="h-3 w-3" />
                            Oui
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="flex items-center gap-1 w-fit">
                            <XCircle className="h-3 w-3" />
                            Non
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                            <Button variant="ghost" size="icon">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                handleViewProfessionnel(professionnel);
                              }}
                            >
                              Voir détails
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditProfessionnel(professionnel);
                              }}
                            >
                              Modifier
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {!professionnel.is_indexed && (
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleReindexProfessionnel(professionnel.id);
                                }}
                              >
                                <RefreshCcw className="h-3 w-3 mr-2" />
                                Indexer dans RAG
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditProfessionnel(professionnel);
                              }}
                            >
                              <Trash2 className="h-3 w-3 mr-2" />
                              Supprimer
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Results count */}
          {!isLoading && filteredData.length > 0 && (
            <div className="mt-4 text-sm text-gray-500 text-center">
              Affichage de {filteredData.length} résultat{filteredData.length > 1 ? 's' : ''}
              {filteredData.length !== professionnels.length &&
                ` sur ${professionnels.length} au total`}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Entity Drawer */}
      <EntityDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        entity="professionnel"
        mode={drawerMode}
        data={selectedProfessionnel}
        onSave={handleSaveProfessionnel}
        onDelete={drawerMode === 'edit' ? handleDeleteProfessionnel : undefined}
      />
    </div>
  );
};
