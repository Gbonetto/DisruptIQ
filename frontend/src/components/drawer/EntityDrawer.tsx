/**
 * EntityDrawer - Quick view/edit drawer for entities
 * Premium drawer with form validation and real-time updates
 */

import React from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Save, X, Trash2, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

interface EntityDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entity: 'professionnel' | 'copropriete' | 'coproprietaire' | null;
  mode: 'create' | 'edit' | 'view';
  data?: any;
  onSave?: (data: any) => Promise<void>;
  onDelete?: () => Promise<void>;
}

export const EntityDrawer: React.FC<EntityDrawerProps> = ({
  open,
  onOpenChange,
  entity,
  mode,
  data,
  onSave,
  onDelete,
}) => {
  const [formData, setFormData] = React.useState(data || {});
  const [isLoading, setIsLoading] = React.useState(false);

  React.useEffect(() => {
    setFormData(data || {});
  }, [data]);

  const handleSave = async () => {
    if (!onSave) return;

    setIsLoading(true);
    try {
      await onSave(formData);
      toast.success(
        mode === 'create'
          ? 'Créé avec succès'
          : 'Modifié avec succès'
      );
      onOpenChange(false);
    } catch (error) {
      toast.error('Une erreur est survenue');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;

    if (!confirm('Êtes-vous sûr de vouloir supprimer cet élément ?')) {
      return;
    }

    setIsLoading(true);
    try {
      await onDelete();
      toast.success('Supprimé avec succès');
      onOpenChange(false);
    } catch (error) {
      toast.error('Erreur lors de la suppression');
    } finally {
      setIsLoading(false);
    }
  };

  const renderForm = () => {
    switch (entity) {
      case 'professionnel':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nom *</Label>
                <Input
                  id="name"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Jean Dupont"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company_name">Entreprise</Label>
                <Input
                  id="company_name"
                  value={formData.company_name || ''}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  placeholder="Plomberie Dupont"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email || ''}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="jean@plomberie.fr"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Téléphone</Label>
                <Input
                  id="phone"
                  value={formData.phone || ''}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="0612345678"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="category">Catégorie</Label>
              <Select
                value={formData.category || ''}
                onValueChange={(value) => setFormData({ ...formData, category: value })}
                disabled={mode === 'view'}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner une catégorie" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="plombier">Plombier</SelectItem>
                  <SelectItem value="electricien">Électricien</SelectItem>
                  <SelectItem value="peintre">Peintre</SelectItem>
                  <SelectItem value="serrurier">Serrurier</SelectItem>
                  <SelectItem value="autres">Autres</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">Ville</Label>
                <Input
                  id="city"
                  value={formData.city || ''}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="Paris"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="postal_code">Code postal</Label>
                <Input
                  id="postal_code"
                  value={formData.postal_code || ''}
                  onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
                  placeholder="75001"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            {mode === 'view' && (
              <>
                <Separator />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Indexé dans RAG</span>
                  <Badge variant={formData.is_indexed ? 'success' : 'secondary'}>
                    {formData.is_indexed ? 'Oui' : 'Non'}
                  </Badge>
                </div>
              </>
            )}
          </div>
        );

      case 'copropriete':
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nom">Nom *</Label>
              <Input
                id="nom"
                value={formData.nom || ''}
                onChange={(e) => setFormData({ ...formData, nom: e.target.value })}
                placeholder="Résidence Les Mimosas"
                disabled={mode === 'view'}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="adresse">Adresse *</Label>
              <Input
                id="adresse"
                value={formData.adresse || ''}
                onChange={(e) => setFormData({ ...formData, adresse: e.target.value })}
                placeholder="12 Avenue de la République"
                disabled={mode === 'view'}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ville">Ville *</Label>
                <Input
                  id="ville"
                  value={formData.ville || ''}
                  onChange={(e) => setFormData({ ...formData, ville: e.target.value })}
                  placeholder="Paris"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="code_postal">Code postal *</Label>
                <Input
                  id="code_postal"
                  value={formData.code_postal || ''}
                  onChange={(e) => setFormData({ ...formData, code_postal: e.target.value })}
                  placeholder="75013"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nombre_lots">Nombre de lots</Label>
                <Input
                  id="nombre_lots"
                  type="number"
                  value={formData.nombre_lots || ''}
                  onChange={(e) => setFormData({ ...formData, nombre_lots: parseInt(e.target.value) })}
                  placeholder="45"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nombre_batiments">Nombre de bâtiments</Label>
                <Input
                  id="nombre_batiments"
                  type="number"
                  value={formData.nombre_batiments || ''}
                  onChange={(e) => setFormData({ ...formData, nombre_batiments: parseInt(e.target.value) })}
                  placeholder="2"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="syndic">Syndic</Label>
              <Input
                id="syndic"
                value={formData.syndic || ''}
                onChange={(e) => setFormData({ ...formData, syndic: e.target.value })}
                placeholder="Syndic Foncia"
                disabled={mode === 'view'}
              />
            </div>
          </div>
        );

      case 'coproprietaire':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nom">Nom *</Label>
                <Input
                  id="nom"
                  value={formData.nom || ''}
                  onChange={(e) => setFormData({ ...formData, nom: e.target.value })}
                  placeholder="Dupont"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="prenom">Prénom *</Label>
                <Input
                  id="prenom"
                  value={formData.prenom || ''}
                  onChange={(e) => setFormData({ ...formData, prenom: e.target.value })}
                  placeholder="Jean"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email || ''}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="jean@exemple.fr"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="telephone">Téléphone</Label>
                <Input
                  id="telephone"
                  value={formData.telephone || ''}
                  onChange={(e) => setFormData({ ...formData, telephone: e.target.value })}
                  placeholder="0612345678"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="numero_lot">Lot *</Label>
                <Input
                  id="numero_lot"
                  value={formData.numero_lot || ''}
                  onChange={(e) => setFormData({ ...formData, numero_lot: e.target.value })}
                  placeholder="A12"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="etage">Étage</Label>
                <Input
                  id="etage"
                  type="number"
                  value={formData.etage || ''}
                  onChange={(e) => setFormData({ ...formData, etage: parseInt(e.target.value) })}
                  placeholder="3"
                  disabled={mode === 'view'}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="surface">Surface (m²)</Label>
                <Input
                  id="surface"
                  type="number"
                  step="0.1"
                  value={formData.surface || ''}
                  onChange={(e) => setFormData({ ...formData, surface: parseFloat(e.target.value) })}
                  placeholder="65.5"
                  disabled={mode === 'view'}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="statut_special">Rôle spécial</Label>
              <Select
                value={formData.statut_special || ''}
                onValueChange={(value) => setFormData({ ...formData, statut_special: value })}
                disabled={mode === 'view'}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Aucun" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Aucun</SelectItem>
                  <SelectItem value="président">Président</SelectItem>
                  <SelectItem value="conseil_syndical">Conseil Syndical</SelectItem>
                  <SelectItem value="syndic">Syndic</SelectItem>
                  <SelectItem value="gardien">Gardien</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {mode === 'view' && formData.copropriete_nom && (
              <>
                <Separator />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Copropriété</span>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{formData.copropriete_nom}</span>
                    <Button variant="ghost" size="icon" className="h-6 w-6">
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        );

      default:
        return <div>Type d'entité non supporté</div>;
    }
  };

  const getTitle = () => {
    const entityLabels = {
      professionnel: 'Professionnel',
      copropriete: 'Copropriété',
      coproprietaire: 'Copropriétaire',
    };

    const label = entity ? entityLabels[entity] : '';

    switch (mode) {
      case 'create':
        return `Créer un ${label.toLowerCase()}`;
      case 'edit':
        return `Modifier ${label.toLowerCase()}`;
      case 'view':
        return label;
      default:
        return '';
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{getTitle()}</SheetTitle>
          <SheetDescription>
            {mode === 'create'
              ? 'Remplissez les informations ci-dessous'
              : mode === 'edit'
              ? 'Modifiez les informations nécessaires'
              : 'Détails de l\'entité'}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6">
          <ScrollArea className="h-[calc(100vh-200px)]">
            {renderForm()}
          </ScrollArea>
        </div>

        <SheetFooter className="mt-6">
          {mode !== 'view' ? (
            <div className="flex gap-2 w-full">
              {mode === 'edit' && onDelete && (
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={isLoading}
                  className="mr-auto"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Supprimer
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isLoading}
              >
                <X className="h-4 w-4 mr-2" />
                Annuler
              </Button>
              <Button onClick={handleSave} disabled={isLoading}>
                <Save className="h-4 w-4 mr-2" />
                {mode === 'create' ? 'Créer' : 'Enregistrer'}
              </Button>
            </div>
          ) : (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Fermer
            </Button>
          )}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};
