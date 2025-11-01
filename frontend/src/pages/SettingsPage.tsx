import React from 'react';
import { Settings } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Settings className="h-8 w-8" />
          Configuration
        </h1>
        <p className="text-gray-500 mt-1">
          Paramètres et configuration du système
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Paramètres</CardTitle>
          <CardDescription>
            Configuration en développement
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600">
            Les paramètres système seront disponibles prochainement.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
