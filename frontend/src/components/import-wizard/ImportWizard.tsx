/**
 * ImportWizard - Multi-step CSV import wizard
 * Premium import experience with drag & drop, validation, and preview
 */

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Download,
} from 'lucide-react';
import { toast } from 'sonner';
import Papa, { ParseResult } from 'papaparse';

interface ImportWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type EntityType = 'professionnels' | 'coproprietes' | 'coproprietaires' | null;

type Step = 'entity-selection' | 'file-upload' | 'column-mapping' | 'preview' | 'import';

interface MappingRule {
  csvColumn: string;
  dbField: string | null;
}

export const ImportWizard: React.FC<ImportWizardProps> = ({
  open,
  onOpenChange,
}) => {
  const [step, setStep] = useState<Step>('entity-selection');
  const [entityType, setEntityType] = useState<EntityType>(null);
  const [file, setFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<any[]>([]);
  const [, setHeaders] = useState<string[]>([]);
  const [mappings, setMappings] = useState<MappingRule[]>([]);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importResults, setImportResults] = useState<any>(null);

  // Database field schemas
  type FieldSchema = Record<string, { label: string; required?: boolean }>;
  const fieldSchemas: Record<string, FieldSchema> = {
    professionnels: {
      name: { label: 'Nom', required: true },
      email: { label: 'Email', required: true },
      company_name: { label: 'Entreprise' },
      phone: { label: 'Téléphone' },
      category: { label: 'Catégorie' },
      city: { label: 'Ville' },
      postal_code: { label: 'Code postal' },
      address: { label: 'Adresse' },
    },
    coproprietes: {
      nom: { label: 'Nom', required: true },
      adresse: { label: 'Adresse', required: true },
      ville: { label: 'Ville', required: true },
      code_postal: { label: 'Code postal', required: true },
      nombre_lots: { label: 'Nombre de lots' },
      nombre_batiments: { label: 'Nombre de bâtiments' },
      annee_construction: { label: 'Année de construction' },
      syndic: { label: 'Syndic' },
      type_copropriete: { label: 'Type' },
    },
    coproprietaires: {
      nom: { label: 'Nom', required: true },
      prenom: { label: 'Prénom', required: true },
      email: { label: 'Email' },
      telephone: { label: 'Téléphone' },
      numero_lot: { label: 'Numéro de lot', required: true },
      etage: { label: 'Étage' },
      surface: { label: 'Surface' },
      statut: { label: 'Statut' },
      statut_special: { label: 'Rôle spécial' },
    },
  };

  // Dropzone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setFile(file);

    // Parse CSV
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results: ParseResult<Record<string, string>>) => {
        const headers = results.meta.fields || [];
        setCsvData(results.data);
        setHeaders(headers);

        // Auto-map columns
        const autoMappings = headers.map((csvCol: string) => {
          const dbField = autoMapColumn(csvCol);
          return { csvColumn: csvCol, dbField };
        });
        setMappings(autoMappings);

        setStep('column-mapping');
        toast.success(`${results.data.length} lignes détectées`);
      },
      error: (error: Error) => {
        toast.error(`Erreur de parsing: ${error.message}`);
      },
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv'],
    },
    maxFiles: 1,
  });

  // Auto-map CSV columns to DB fields
  const autoMapColumn = (csvCol: string): string | null => {
    if (!entityType) return null;

    const normalizedCsvCol = csvCol.toLowerCase().trim();
    const schema = fieldSchemas[entityType];

    // Direct match
    if (schema[normalizedCsvCol]) return normalizedCsvCol;

    // Fuzzy match
    const fuzzyMatches: Record<string, string[]> = {
      name: ['nom', 'name', 'prenom', 'first name'],
      email: ['email', 'e-mail', 'mail', 'courriel'],
      telephone: ['telephone', 'phone', 'tel', 'mobile'],
      ville: ['ville', 'city', 'town'],
      adresse: ['adresse', 'address', 'rue', 'street'],
    };

    for (const [dbField, aliases] of Object.entries(fuzzyMatches)) {
      if (aliases.some((alias) => normalizedCsvCol.includes(alias))) {
        return dbField;
      }
    }

    return null;
  };

  // Validate mappings
  const validateMappings = (): boolean => {
    if (!entityType) return false;

    const schema = fieldSchemas[entityType];
    const requiredFields = Object.entries(schema)
      .filter(([_, config]) => config.required)
      .map(([field, _]) => field);

    const mappedFields = mappings
      .filter((m) => m.dbField)
      .map((m) => m.dbField);

    const missingFields = requiredFields.filter(
      (field) => !mappedFields.includes(field)
    );

    if (missingFields.length > 0) {
      toast.error(
        `Champs requis manquants: ${missingFields
          .map((f) => schema[f].label)
          .join(', ')}`
      );
      return false;
    }

    return true;
  };

  // Transform data based on mappings
  const transformData = (): any[] => {
    return csvData.map((row) => {
      const transformedRow: any = {};

      mappings.forEach((mapping) => {
        if (mapping.dbField && row[mapping.csvColumn]) {
          transformedRow[mapping.dbField] = row[mapping.csvColumn];
        }
      });

      return transformedRow;
    });
  };

  // Import data
  const handleImport = async () => {
    if (!entityType) return;

    setImporting(true);
    setImportProgress(0);

    try {
      const data = transformData();

      // Import via API
      const endpoint = `http://localhost:8000/api/${entityType}/batch-import`;

      // Simulate progress
      const progressInterval = setInterval(() => {
        setImportProgress((prev) => Math.min(prev + 10, 90));
      }, 300);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: data }),
      });

      clearInterval(progressInterval);
      setImportProgress(100);

      if (!response.ok) {
        throw new Error('Import failed');
      }

      const results = await response.json();
      setImportResults(results);
      setStep('import');

      toast.success(`Import réussi: ${results.imported || data.length} éléments`);
    } catch (error) {
      toast.error('Erreur lors de l\'import');
      console.error(error);
    } finally {
      setImporting(false);
    }
  };

  // Download template
  const downloadTemplate = (type: EntityType) => {
    if (!type) return;

    const schema = fieldSchemas[type];
    const headers = Object.keys(schema);
    const csv = headers.join(',');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `template_${type}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Render step content
  const renderStep = () => {
    switch (step) {
      case 'entity-selection':
        return (
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <Label>Type de données à importer</Label>
              <div className="grid gap-3">
                <Button
                  variant={entityType === 'professionnels' ? 'default' : 'outline'}
                  className="justify-start h-auto py-4"
                  onClick={() => {
                    setEntityType('professionnels');
                    setStep('file-upload');
                  }}
                >
                  <div className="text-left">
                    <div className="font-semibold">👷 Professionnels</div>
                    <div className="text-sm text-gray-500">
                      Importer des prestataires et fournisseurs
                    </div>
                  </div>
                </Button>

                <Button
                  variant={entityType === 'coproprietes' ? 'default' : 'outline'}
                  className="justify-start h-auto py-4"
                  onClick={() => {
                    setEntityType('coproprietes');
                    setStep('file-upload');
                  }}
                >
                  <div className="text-left">
                    <div className="font-semibold">🏢 Copropriétés</div>
                    <div className="text-sm text-gray-500">
                      Importer des résidences et immeubles
                    </div>
                  </div>
                </Button>

                <Button
                  variant={entityType === 'coproprietaires' ? 'default' : 'outline'}
                  className="justify-start h-auto py-4"
                  onClick={() => {
                    setEntityType('coproprietaires');
                    setStep('file-upload');
                  }}
                >
                  <div className="text-left">
                    <div className="font-semibold">👥 Copropriétaires</div>
                    <div className="text-sm text-gray-500">
                      Importer des résidents et propriétaires
                    </div>
                  </div>
                </Button>
              </div>
            </div>
          </div>
        );

      case 'file-upload':
        return (
          <div className="space-y-6 py-4">
            <div className="flex items-center justify-between">
              <Label>Fichier CSV</Label>
              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadTemplate(entityType)}
              >
                <Download className="h-4 w-4 mr-2" />
                Télécharger modèle
              </Button>
            </div>

            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
                transition-colors
                ${
                  isDragActive
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400'
                }
              `}
            >
              <input {...getInputProps()} />
              {file ? (
                <div className="space-y-2">
                  <FileText className="h-12 w-12 mx-auto text-green-500" />
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <Upload className="h-12 w-12 mx-auto text-gray-400" />
                  <p className="font-medium">
                    {isDragActive
                      ? 'Déposez le fichier ici'
                      : 'Glissez-déposez un fichier CSV'}
                  </p>
                  <p className="text-sm text-gray-500">
                    ou cliquez pour sélectionner
                  </p>
                </div>
              )}
            </div>
          </div>
        );

      case 'column-mapping':
        return (
          <div className="space-y-4 py-4">
            <div>
              <Label>Mappage des colonnes</Label>
              <p className="text-sm text-gray-500 mt-1">
                Associez chaque colonne CSV à un champ de la base de données
              </p>
            </div>

            <ScrollArea className="h-96">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Colonne CSV</TableHead>
                    <TableHead>→</TableHead>
                    <TableHead>Champ Base de Données</TableHead>
                    <TableHead>Aperçu</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mappings.map((mapping, index) => {
                    const schema = entityType ? fieldSchemas[entityType] : {};
                    const preview = csvData[0]?.[mapping.csvColumn];

                    return (
                      <TableRow key={index}>
                        <TableCell className="font-medium">
                          {mapping.csvColumn}
                        </TableCell>
                        <TableCell>→</TableCell>
                        <TableCell>
                          <Select
                            value={mapping.dbField || 'ignore'}
                            onValueChange={(value) => {
                              const newMappings = [...mappings];
                              newMappings[index].dbField =
                                value === 'ignore' ? null : value;
                              setMappings(newMappings);
                            }}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ignore">
                                <span className="text-gray-500">Ignorer</span>
                              </SelectItem>
                              {Object.entries(schema).map(([field, config]) => (
                                <SelectItem key={field} value={field}>
                                  {config.label}
                                  {config.required && (
                                    <span className="text-red-500 ml-1">*</span>
                                  )}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell className="text-sm text-gray-500 truncate max-w-xs">
                          {preview}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </ScrollArea>
          </div>
        );

      case 'preview':
        const transformedData = transformData();
        return (
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-between">
              <div>
                <Label>Aperçu des données</Label>
                <p className="text-sm text-gray-500 mt-1">
                  {transformedData.length} éléments seront importés
                </p>
              </div>
              <Badge variant="secondary">
                {transformedData.length} lignes
              </Badge>
            </div>

            <ScrollArea className="h-96">
              <Table>
                <TableHeader>
                  <TableRow>
                    {mappings
                      .filter((m) => m.dbField)
                      .map((mapping, index) => (
                        <TableHead key={index}>
                          {entityType && fieldSchemas[entityType][mapping.dbField!]?.label}
                        </TableHead>
                      ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transformedData.slice(0, 10).map((row, rowIndex) => (
                    <TableRow key={rowIndex}>
                      {mappings
                        .filter((m) => m.dbField)
                        .map((mapping, colIndex) => (
                          <TableCell key={colIndex}>
                            {row[mapping.dbField!]}
                          </TableCell>
                        ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>

            {transformedData.length > 10 && (
              <p className="text-sm text-gray-500 text-center">
                ... et {transformedData.length - 10} autres lignes
              </p>
            )}
          </div>
        );

      case 'import':
        return (
          <div className="space-y-6 py-8 text-center">
            {importing ? (
              <>
                <div className="space-y-4">
                  <div className="w-16 h-16 mx-auto rounded-full bg-blue-100 flex items-center justify-center">
                    <Upload className="h-8 w-8 text-blue-600 animate-pulse" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">Import en cours...</h3>
                    <p className="text-sm text-gray-500">
                      Veuillez patienter pendant le traitement
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Progress value={importProgress} className="w-full" />
                    <p className="text-sm text-gray-500">{importProgress}%</p>
                  </div>
                </div>
              </>
            ) : importResults ? (
              <>
                <div className="w-16 h-16 mx-auto rounded-full bg-green-100 flex items-center justify-center">
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">Import réussi !</h3>
                  <p className="text-sm text-gray-500 mt-2">
                    {importResults.imported || csvData.length} éléments importés avec succès
                  </p>
                </div>
                {importResults.errors && importResults.errors.length > 0 && (
                  <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                    <div className="flex items-center gap-2 text-yellow-800">
                      <AlertCircle className="h-5 w-5" />
                      <span className="font-medium">
                        {importResults.errors.length} erreurs détectées
                      </span>
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>
        );
    }
  };

  // Navigation buttons
  const renderNavigation = () => {
    if (step === 'entity-selection') {
      return (
        <div className="flex justify-between">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
        </div>
      );
    }

    if (step === 'import') {
      return (
        <div className="flex justify-end">
          <Button onClick={() => onOpenChange(false)}>Terminer</Button>
        </div>
      );
    }

    return (
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => {
            const steps: Step[] = [
              'entity-selection',
              'file-upload',
              'column-mapping',
              'preview',
            ];
            const currentIndex = steps.indexOf(step);
            if (currentIndex > 0) {
              setStep(steps[currentIndex - 1]);
            }
          }}
          disabled={importing}
        >
          <ChevronLeft className="h-4 w-4 mr-2" />
          Précédent
        </Button>

        <Button
          onClick={() => {
            if (step === 'file-upload' && file) {
              setStep('column-mapping');
            } else if (step === 'column-mapping') {
              if (validateMappings()) {
                setStep('preview');
              }
            } else if (step === 'preview') {
              handleImport();
            }
          }}
          disabled={
            (step === 'file-upload' && !file) ||
            (step === 'column-mapping' && !validateMappings()) ||
            importing
          }
        >
          {step === 'preview' ? (
            <>
              <Upload className="h-4 w-4 mr-2" />
              Importer
            </>
          ) : (
            <>
              Suivant
              <ChevronRight className="h-4 w-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    );
  };

  // Step indicator
  const getStepNumber = (): number => {
    const steps: Step[] = [
      'entity-selection',
      'file-upload',
      'column-mapping',
      'preview',
      'import',
    ];
    return steps.indexOf(step) + 1;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Assistant d'import CSV</DialogTitle>
          <DialogDescription>
            Étape {getStepNumber()}/5 -{' '}
            {step === 'entity-selection' && 'Sélection du type de données'}
            {step === 'file-upload' && 'Upload du fichier'}
            {step === 'column-mapping' && 'Mappage des colonnes'}
            {step === 'preview' && 'Aperçu et confirmation'}
            {step === 'import' && 'Import en cours'}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          {renderStep()}
        </div>

        <div className="mt-6 border-t pt-4">
          {renderNavigation()}
        </div>
      </DialogContent>
    </Dialog>
  );
};
