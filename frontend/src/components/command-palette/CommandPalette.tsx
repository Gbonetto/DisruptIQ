/**
 * CommandPalette - Global search and quick actions (Ctrl+K)
 * Premium command palette with fuzzy search and keyboard navigation
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command';
import {
  Users,
  Building,
  UserCog,
  Upload,
  Mail,
  FileText,
  Settings,
  TrendingUp,
  Download,
  Plus,
} from 'lucide-react';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface CommandAction {
  id: string;
  label: string;
  keywords?: string[];
  icon: React.ElementType;
  action: () => void;
  group: 'navigation' | 'actions' | 'recent';
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  open,
  onOpenChange,
}) => {
  const navigate = useNavigate();
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Command actions
  const commands: CommandAction[] = [
    // Navigation
    {
      id: 'nav-dashboard',
      label: 'Vue Globale',
      keywords: ['dashboard', 'accueil', 'home'],
      icon: TrendingUp,
      action: () => navigate('/admin'),
      group: 'navigation',
    },
    {
      id: 'nav-professionnels',
      label: 'Professionnels',
      keywords: ['vendors', 'fournisseurs', 'prestataires'],
      icon: Users,
      action: () => navigate('/admin/professionnels'),
      group: 'navigation',
    },
    {
      id: 'nav-coproprietes',
      label: 'Copropriétés',
      keywords: ['residences', 'immeubles', 'buildings'],
      icon: Building,
      action: () => navigate('/admin/coproprietes'),
      group: 'navigation',
    },
    {
      id: 'nav-coproprietaires',
      label: 'Copropriétaires',
      keywords: ['residents', 'owners', 'habitants'],
      icon: UserCog,
      action: () => navigate('/admin/coproprietaires'),
      group: 'navigation',
    },
    {
      id: 'nav-emails',
      label: 'Emails',
      keywords: ['mail', 'messages'],
      icon: Mail,
      action: () => navigate('/admin/emails'),
      group: 'navigation',
    },
    {
      id: 'nav-documents',
      label: 'Documents',
      keywords: ['files', 'fichiers'],
      icon: FileText,
      action: () => navigate('/admin/documents'),
      group: 'navigation',
    },
    {
      id: 'nav-settings',
      label: 'Configuration',
      keywords: ['settings', 'parametres'],
      icon: Settings,
      action: () => navigate('/admin/settings'),
      group: 'navigation',
    },

    // Actions
    {
      id: 'action-import',
      label: 'Importer des données',
      keywords: ['import', 'csv', 'upload'],
      icon: Upload,
      action: () => navigate('/admin/import'),
      group: 'actions',
    },
    {
      id: 'action-export',
      label: 'Exporter toutes les données',
      keywords: ['export', 'download', 'télécharger'],
      icon: Download,
      action: () => {
        console.log('Export triggered');
        onOpenChange(false);
      },
      group: 'actions',
    },
    {
      id: 'action-add-professionnel',
      label: 'Ajouter un professionnel',
      keywords: ['add', 'new', 'create', 'nouveau'],
      icon: Plus,
      action: () => {
        navigate('/admin/professionnels');
        // TODO: Open drawer to add
      },
      group: 'actions',
    },
    {
      id: 'action-add-copropriete',
      label: 'Ajouter une copropriété',
      keywords: ['add', 'new', 'create', 'nouveau'],
      icon: Plus,
      action: () => {
        navigate('/admin/coproprietes');
        // TODO: Open drawer to add
      },
      group: 'actions',
    },
  ];

  // Search in data (debounced)
  const searchData = useCallback(
    async (query: string) => {
      if (!query || query.length < 2) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);

      try {
        // Search across all entities
        const [professionnels, coproprietes, coproprietaires] = await Promise.all([
          fetch(`http://localhost:8000/api/admin/vendors?limit=5`).then((r) => r.json()),
          fetch(`http://localhost:8000/api/coproprietes/?limit=5&search=${query}`).then((r) => r.json()),
          fetch(`http://localhost:8000/api/coproprietaires/?limit=5&search=${query}`).then((r) => r.json()),
        ]);

        const results = [
          ...professionnels.slice(0, 3).map((p: any) => ({
            type: 'professionnel',
            label: p.name,
            sublabel: p.email,
            icon: Users,
            action: () => navigate(`/admin/professionnels/${p.id}`),
          })),
          ...coproprietes.slice(0, 3).map((c: any) => ({
            type: 'copropriete',
            label: c.nom,
            sublabel: `${c.ville} - ${c.code_postal}`,
            icon: Building,
            action: () => navigate(`/admin/coproprietes/${c.id}`),
          })),
          ...coproprietaires.slice(0, 3).map((c: any) => ({
            type: 'coproprietaire',
            label: `${c.prenom} ${c.nom}`,
            sublabel: c.email || c.numero_lot,
            icon: UserCog,
            action: () => navigate(`/admin/coproprietaires/${c.id}`),
          })),
        ];

        setSearchResults(results);
      } catch (error) {
        console.error('Search error:', error);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [navigate]
  );

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      const input = document.querySelector('[cmdk-input]') as HTMLInputElement;
      if (input && input.value) {
        searchData(input.value);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchData]);

  const handleSelect = (action: () => void) => {
    action();
    onOpenChange(false);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Rechercher ou exécuter une action..." />
      <CommandList>
        <CommandEmpty>
          {isSearching ? 'Recherche en cours...' : 'Aucun résultat trouvé.'}
        </CommandEmpty>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <>
            <CommandGroup heading="Résultats de recherche">
              {searchResults.map((result, index) => {
                const Icon = result.icon;
                return (
                  <CommandItem
                    key={`result-${index}`}
                    onSelect={() => handleSelect(result.action)}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    <div className="flex flex-col">
                      <span>{result.label}</span>
                      {result.sublabel && (
                        <span className="text-xs text-gray-500">{result.sublabel}</span>
                      )}
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        {/* Navigation Commands */}
        <CommandGroup heading="Navigation">
          {commands
            .filter((cmd) => cmd.group === 'navigation')
            .map((cmd) => {
              const Icon = cmd.icon;
              return (
                <CommandItem key={cmd.id} onSelect={() => handleSelect(cmd.action)}>
                  <Icon className="mr-2 h-4 w-4" />
                  <span>{cmd.label}</span>
                </CommandItem>
              );
            })}
        </CommandGroup>

        <CommandSeparator />

        {/* Action Commands */}
        <CommandGroup heading="Actions rapides">
          {commands
            .filter((cmd) => cmd.group === 'actions')
            .map((cmd) => {
              const Icon = cmd.icon;
              return (
                <CommandItem key={cmd.id} onSelect={() => handleSelect(cmd.action)}>
                  <Icon className="mr-2 h-4 w-4" />
                  <span>{cmd.label}</span>
                </CommandItem>
              );
            })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
};
