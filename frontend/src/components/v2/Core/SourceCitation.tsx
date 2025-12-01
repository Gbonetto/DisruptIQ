import React, { useState } from 'react';
import { FileText, Database, Globe, ExternalLink } from 'lucide-react';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';

export interface Citation {
  id: number;
  type: 'sql' | 'rag' | 'web';
  title: string;
  content: string;
  url?: string;
  metadata?: Record<string, any>;
}

export interface SourceCitationProps {
  citations: Citation[];
}

const getCitationIcon = (type: Citation['type']) => {
  switch (type) {
    case 'sql':
      return <Database className="w-3 h-3" />;
    case 'rag':
      return <FileText className="w-3 h-3" />;
    case 'web':
      return <Globe className="w-3 h-3" />;
  }
};

const getCitationColor = (type: Citation['type']) => {
  switch (type) {
    case 'sql':
      return 'text-blue-600 bg-blue-50 hover:bg-blue-100 border-blue-200';
    case 'rag':
      return 'text-purple-600 bg-purple-50 hover:bg-purple-100 border-purple-200';
    case 'web':
      return 'text-green-600 bg-green-50 hover:bg-green-100 border-green-200';
  }
};

export const CitationNumber: React.FC<{ citation: Citation }> = ({ citation }) => {
  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <button
          className={`
            inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium
            border transition-colors cursor-pointer
            ${getCitationColor(citation.type)}
          `}
        >
          {getCitationIcon(citation.type)}
          [{citation.id}]
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80">
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-semibold text-foreground">
              {citation.title}
            </h4>
            <span className={`text-xs px-2 py-0.5 rounded-full ${getCitationColor(citation.type)}`}>
              {citation.type.toUpperCase()}
            </span>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-3">
            {citation.content}
          </p>
          {citation.url && (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              Voir la source
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

// Helper to get confidence level and color
const getConfidenceInfo = (score?: number) => {
  if (!score) return { label: '?', color: 'bg-gray-400', textColor: 'text-gray-700' };

  if (score >= 80) return { label: 'Élevée', color: 'bg-green-500', textColor: 'text-green-700' };
  if (score >= 60) return { label: 'Bonne', color: 'bg-blue-500', textColor: 'text-blue-700' };
  if (score >= 40) return { label: 'Moyenne', color: 'bg-yellow-500', textColor: 'text-yellow-700' };
  return { label: 'Faible', color: 'bg-orange-500', textColor: 'text-orange-700' };
};

export const SourceCitationFooter: React.FC<SourceCitationProps> = ({ citations = [] }) => {
  const [isExpanded, setIsExpanded] = useState(true); // Expanded by default for better UX

  if (!citations || citations.length === 0) return null;

  // Calculate average confidence
  const avgConfidence = citations.reduce((sum, c) => sum + (c.metadata?.score || 0), 0) / citations.length;
  const confidenceInfo = getConfidenceInfo(avgConfidence);

  return (
    <div className="mt-4 pt-3 border-t border-border/50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="flex items-center gap-2">
          <FileText className="w-3 h-3" />
          Sources ({citations.length})
          {/* Average confidence indicator */}
          <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-secondary/50" title={`Confiance moyenne: ${Math.round(avgConfidence)}%`}>
            <span className={`w-1.5 h-1.5 rounded-full ${confidenceInfo.color}`} />
            {Math.round(avgConfidence)}%
          </span>
        </span>
        <svg
          className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isExpanded && (
        <div className="space-y-1.5 mt-2">
          {citations.map((citation) => {
            // Extract table names from SQL metadata if available
            const tables = citation.metadata?.tables || citation.metadata?.table;
            const displayTables = tables ? (Array.isArray(tables) ? tables.join(', ') : tables) : null;

            // Get confidence indicator for this source
            const sourceConfidence = getConfidenceInfo(citation.metadata?.score);

            return (
              <div
                key={citation.id}
                className="flex gap-2 p-2 rounded bg-secondary/30 hover:bg-secondary/50 transition-colors"
              >
                <div className={`flex-shrink-0 w-5 h-5 rounded flex items-center justify-center ${getCitationColor(citation.type)}`}>
                  {getCitationIcon(citation.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[11px] font-medium text-foreground leading-tight flex items-center gap-1.5">
                      [{citation.id}] {citation.title}
                      {/* Individual confidence badge */}
                      {citation.metadata?.score !== undefined && (
                        <span className={`inline-flex items-center gap-0.5 px-1 py-0.5 rounded text-[9px] font-semibold ${sourceConfidence.textColor} bg-secondary/70`} title={sourceConfidence.label}>
                          <span className={`w-1 h-1 rounded-full ${sourceConfidence.color}`} />
                          {Math.round(citation.metadata.score)}%
                        </span>
                      )}
                    </span>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap uppercase tracking-wide">
                      {citation.type}
                    </span>
                  </div>

                  {/* SQL: Show tables */}
                  {citation.type === 'sql' && displayTables && (
                    <div className="text-[10px] text-blue-600 dark:text-blue-400 mt-0.5 font-mono">
                      Tables: {displayTables}
                    </div>
                  )}

                  {/* RAG: Show excerpt */}
                  {(citation.type === 'rag') && citation.content && (
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2 leading-snug italic">
                      "{citation.content}"
                    </p>
                  )}

                  {/* WEB: Show snippet + domain */}
                  {citation.type === 'web' && citation.content && (
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2 leading-snug italic">
                      "{citation.content}"
                    </p>
                  )}
                  {citation.type === 'web' && citation.metadata?.domain && (
                    <div className="text-[10px] text-green-600 dark:text-green-400 mt-0.5 font-mono">
                      {citation.metadata.domain}
                    </div>
                  )}

                  {citation.url && (
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-primary hover:underline flex items-center gap-0.5 mt-0.5 truncate max-w-full"
                      title={citation.url}
                    >
                      <span className="truncate">{citation.url}</span>
                      <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Helper function to inject citations into text (future implementation)
// export const injectCitations = (text: string, citations: Citation[]) => {
//   // This would need to be implemented based on how citations are marked in the text
//   // For now, we return the text as-is
//   return text;
// };
