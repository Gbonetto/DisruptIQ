import React from 'react';
import { FileText } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const DocumentsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <FileText className="h-8 w-8" />
          Documents
        </h1>
        <p className="text-gray-500 mt-1">
          Gérez vos documents et fichiers
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Gestion documentaire</CardTitle>
          <CardDescription>
            Fonctionnalité en développement
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600">
            Le système de gestion documentaire sera disponible prochainement.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
