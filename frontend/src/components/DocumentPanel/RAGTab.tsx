import { useState, useEffect } from 'react';
import { Upload, Trash2, CheckCircle, Circle, AlertCircle, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { documentApi } from '@/lib/api';

interface RAGDocument {
  id: number;
  filename: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  uploaded_at: string;
  indexed: boolean;
  chunk_count?: number;
}

const ACTIVE_DOCS_KEY = 'active_document_ids';

export function RAGTab() {
  const [documents, setDocuments] = useState<RAGDocument[]>([]);
  const [activeDocIds, setActiveDocIds] = useState<Set<number>>(() => {
    // Restaurer depuis localStorage au montage
    const saved = localStorage.getItem(ACTIVE_DOCS_KEY);
    if (saved) {
      try {
        return new Set(JSON.parse(saved));
      } catch (e) {
        return new Set();
      }
    }
    return new Set();
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [isFirstLoad, setIsFirstLoad] = useState(true);

  // Load documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  // Helper pour mettre à jour activeDocIds + sync backend + localStorage
  const updateActiveDocIds = (newIds: Set<number>) => {
    setActiveDocIds(newIds);

    // Sauvegarder dans localStorage
    const idsArray = Array.from(newIds);
    localStorage.setItem(ACTIVE_DOCS_KEY, JSON.stringify(idsArray));

    // Synchroniser avec le backend
    documentApi.setActive(idsArray, 'default').catch(err => {
      console.error('Failed to sync active documents:', err);
    });
  };

  const loadDocuments = async (silentReload = false) => {
    try {
      if (!silentReload) {
        setIsLoading(true);
      }
      const response = await documentApi.list();
      const docs = response.data.documents || [];
      setDocuments(docs as unknown as RAGDocument[]);

      // Premier chargement: activer tous les docs (sauf si déjà restauré depuis localStorage)
      // Rechargements suivants: garder état actuel
      if (isFirstLoad) {
        setIsFirstLoad(false);

        // Si localStorage est vide, activer tous les docs
        if (activeDocIds.size === 0) {
          const allIds = docs.map((d: any) => d.id);
          updateActiveDocIds(new Set(allIds));
        } else {
          // Vérifier que les docs restaurés existent toujours
          const existingDocIds = new Set(docs.map((d: any) => d.id));
          const validIds = new Set<number>();

          activeDocIds.forEach(id => {
            if (existingDocIds.has(id)) {
              validIds.add(id);
            }
          });

          // Mettre à jour si certains docs ont été supprimés
          if (validIds.size !== activeDocIds.size) {
            updateActiveDocIds(validIds);
          }
        }
      }

      if (!silentReload && docs.length > 0) {
        toast.success(`${docs.length} documents chargés`);
      }
    } catch (error) {
      console.error('Échec du chargement des documents:', error);
      toast.error('Échec du chargement des documents');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleDocument = (id: number) => {
    const next = new Set(activeDocIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    updateActiveDocIds(next);
  };

  const handleDelete = async (doc: RAGDocument) => {
    // Demander confirmation avec un toast custom
    const toastId = `confirm-delete-${doc.id}`;

    toast.custom(
      () => (
        <div className="bg-white border border-orange-200 rounded-lg shadow-lg p-4 max-w-md">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-gray-900 mb-1">
                Confirmer la suppression
              </h4>
              <p className="text-xs text-gray-600 mb-3">
                Voulez-vous vraiment supprimer <strong>{doc.original_filename}</strong> ?
                <br />
                Cette action supprimera également tous les chunks indexés dans Qdrant.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    toast.dismiss(toastId);
                    try {
                      toast.loading('Suppression en cours...', { id: `delete-${doc.id}` });
                      await documentApi.delete(doc.id);

                      setDocuments(prev => prev.filter(d => d.id !== doc.id));
                      setActiveDocIds(prev => {
                        const next = new Set(prev);
                        next.delete(doc.id);
                        return next;
                      });

                      toast.success(`${doc.original_filename} supprimé`, {
                        id: `delete-${doc.id}`,
                        description: 'Document et chunks supprimés'
                      });
                    } catch (error) {
                      console.error('Échec de la suppression:', error);
                      toast.error('Échec de la suppression', {
                        id: `delete-${doc.id}`,
                        description: 'Une erreur est survenue'
                      });
                    }
                  }}
                  className="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors"
                >
                  Supprimer
                </button>
                <button
                  onClick={() => {
                    toast.dismiss(toastId);
                    toast.info('Suppression annulée');
                  }}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors"
                >
                  Annuler
                </button>
              </div>
            </div>
          </div>
        </div>
      ),
      { id: toastId, duration: Infinity }
    );
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    await uploadFiles(files);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    await uploadFiles(files);
  };

  const uploadFiles = async (files: File[]) => {
    const allowedTypes = ['application/pdf', 'application/msword',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'text/plain'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    for (const file of files) {
      // Validation type de fichier
      if (!allowedTypes.includes(file.type)) {
        toast.error(`${file.name}: Type de fichier non supporté`, {
          description: 'Formats acceptés: PDF, DOCX, TXT'
        });
        continue;
      }

      // Validation taille
      if (file.size > maxSize) {
        toast.error(`${file.name}: Fichier trop volumineux`, {
          description: 'Taille maximum: 10 MB'
        });
        continue;
      }

      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));

        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            setUploadProgress(prev => ({ ...prev, [file.name]: percent }));
          }
        });

        xhr.addEventListener('load', async () => {
          setUploadProgress(prev => {
            const next = { ...prev };
            delete next[file.name];
            return next;
          });

          if (xhr.status === 200) {
            toast.success(`${file.name} uploadé et indexé`, {
              description: 'Prêt pour la recherche'
            });

            // Recharger la liste sans toast
            await loadDocuments(true);
          } else {
            // Parser la réponse JSON du backend
            let errorMessage = 'Erreur inconnue';
            try {
              const errorData = JSON.parse(xhr.responseText);
              if (errorData.detail) {
                // Traduire les erreurs courantes
                const detail = errorData.detail;
                if (detail.includes('timed out')) {
                  errorMessage = 'Délai dépassé (fichier trop volumineux ou serveur lent)';
                } else if (detail.includes('Unsupported file type')) {
                  errorMessage = 'Type de fichier non supporté';
                } else if (detail.includes('File too large')) {
                  errorMessage = 'Fichier trop volumineux (max 10 MB)';
                } else if (detail.includes('Failed to extract text')) {
                  errorMessage = 'Impossible d\'extraire le texte du document';
                } else {
                  errorMessage = detail;
                }
              }
            } catch (e) {
              errorMessage = xhr.responseText.substring(0, 100);
            }

            toast.error(`Échec upload ${file.name}`, {
              description: errorMessage
            });
          }
        });

        xhr.addEventListener('error', () => {
          setUploadProgress(prev => {
            const next = { ...prev };
            delete next[file.name];
            return next;
          });
          toast.error(`Erreur réseau: ${file.name}`);
        });

        xhr.addEventListener('timeout', () => {
          setUploadProgress(prev => {
            const next = { ...prev };
            delete next[file.name];
            return next;
          });
          toast.error(`Timeout: ${file.name}`, {
            description: 'Le fichier est peut-être trop gros'
          });
        });

        xhr.open('POST', `http://localhost:8000/api/documents/upload?session_id=default`);
        xhr.timeout = 120000; // 2 minutes timeout
        xhr.send(formData);

      } catch (error) {
        console.error('Erreur upload:', error);
        toast.error(`Erreur: ${file.name}`);
        setUploadProgress(prev => {
          const next = { ...prev };
          delete next[file.name];
          return next;
        });
      }
    }
  };

  const selectAll = () => {
    const allIds = documents.map(d => d.id);
    updateActiveDocIds(new Set(allIds));
  };

  const clearAll = () => {
    updateActiveDocIds(new Set());
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-neon-cyan mx-auto mb-4"></div>
          <p className="text-gray-400 font-pixel">Chargement des documents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Zone Upload */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors pixel-border-sm ${
          isDragging
            ? 'border-neon-cyan bg-retro-dark/50 neon-glow-cyan'
            : 'border-neon-violet/50 hover:border-neon-cyan/70 hover:bg-retro-dark/30'
        }`}
      >
        <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragging ? 'text-neon-cyan' : 'text-gray-400'}`} />
        <p className="text-sm font-medium text-white mb-1">
          Déposez vos fichiers ici ou cliquez pour parcourir
        </p>
        <p className="text-xs text-gray-400 mb-3">
          PDF, DOCX, TXT (max 10 MB)
        </p>
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".pdf,.doc,.docx,.txt"
          onChange={handleFileSelect}
          className="hidden"
        />
        <label
          htmlFor="file-upload"
          className="inline-block px-4 py-2 retro-gradient-cyber text-white text-sm font-medium rounded-lg hover:animate-neon-pulse cursor-pointer transition-colors pixel-border-sm"
        >
          Parcourir
        </label>
      </div>

      {/* Upload Progress */}
      {Object.keys(uploadProgress).length > 0 && (
        <div className="space-y-2">
          {Object.entries(uploadProgress).map(([filename, progress]) => (
            <div key={filename} className="bg-retro-dark p-3 rounded-lg border border-neon-cyan/50 pixel-border-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">{filename}</span>
                <span className="text-xs text-neon-cyan font-pixel">{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-retro-gray rounded-full h-1.5">
                <div
                  className="bg-neon-cyan h-1.5 rounded-full transition-all animate-neon-pulse"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* En-tête Liste Documents */}
      <div className="flex items-center justify-between pt-2">
        <h3 className="text-sm font-semibold text-white font-pixel">
          Documents Actifs ({activeDocIds.size}/{documents.length})
        </h3>
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="text-xs text-neon-cyan hover:neon-glow-cyan font-medium transition-all"
          >
            Tout sélectionner
          </button>
          <button
            onClick={clearAll}
            className="text-xs text-gray-400 hover:text-white font-medium transition-all"
          >
            Tout désélectionner
          </button>
        </div>
      </div>

      {/* Liste Documents */}
      {documents.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-16 h-16 mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 font-medium mb-2 font-pixel">Aucun document</p>
          <p className="text-sm text-gray-500">Uploadez votre premier document pour commencer</p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => {
            const isActive = activeDocIds.has(doc.id);

            return (
              <div
                key={doc.id}
                className={`p-3 rounded-lg border transition-all pixel-border-sm ${
                  isActive
                    ? 'border-neon-cyan bg-retro-dark neon-border-cyan'
                    : 'border-neon-violet/20 bg-retro-dark/50 opacity-60'
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleDocument(doc.id)}
                    className="mt-0.5 focus:outline-none"
                  >
                    {isActive ? (
                      <CheckCircle className="w-5 h-5 text-indigo-600" />
                    ) : (
                      <Circle className="w-5 h-5 text-gray-400" />
                    )}
                  </button>

                  {/* Document Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h4 className="text-sm font-medium text-white truncate">
                        {doc.original_filename}
                      </h4>
                      {isActive && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-neon-green/20 text-neon-green whitespace-nowrap pixel-border-sm border border-neon-green/50">
                          Actif
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-2">
                      <span>{formatFileSize(doc.file_size)}</span>
                      <span>•</span>
                      <span>{formatDate(doc.uploaded_at)}</span>
                      {doc.indexed && (
                        <>
                          <span>•</span>
                          <span className="text-neon-green font-medium">Indexé</span>
                        </>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDelete(doc)}
                        className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-neon-pink hover:bg-retro-dark hover:border-neon-pink/50 rounded transition-colors border border-transparent"
                      >
                        <Trash2 className="w-3 h-3" />
                        Supprimer
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bannière Info */}
      {documents.length > 0 && (
        <div className="bg-retro-dark/50 border border-neon-violet/50 rounded-lg p-3 pixel-border-sm">
          <div className="flex gap-2">
            <AlertCircle className="w-4 h-4 text-neon-violet mt-0.5 flex-shrink-0" />
            <div className="text-xs text-gray-300">
              <p className="font-medium mb-1 text-neon-violet font-pixel">Comment ça fonctionne</p>
              <p>Seuls les documents cochés seront interrogés lors de vos recherches. Décochez les documents que vous souhaitez exclure des résultats.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
