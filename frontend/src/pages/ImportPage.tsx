import React, { useState } from 'react';
import { Upload, FileCheck, AlertCircle, CheckCircle, Download, ArrowRight, ArrowLeft } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { useMutation } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';

type ImportStep = 'upload' | 'preview' | 'result';

interface ImportResult {
  imported_count: number;
  failed_count: number;
  errors?: string[];
  message: string;
}

export const ImportPage: React.FC = () => {
  const [currentStep, setCurrentStep] = useState<ImportStep>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  // Import mutation
  const importMutation = useMutation({
    mutationFn: (file: File) => adminApi.importVendors(file),
    onSuccess: (response) => {
      setImportResult(response.data);
      setCurrentStep('result');
    },
  });

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setCurrentStep('preview');
      } else {
        alert('Veuillez sélectionner un fichier CSV');
      }
    }
  };

  // File input handler
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setCurrentStep('preview');
      } else {
        alert('Veuillez sélectionner un fichier CSV');
      }
    }
  };

  // Start import
  const handleImport = () => {
    if (selectedFile) {
      importMutation.mutate(selectedFile);
    }
  };

  // Reset wizard
  const handleReset = () => {
    setSelectedFile(null);
    setImportResult(null);
    setCurrentStep('upload');
    importMutation.reset();
  };

  // Download template
  const downloadTemplate = () => {
    const csvContent = `name,company_name,email,phone,category,statut
Jean Dupont,Plomberie Dupont,jean@plomberie.fr,0123456789,plombier,active
Marie Martin,Électricité Martin,marie@elec.fr,0987654321,électricien,active`;

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'template_professionnels.csv';
    link.click();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Upload className="h-8 w-8" />
          Import de données
        </h1>
        <p className="text-gray-500 mt-1">
          Importez vos professionnels en masse via CSV
        </p>
      </div>

      {/* Progress Steps */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                currentStep === 'upload' ? 'bg-blue-600 text-white' : 'bg-green-600 text-white'
              }`}>
                {currentStep === 'upload' ? '1' : <CheckCircle className="h-6 w-6" />}
              </div>
              <span className="font-medium">Upload</span>
            </div>

            <div className="flex-1 h-1 mx-4 bg-gray-200">
              <div className={`h-full transition-all ${
                ['preview', 'result'].includes(currentStep) ? 'bg-blue-600 w-full' : 'w-0'
              }`} />
            </div>

            <div className="flex items-center gap-2">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                currentStep === 'preview' ? 'bg-blue-600 text-white' :
                currentStep === 'result' ? 'bg-green-600 text-white' :
                'bg-gray-200 text-gray-500'
              }`}>
                {currentStep === 'result' ? <CheckCircle className="h-6 w-6" /> : '2'}
              </div>
              <span className="font-medium">Prévisualisation</span>
            </div>

            <div className="flex-1 h-1 mx-4 bg-gray-200">
              <div className={`h-full transition-all ${
                currentStep === 'result' ? 'bg-blue-600 w-full' : 'w-0'
              }`} />
            </div>

            <div className="flex items-center gap-2">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                currentStep === 'result' ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {currentStep === 'result' ? <CheckCircle className="h-6 w-6" /> : '3'}
              </div>
              <span className="font-medium">Résultat</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step 1: Upload */}
      {currentStep === 'upload' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Télécharger le fichier CSV</CardTitle>
              <CardDescription>
                Sélectionnez un fichier CSV contenant les données des professionnels
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                  dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <Upload className="h-16 w-16 mx-auto text-gray-400 mb-4" />
                <p className="text-xl font-medium text-gray-700 mb-2">
                  Glissez-déposez votre fichier CSV ici
                </p>
                <p className="text-sm text-gray-500 mb-6">
                  ou cliquez pour sélectionner un fichier
                </p>
                <input
                  type="file"
                  id="csv-upload"
                  className="hidden"
                  onChange={handleFileInput}
                  accept=".csv"
                />
                <Button size="lg" onClick={() => document.getElementById('csv-upload')?.click()}>
                  Sélectionner un fichier CSV
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Format requis</CardTitle>
              <CardDescription>
                Votre fichier CSV doit contenir les colonnes suivantes
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-medium text-sm mb-2">Colonnes obligatoires:</p>
                    <ul className="space-y-1 text-sm text-gray-600">
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">name</code> - Nom du professionnel</li>
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">email</code> - Email (unique)</li>
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">category</code> - Catégorie (plombier, électricien...)</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-sm mb-2">Colonnes optionnelles:</p>
                    <ul className="space-y-1 text-sm text-gray-600">
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">company_name</code> - Nom de l'entreprise</li>
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">phone</code> - Téléphone</li>
                      <li>• <code className="bg-gray-100 px-2 py-0.5 rounded">statut</code> - active/inactive</li>
                    </ul>
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <Button variant="outline" onClick={downloadTemplate}>
                    <Download className="h-4 w-4 mr-2" />
                    Télécharger le template CSV
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Step 2: Preview */}
      {currentStep === 'preview' && selectedFile && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Prévisualisation</CardTitle>
              <CardDescription>
                Vérifiez les données avant l'import
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileCheck className="h-10 w-10 text-blue-600" />
                    <div>
                      <p className="font-medium">{selectedFile.name}</p>
                      <p className="text-sm text-gray-600">
                        Taille: {(selectedFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  </div>
                  <Badge className="bg-blue-600 text-white">Prêt à importer</Badge>
                </div>

                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    L'import va créer ou mettre à jour les professionnels dans la base de données.
                    Les emails existants seront ignorés pour éviter les doublons.
                  </AlertDescription>
                </Alert>

                <div className="flex items-center gap-4 pt-4">
                  <Button variant="outline" onClick={handleReset}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Retour
                  </Button>
                  <Button
                    onClick={handleImport}
                    disabled={importMutation.isPending}
                    className="flex-1"
                  >
                    {importMutation.isPending ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                        Import en cours...
                      </>
                    ) : (
                      <>
                        Lancer l'import
                        <ArrowRight className="h-4 w-4 ml-2" />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Step 3: Result */}
      {currentStep === 'result' && importResult && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Résultat de l'import</CardTitle>
              <CardDescription>
                Récapitulatif des données importées
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Success Summary */}
                {importResult.imported_count > 0 && (
                  <div className="flex items-start gap-4 p-4 bg-green-50 rounded-lg">
                    <CheckCircle className="h-6 w-6 text-green-600 mt-1" />
                    <div className="flex-1">
                      <p className="font-medium text-green-900">
                        Import réussi !
                      </p>
                      <p className="text-sm text-green-700 mt-1">
                        {importResult.imported_count} professionnel(s) importé(s) avec succès
                      </p>
                    </div>
                  </div>
                )}

                {/* Error Summary */}
                {importResult.failed_count > 0 && (
                  <div className="flex items-start gap-4 p-4 bg-red-50 rounded-lg">
                    <AlertCircle className="h-6 w-6 text-red-600 mt-1" />
                    <div className="flex-1">
                      <p className="font-medium text-red-900">
                        {importResult.failed_count} échec(s) détecté(s)
                      </p>
                      {importResult.errors && importResult.errors.length > 0 && (
                        <ul className="text-sm text-red-700 mt-2 space-y-1">
                          {importResult.errors.slice(0, 5).map((error, index) => (
                            <li key={index}>• {error}</li>
                          ))}
                          {importResult.errors.length > 5 && (
                            <li className="text-red-600 font-medium">
                              ... et {importResult.errors.length - 5} autre(s) erreur(s)
                            </li>
                          )}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                {/* Progress Bar */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Taux de réussite</span>
                    <span className="font-medium">
                      {Math.round((importResult.imported_count / (importResult.imported_count + importResult.failed_count)) * 100)}%
                    </span>
                  </div>
                  <Progress
                    value={(importResult.imported_count / (importResult.imported_count + importResult.failed_count)) * 100}
                    className="h-2"
                  />
                </div>

                {/* Actions */}
                <div className="flex items-center gap-4 pt-4 border-t">
                  <Button onClick={handleReset} variant="outline" className="flex-1">
                    Nouvel import
                  </Button>
                  <Button
                    onClick={() => window.location.href = '/professionnels'}
                    className="flex-1"
                  >
                    Voir les professionnels
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};
