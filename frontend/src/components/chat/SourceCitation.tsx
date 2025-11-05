/**
 * SourceCitation - Citations élégantes style footnote académique
 * Design: Discret, minimaliste, inspiré des publications académiques
 */

import { FileText, Database, Globe } from 'lucide-react';
import { motion } from 'framer-motion';

interface Source {
  type: 'sql' | 'rag' | 'web';
  title: string;
  content?: string;
  metadata?: {
    page?: number;
    table?: string;
    url?: string;
    document_type?: string;
  };
}

interface SourceCitationProps {
  sources: Source[];
}

const sourceIcons = {
  rag: FileText,
  sql: Database,
  web: Globe,
};

const sourceLabels = {
  rag: 'Document',
  sql: 'Base de données',
  web: 'Web',
};

export function SourceCitation({ sources }: SourceCitationProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      className="mt-6 pt-4 border-t border-gray-200"
    >
      {/* Header discret */}
      <div className="flex items-center gap-2 mb-3">
        <div className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">
          Sources
        </div>
        <div className="h-px flex-1 bg-gray-200" />
      </div>

      {/* Liste des sources style footnote */}
      <div className="space-y-2">
        {sources.map((source, index) => {
          const Icon = sourceIcons[source.type];

          return (
            <div
              key={index}
              className="flex items-start gap-2.5 text-sm group hover:bg-gray-50 -mx-2 px-2 py-1.5 rounded-md transition-colors"
            >
              {/* Numéro de référence style académique */}
              <span className="text-[11px] font-medium text-gray-400 mt-0.5 flex-shrink-0 w-4">
                {index + 1}
              </span>

              {/* Icône du type de source */}
              <Icon className="w-3.5 h-3.5 text-gray-400 mt-0.5 flex-shrink-0" />

              {/* Contenu de la citation */}
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 flex-wrap">
                  {/* Type de source */}
                  <span className="text-[11px] text-gray-500">
                    {sourceLabels[source.type]}:
                  </span>

                  {/* Titre de la source */}
                  <span className="text-gray-700 font-medium">
                    {source.title}
                  </span>
                </div>

                {/* Métadonnées additionnelles */}
                {source.metadata && (
                  <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2 flex-wrap">
                    {source.metadata.page && (
                      <span>p. {source.metadata.page}</span>
                    )}
                    {source.metadata.table && (
                      <span>Table: {source.metadata.table}</span>
                    )}
                    {source.metadata.document_type && (
                      <span className="px-1.5 py-0.5 bg-gray-100 rounded text-[10px] uppercase tracking-wide">
                        {source.metadata.document_type}
                      </span>
                    )}
                    {source.metadata.url && (
                      <a
                        href={source.metadata.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline truncate max-w-xs"
                      >
                        {new URL(source.metadata.url).hostname}
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Note explicative si beaucoup de sources */}
      {sources.length > 3 && (
        <div className="mt-3 text-[10px] text-gray-400 italic">
          {sources.length} sources consultées
        </div>
      )}
    </motion.div>
  );
}
