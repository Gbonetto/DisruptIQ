import React, { useState, useCallback, useEffect } from 'react';
import { FileText, Upload, Trash2, Eye, Search, Filter, CheckSquare, Square, FileCheck } from 'lucide-react';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentApi } from '@/lib/api';
import type { Document } from '@/types/api';

export const DocumentsPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<number | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // NEW: Selection state for checkboxes
  const [selectedDocIds, setSelectedDocIds] = useState<Set<number>>(new Set());

  const queryClient = useQueryClient();

  // NEW: Sync selected documents with backend
  useEffect(() => {
    if (selectedDocIds.size > 0) {
      // Send active document IDs to backend
      documentApi.setActive(Array.from(selectedDocIds))
        .catch(err => console.error('Failed to set active documents:', err));
    }
  }, [selectedDocIds]);

  // Fetch documents
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentApi.list().then(res => res.data),
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => documentApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
    },
  });

  // Filter documents
  const filteredDocuments = React.useMemo(() => {
    if (!documentsData?.documents) return [];

    return documentsData.documents.filter((doc) => {
      const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = categoryFilter === 'all' || doc.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [documentsData, searchQuery, categoryFilter]);

  // Handle file upload
  const handleFileUpload = useCallback((file: File) => {
    uploadMutation.mutate(file);
  }, [uploadMutation]);

  // Drag and drop handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  }, [handleFileUpload]);

  // File input handler
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  // Toggle individual document selection
  const toggleDocumentSelection = useCallback((docId: number) => {
    setSelectedDocIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return newSet;
    });
  }, []);

  // Toggle all documents
  const toggleSelectAll = useCallback(() => {
    if (selectedDocIds.size === filteredDocuments.length) {
      // Deselect all
      setSelectedDocIds(new Set());
    } else {
      // Select all
      setSelectedDocIds(new Set(filteredDocuments.map(doc => doc.id)));
    }
  }, [filteredDocuments, selectedDocIds.size]);

  // Clear selection
  const clearSelection = useCallback(() => {
    setSelectedDocIds(new Set());
  }, []);

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Get category badge color
  const getCategoryColor = (category?: string) => {
    switch (category) {
      case 'invoice': return 'bg-blue-100 text-blue-800';
      case 'contract': return 'bg-purple-100 text-purple-800';
      case 'letter': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Get document type icon
  const getDocumentIcon = (doc: Document) => {
    // Check if it's an invoice
    if (doc.category === 'invoice' || doc.document_type === 'facture') {
      return '🧾';
    }
    return '📄';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <FileText className="h-8 w-8" />
          Documents
        </h1>
        <p className="text-gray-500 mt-1">
          Gérez vos documents et fichiers - {documentsData?.total || 0} document(s)
        </p>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Uploader un document</CardTitle>
          <CardDescription>
            Glissez-déposez un fichier ou cliquez pour sélectionner
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">
              Glissez-déposez votre fichier ici
            </p>
            <p className="text-sm text-gray-500 mb-4">
              PDF, DOCX, images (max 10 MB)
            </p>
            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={handleFileInput}
              accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
            />
            <Button onClick={() => document.getElementById('file-upload')?.click()}>
              Sélectionner un fichier
            </Button>
            {uploadMutation.isPending && (
              <p className="mt-4 text-sm text-blue-600">Upload en cours...</p>
            )}
            {uploadMutation.isError && (
              <p className="mt-4 text-sm text-red-600">Erreur lors de l'upload</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CardTitle>Liste des documents</CardTitle>
              {selectedDocIds.size > 0 && (
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                    <FileCheck className="h-3 w-3 mr-1" />
                    {selectedDocIds.size} sélectionné{selectedDocIds.size > 1 ? 's' : ''}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearSelection}
                    className="h-7 text-xs"
                  >
                    Tout désélectionner
                  </Button>
                </div>
              )}
            </div>
            <div className="flex items-center gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Rechercher..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 w-64"
                />
              </div>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-40">
                  <Filter className="h-4 w-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes catégories</SelectItem>
                  <SelectItem value="invoice">Factures</SelectItem>
                  <SelectItem value="contract">Contrats</SelectItem>
                  <SelectItem value="letter">Courriers</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">Chargement...</div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              {searchQuery || categoryFilter !== 'all'
                ? 'Aucun document ne correspond aux filtres'
                : 'Aucun document. Uploadez votre premier fichier ci-dessus.'}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <button
                      onClick={toggleSelectAll}
                      className="flex items-center justify-center w-full hover:bg-gray-100 rounded p-1"
                    >
                      {selectedDocIds.size === filteredDocuments.length && filteredDocuments.length > 0 ? (
                        <CheckSquare className="h-4 w-4 text-blue-600" />
                      ) : (
                        <Square className="h-4 w-4 text-gray-400" />
                      )}
                    </button>
                  </TableHead>
                  <TableHead>Nom du fichier</TableHead>
                  <TableHead>Catégorie</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Taille</TableHead>
                  <TableHead>Date d'upload</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredDocuments.map((doc) => {
                  const isSelected = selectedDocIds.has(doc.id);
                  return (
                    <TableRow
                      key={doc.id}
                      className={isSelected ? 'bg-blue-50 hover:bg-blue-100' : ''}
                    >
                      <TableCell>
                        <button
                          onClick={() => toggleDocumentSelection(doc.id)}
                          className="flex items-center justify-center w-full hover:bg-gray-100 rounded p-1"
                        >
                          {isSelected ? (
                            <CheckSquare className="h-4 w-4 text-blue-600" />
                          ) : (
                            <Square className="h-4 w-4 text-gray-400" />
                          )}
                        </button>
                      </TableCell>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{getDocumentIcon(doc)}</span>
                          <span>{doc.filename}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {doc.category && (
                          <Badge className={getCategoryColor(doc.category)}>
                            {doc.category}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-gray-500">{doc.mime_type}</span>
                      </TableCell>
                      <TableCell>{formatFileSize(doc.file_size)}</TableCell>
                      <TableCell>
                        {new Date(doc.uploaded_at).toLocaleDateString('fr-FR')}
                      </TableCell>
                      <TableCell>
                        {doc.is_indexed ? (
                          <Badge className="bg-green-100 text-green-800">Indexé</Badge>
                        ) : (
                          <Badge className="bg-yellow-100 text-yellow-800">En attente</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedDocument(doc)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setDocumentToDelete(doc.id);
                              setDeleteDialogOpen(true);
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Document Preview Dialog */}
      <Dialog open={!!selectedDocument} onOpenChange={() => setSelectedDocument(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedDocument?.filename}</DialogTitle>
            <DialogDescription>
              {selectedDocument?.mime_type} • {selectedDocument && formatFileSize(selectedDocument.file_size)}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm font-medium">Date d'upload:</span>
                <span className="text-sm text-gray-600">
                  {selectedDocument && new Date(selectedDocument.uploaded_at).toLocaleString('fr-FR')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm font-medium">Catégorie:</span>
                <span className="text-sm text-gray-600">{selectedDocument?.category || 'Non classé'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm font-medium">Indexation:</span>
                <span className="text-sm text-gray-600">
                  {selectedDocument?.is_indexed ? 'Indexé dans Qdrant' : 'En attente'}
                </span>
              </div>
            </div>
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">
                La prévisualisation des documents sera disponible prochainement.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedDocument(null)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmer la suppression</DialogTitle>
            <DialogDescription>
              Êtes-vous sûr de vouloir supprimer ce document ? Cette action est irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false);
                setDocumentToDelete(null);
              }}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={() => documentToDelete && deleteMutation.mutate(documentToDelete)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Suppression...' : 'Supprimer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
