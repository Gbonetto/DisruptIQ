/**
 * SourceSelector - ChatGPT-style source selection
 *
 * Minimalist "+" button that opens upward dropdown
 */

import React, { useState, useRef, useEffect } from 'react';
import { Database, FileText, Globe, Plus, Check } from 'lucide-react';

export interface Source {
  id: 'sql' | 'rag' | 'web';
  label: string;
  icon: React.ReactNode;
  description: string;
  enabled: boolean;
}

interface SourceSelectorProps {
  selectedSources: string[];
  onChange: (sources: string[]) => void;
  className?: string;
}

const AVAILABLE_SOURCES: Source[] = [
  {
    id: 'sql',
    label: 'Base de données',
    icon: <Database className="w-4 h-4" />,
    description: 'Copropriétaires, professionnels, propriétés',
    enabled: true
  },
  {
    id: 'rag',
    label: 'Documents',
    icon: <FileText className="w-4 h-4" />,
    description: 'Contrats, règlements, factures',
    enabled: true
  },
  {
    id: 'web',
    label: 'Internet',
    icon: <Globe className="w-4 h-4" />,
    description: 'Recherche web via DuckDuckGo',
    enabled: true
  }
];

export const SourceSelector: React.FC<SourceSelectorProps> = ({
  selectedSources,
  onChange,
  className = ''
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const toggleSource = (sourceId: string) => {
    if (selectedSources.includes(sourceId)) {
      onChange(selectedSources.filter(s => s !== sourceId));
    } else {
      onChange([...selectedSources, sourceId]);
    }
  };

  const activeSourcesCount = selectedSources.length;
  const hasSelection = activeSourcesCount > 0;

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* ChatGPT-style Plus Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center justify-center
          w-8 h-8 rounded-lg
          transition-all duration-200
          ${hasSelection
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }
          ${isOpen ? 'ring-2 ring-blue-400' : ''}
        `}
        title={hasSelection ? `${activeSourcesCount} source(s) sélectionnée(s)` : 'Sélectionner les sources'}
        type="button"
      >
        {hasSelection ? (
          <span className="text-xs font-semibold">{activeSourcesCount}</span>
        ) : (
          <Plus className="w-4 h-4" />
        )}
      </button>

      {/* Dropdown Menu - Opens UPWARD */}
      {isOpen && (
        <div className="
          absolute bottom-full left-0 mb-2
          w-72
          bg-white dark:bg-gray-800
          border border-gray-200 dark:border-gray-700
          rounded-xl shadow-2xl
          z-50
          overflow-hidden
        ">
          {/* Header */}
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Sources de recherche
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {activeSourcesCount === 0
                ? 'Détection automatique'
                : `${activeSourcesCount} sélectionnée${activeSourcesCount > 1 ? 's' : ''}`
              }
            </p>
          </div>

          {/* Source Options */}
          <div className="py-2">
            {AVAILABLE_SOURCES.map((source) => {
              const isSelected = selectedSources.includes(source.id);
              const isDisabled = !source.enabled;

              return (
                <button
                  key={source.id}
                  onClick={() => !isDisabled && toggleSource(source.id)}
                  disabled={isDisabled}
                  className={`
                    w-full px-4 py-2.5 flex items-center gap-3
                    transition-colors duration-150
                    ${isDisabled
                      ? 'opacity-50 cursor-not-allowed'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer'
                    }
                    ${isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''}
                  `}
                >
                  {/* Checkbox */}
                  <div className={`
                    w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0
                    ${isSelected
                      ? 'bg-blue-600 border-blue-600'
                      : 'border-gray-300 dark:border-gray-600'
                    }
                  `}>
                    {isSelected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                  </div>

                  {/* Icon */}
                  <div className={`
                    flex-shrink-0
                    ${source.id === 'sql' ? 'text-blue-600' : ''}
                    ${source.id === 'rag' ? 'text-green-600' : ''}
                    ${source.id === 'web' ? 'text-purple-600' : ''}
                  `}>
                    {source.icon}
                  </div>

                  {/* Label & Description */}
                  <div className="flex-1 text-left min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {source.label}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {source.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-750 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              💡 Aucune sélection = détection automatique
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default SourceSelector;
