/**
 * CopropriétairesPage - Manage residents/owners
 * Premium data table with search, filters, and quick actions
 */

import React, { useState, useEffect } from 'react';
import {
  UserCog,
  Plus,
  Search,
  Download,
  Upload,
  Trash2,
  MoreVertical,
  RefreshCcw,
  Building,
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

interface Coproprietaire {
  id: number;
  nom: string;
  prenom: string;
  email?: string;
  telephone?: string;
  copropriete_id: number;
  copropriete_nom?: string;
  numero_lot: string;
  etage?: number;
  surface?: number;
  statut?: string;
  statut_special?: string;
  created_at: string;
}

export const CopropriétairesPage: React.FC = () => {
  const [coproprietaires, setCoproprietaires] = useState<Coproprietaire[]>([]);
  const [filteredData, setFilteredData] = useState<Coproprietaire[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [coproprieteFilter, setCoproprieteFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit' | 'view'>('view');
  const [selectedCoproprietaire, setSelectedCoproprietaire] = useState<Coproprietaire | null>(null);

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
    fetchCoproprietaires();
  }, []);

  useEffect(() => {
    filterData();
  }, [coproprietaires, searchQuery, coproprieteFilter, statusFilter]);

  const fetchCoproprietaires = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/coproprietaires/');
      const data = await response.json();
      setCoproprietaires(data);
    } catch (error) {
      console.error('Error fetching copropriétaires:', error);
      toast.error('Erreur lors du chargement des copropriétaires');
    } finally {
      setIsLoading(false);
    }
  };

  const filterData = () => {
    let filtered = [...coproprietaires];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.nom.toLowerCase().includes(query) ||
          c.prenom.toLowerCase().includes(query) ||
          c.email?.toLowerCase().includes(query) ||
          c.telephone?.includes(query) ||
          c.numero_lot.toLowerCase().includes(query) ||
          c.copropriete_nom?.toLowerCase().includes(query)
      );
    }

    // Copropriété filter
    if (coproprieteFilter !== 'all') {
      filtered = filtered.filter((c) => c.copropriete_id === parseInt(coproprieteFilter));
    }

    // Status filter
    if (statusFilter !== 'all') {
      if (statusFilter === 'special') {
        filtered = filtered.filter((c) => c.statut_special);
      } else {
        filtered = filtered.filter((c) => !c.statut_special);
      }
    }

    setFilteredData(filtered);
  };

  const handleViewCoproprietaire = (coproprietaire: Coproprietaire) => {
    setSelectedCoproprietaire(coproprietaire);
    setDrawerMode('view');
    setDrawerOpen(true);
  };

  const handleEditCoproprietaire = (coproprietaire: Coproprietaire) => {
    setSelectedCoproprietaire(coproprietaire);
    setDrawerMode('edit');
    setDrawerOpen(true);
  };

  const handleCreateCoproprietaire = () => {
    setSelectedCoproprietaire(null);
    setDrawerMode('create');
    setDrawerOpen(true);
  };

  const handleSaveCoproprietaire = async (data: any) => {
    try {
      const url = drawerMode === 'create'
        ? 'http://localhost:8000/api/coproprietaires/'
        : `http://localhost:8000/api/coproprietaires/${selectedCoproprietaire?.id}`;

      const method = drawerMode === 'create' ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) throw new Error('Failed to save');

      await fetchCoproprietaires();
      toast.success(
        drawerMode === 'create'
          ? 'Copropriétaire créé avec succès'
          : 'Copropriétaire modifié avec succès'
      );
    } catch (error) {
      toast.error('Erreur lors de la sauvegarde');
      throw error;
    }
  };

  const handleDeleteCoproprietaire = async () => {
    if (!selectedCoproprietaire) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/coproprietaires/${selectedCoproprietaire.id}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete');

      await fetchCoproprietaires();
      toast.success('Copropriétaire supprimé avec succès');
    } catch (error) {
      toast.error('Erreur lors de la suppression');
      throw error;
    }
  };

  const handleExportCSV = () => {
    const headers = [
      'ID',
      'Nom',
      'Prénom',
      'Email',
      'Téléphone',
      'Copropriété',
      'Lot',
      'Étage',
      'Surface',
      'Statut spécial',
    ];
    const csvData = filteredData.map((c) => [
      c.id,
      c.nom,
      c.prenom,
      c.email || '',
      c.telephone || '',
      c.copropriete_nom || '',
      c.numero_lot,
      c.etage || '',
      c.surface || '',
      c.statut_special || '',
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
    link.download = `coproprietaires_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();

    toast.success('Export CSV réussi');
  };

  const coproprietes = Array.from(
    new Map(
      coproprietaires
        .filter((c) => c.copropriete_nom)
        .map((c) => [c.copropriete_id, c.copropriete_nom])
    )
  );

  const specialRolesCount = coproprietaires.filter((c) => c.statut_special).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <UserCog className="h-8 w-8" />
          Copropriétaires
        </h1>
        <p className="text-gray-500 mt-1">
          Gérez les résidents et propriétaires
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total copropriétaires</CardDescription>
            <CardTitle className="text-3xl">{coproprietaires.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Rôles spéciaux</CardDescription>
            <CardTitle className="text-3xl text-purple-600">{specialRolesCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Copropriétés</CardDescription>
            <CardTitle className="text-3xl text-green-600">{coproprietes.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Liste des copropriétaires</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchCoproprietaires}>
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
                  if (!confirm('Êtes-vous sûr de vouloir supprimer TOUS les copropriétaires ? Cette action est irréversible !')) return;
                  try {
                    await Promise.all(
                      coproprietaires.map(c =>
                        fetch(`http://localhost:8000/api/coproprietaires/${c.id}`, {
                          method: 'DELETE'
                        })
                      )
                    );
                    await fetchCoproprietaires();
                    toast.success('Tous les copropriétaires ont été supprimés');
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
                  placeholder="Rechercher par nom, prénom, email, téléphone, lot..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Copropriété Filter */}
            <Select value={coproprieteFilter} onValueChange={setCoproprieteFilter}>
              <SelectTrigger className="w-full md:w-56">
                <SelectValue placeholder="Copropriété" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes les copropriétés</SelectItem>
                {coproprietes.map(([id, nom]) => (
                  <SelectItem key={id} value={id.toString()}>
                    {nom}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Statut" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les statuts</SelectItem>
                <SelectItem value="special">Rôles spéciaux</SelectItem>
                <SelectItem value="regular">Résidents standards</SelectItem>
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
              <UserCog className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Aucun copropriétaire trouvé
              </h3>
              <p className="text-gray-500 mb-4">
                {searchQuery || coproprieteFilter !== 'all'
                  ? 'Essayez de modifier vos filtres'
                  : 'Commencez par ajouter votre premier copropriétaire'}
              </p>
              {!searchQuery && coproprieteFilter === 'all' && (
                <Button onClick={handleCreateCoproprietaire}>
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter un copropriétaire
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
                    <TableHead>Copropriété</TableHead>
                    <TableHead>Lot</TableHead>
                    <TableHead>Étage</TableHead>
                    <TableHead>Statut spécial</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredData.map((coproprietaire) => (
                    <TableRow
                      key={coproprietaire.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => handleViewCoproprietaire(coproprietaire)}
                    >
                      <TableCell className="font-medium">
                        {coproprietaire.prenom} {coproprietaire.nom}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {coproprietaire.email || '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Building className="h-3 w-3 text-gray-400" />
                          <span className="text-sm">{coproprietaire.copropriete_nom || '-'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{coproprietaire.numero_lot}</Badge>
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {coproprietaire.etage !== undefined ? coproprietaire.etage : '-'}
                      </TableCell>
                      <TableCell>
                        {coproprietaire.statut_special ? (
                          <Badge variant="default" className="capitalize">
                            {coproprietaire.statut_special}
                          </Badge>
                        ) : (
                          <span className="text-gray-400 text-sm">-</span>
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
                                handleViewCoproprietaire(coproprietaire);
                              }}
                            >
                              Voir détails
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditCoproprietaire(coproprietaire);
                              }}
                            >
                              Modifier
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditCoproprietaire(coproprietaire);
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
              {filteredData.length !== coproprietaires.length &&
                ` sur ${coproprietaires.length} au total`}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Entity Drawer */}
      <EntityDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        entity="coproprietaire"
        mode={drawerMode}
        data={selectedCoproprietaire}
        onSave={handleSaveCoproprietaire}
        onDelete={drawerMode === 'edit' ? handleDeleteCoproprietaire : undefined}
      />
    </div>
  );
};
