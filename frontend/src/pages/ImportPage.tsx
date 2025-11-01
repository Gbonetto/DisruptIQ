import React from 'react';
import { Upload } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const ImportPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Upload className="h-8 w-8" />
          Import de données
        </h1>
        <p className="text-gray-500 mt-1">
          Importez vos données en masse via CSV
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Import Wizard</CardTitle>
          <CardDescription>
            Cette fonctionnalité sera bientôt disponible
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600">
            Utilisez le Import Wizard depuis les pages de données individuelles pour importer vos fichiers CSV.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
