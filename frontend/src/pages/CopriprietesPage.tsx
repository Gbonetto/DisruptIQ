/**
 * CopropriétésPage - Manage properties/buildings
 * Premium data table with search, filters, and quick actions
 */

import React, { useState, useEffect } from 'react';
import {
  Building,
  Plus,
  Search,
  Download,
  Upload,
  Trash2,
  MoreVertical,
  RefreshCcw,
  MapPin,
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

interface Copropriete {
  id: number;
  nom: string;
  adresse: string;
  ville: string;
  code_postal: string;
  nombre_lots?: number;
  nombre_batiments?: number;
  syndic?: string;
  created_at: string;
}

export const CopropriétésPage: React.FC = () => {
  const [coproprietes, setCoproprietes] = useState<Copropriete[]>([]);
  const [filteredData, setFilteredData] = useState<Copropriete[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [cityFilter, setCityFilter] = useState<string>('all');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit' | 'view'>('view');
  const [selectedCopropriete, setSelectedCopropriete] = useState<Copropriete | null>(null);

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
    fetchCoproprietes();
  }, []);

  useEffect(() => {
    filterData();
  }, [coproprietes, searchQuery, cityFilter]);

  const fetchCoproprietes = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/coproprietes/');
      const data = await response.json();
      setCoproprietes(data);
    } catch (error) {
      console.error('Error fetching copropriétés:', error);
      toast.error('Erreur lors du chargement des copropriétés');
    } finally {
      setIsLoading(false);
    }
  };

  const filterData = () => {
    let filtered = [...coproprietes];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.nom.toLowerCase().includes(query) ||
          c.adresse.toLowerCase().includes(query) ||
          c.ville.toLowerCase().includes(query) ||
          c.code_postal.includes(query) ||
          c.syndic?.toLowerCase().includes(query)
      );
    }

    // City filter
    if (cityFilter !== 'all') {
      filtered = filtered.filter((c) => c.ville === cityFilter);
    }

    setFilteredData(filtered);
  };

  const handleViewCopropriete = (copropriete: Copropriete) => {
    setSelectedCopropriete(copropriete);
    setDrawerMode('view');
    setDrawerOpen(true);
  };

  const handleEditCopropriete = (copropriete: Copropriete) => {
    setSelectedCopropriete(copropriete);
    setDrawerMode('edit');
    setDrawerOpen(true);
  };

  const handleCreateCopropriete = () => {
    setSelectedCopropriete(null);
    setDrawerMode('create');
    setDrawerOpen(true);
  };

  const handleSaveCopropriete = async (data: any) => {
    try {
      const url = drawerMode === 'create'
        ? 'http://localhost:8000/api/coproprietes/'
        : `http://localhost:8000/api/coproprietes/${selectedCopropriete?.id}`;

      const method = drawerMode === 'create' ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) throw new Error('Failed to save');

      await fetchCoproprietes();
      toast.success(
        drawerMode === 'create'
          ? 'Copropriété créée avec succès'
          : 'Copropriété modifiée avec succès'
      );
    } catch (error) {
      toast.error('Erreur lors de la sauvegarde');
      throw error;
    }
  };

  const handleDeleteCopropriete = async () => {
    if (!selectedCopropriete) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/coproprietes/${selectedCopropriete.id}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete');

      await fetchCoproprietes();
      toast.success('Copropriété supprimée avec succès');
    } catch (error) {
      toast.error('Erreur lors de la suppression');
      throw error;
    }
  };

  const handleExportCSV = () => {
    const headers = ['ID', 'Nom', 'Adresse', 'Ville', 'Code Postal', 'Lots', 'Bâtiments', 'Syndic'];
    const csvData = filteredData.map((c) => [
      c.id,
      c.nom,
      c.adresse,
      c.ville,
      c.code_postal,
      c.nombre_lots || 0,
      c.nombre_batiments || 0,
      c.syndic || '',
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
    link.download = `coproprietes_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();

    toast.success('Export CSV réussi');
  };

  const cities = Array.from(new Set(coproprietes.map((c) => c.ville).filter(Boolean)));
  const totalLots = coproprietes.reduce((sum, c) => sum + (c.nombre_lots || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Building className="h-8 w-8" />
          Copropriétés
        </h1>
        <p className="text-gray-500 mt-1">
          Gérez vos biens immobiliers et résidences
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total copropriétés</CardDescription>
            <CardTitle className="text-3xl">{coproprietes.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total lots</CardDescription>
            <CardTitle className="text-3xl text-blue-600">{totalLots}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Villes couvertes</CardDescription>
            <CardTitle className="text-3xl text-green-600">{cities.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Liste des copropriétés</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchCoproprietes}>
                <RefreshCcw className="h-4 w-4 mr-2" />
                Actualiser
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
                  if (!confirm('Êtes-vous sûr de vouloir supprimer TOUTES les copropriétés ? Cette action est irréversible !')) return;
                  try {
                    await Promise.all(
                      coproprietes.map(c =>
                        fetch(`http://localhost:8000/api/coproprietes/${c.id}`, {
                          method: 'DELETE'
                        })
                      )
                    );
                    await fetchCoproprietes();
                    toast.success('Toutes les copropriétés ont été supprimées');
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
                  placeholder="Rechercher par nom, adresse, ville, code postal, syndic..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* City Filter */}
            <Select value={cityFilter} onValueChange={setCityFilter}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Ville" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes les villes</SelectItem>
                {cities.map((city) => (
                  <SelectItem key={city} value={city}>
                    {city}
                  </SelectItem>
                ))}
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
              <Building className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Aucune copropriété trouvée
              </h3>
              <p className="text-gray-500 mb-4">
                {searchQuery || cityFilter !== 'all'
                  ? 'Essayez de modifier vos filtres'
                  : 'Commencez par ajouter votre première copropriété'}
              </p>
              {!searchQuery && cityFilter === 'all' && (
                <Button onClick={handleCreateCopropriete}>
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter une copropriété
                </Button>
              )}
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Adresse</TableHead>
                    <TableHead>Ville</TableHead>
                    <TableHead>Lots</TableHead>
                    <TableHead>Bâtiments</TableHead>
                    <TableHead>Syndic</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredData.map((copropriete) => (
                    <TableRow
                      key={copropriete.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => handleViewCopropriete(copropriete)}
                    >
                      <TableCell className="font-medium">{copropriete.nom}</TableCell>
                      <TableCell className="text-gray-600 max-w-xs truncate">
                        <div className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 text-gray-400" />
                          {copropriete.adresse}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {copropriete.ville} ({copropriete.code_postal})
                        </Badge>
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {copropriete.nombre_lots || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {copropriete.nombre_batiments || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {copropriete.syndic || '-'}
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
                                handleViewCopropriete(copropriete);
                              }}
                            >
                              Voir détails
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditCopropriete(copropriete);
                              }}
                            >
                              Modifier
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditCopropriete(copropriete);
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
              {filteredData.length !== coproprietes.length &&
                ` sur ${coproprietes.length} au total`}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Entity Drawer */}
      <EntityDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        entity="copropriete"
        mode={drawerMode}
        data={selectedCopropriete}
        onSave={handleSaveCopropriete}
        onDelete={drawerMode === 'edit' ? handleDeleteCopropriete : undefined}
      />
    </div>
  );
};
