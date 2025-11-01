import React from 'react';
import { Mail } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export const EmailsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Mail className="h-8 w-8" />
          Emails
        </h1>
        <p className="text-gray-500 mt-1">
          Consultez vos emails et notifications
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Boîte de réception</CardTitle>
          <CardDescription>
            Gestion des emails en développement
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600">
            La gestion des emails sera disponible prochainement.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
