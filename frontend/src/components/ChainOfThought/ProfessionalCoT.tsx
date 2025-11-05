/**
 * Professional Chain of Thought UI Component
 *
 * Displays AI reasoning steps in a clean, notebook-style interface
 * Inspired by DeepSeek's CoT visualization
 *
 * Features:
 * - Collapsible sections
 * - Color-coded by step type
 * - Progress indicators
 * - Metadata for debugging
 * - Trust layer footer
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Brain, CheckCircle, XCircle, Loader } from 'lucide-react';

export interface ThoughtStep {
  type: 'analyzing' | 'classifying' | 'planning' | 'executing' | 'synthesizing' | 'completed' | 'error';
  title: string;
  content: string;
  agent: string;
  progress: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

interface ProfessionalCoTProps {
  thoughts: ThoughtStep[];
  defaultExpanded?: boolean;
}

export const ProfessionalCoT: React.FC<ProfessionalCoTProps> = ({
  thoughts,
  defaultExpanded = false
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const getStepIcon = (type: string, progress: number) => {
    if (progress === 1.0) return <CheckCircle className="w-4 h-4 text-green-600" />;
    if (type === 'error') return <XCircle className="w-4 h-4 text-red-600" />;
    return <Loader className="w-4 h-4 text-blue-600 animate-spin" />;
  };

  const getStepColor = (type: string): string => {
    const colors: Record<string, string> = {
      analyzing: 'border-l-blue-500',
      classifying: 'border-l-purple-500',
      planning: 'border-l-indigo-500',
      executing: 'border-l-orange-500',
      synthesizing: 'border-l-green-500',
      completed: 'border-l-green-600',
      error: 'border-l-red-600',
    };
    return colors[type] || 'border-l-gray-400';
  };

  const getStepLabel = (type: string): string => {
    const labels: Record<string, string> = {
      analyzing: 'Analyse',
      classifying: 'Classification',
      planning: 'Planification',
      executing: 'Exécution',
      synthesizing: 'Synthèse',
      completed: 'Terminé',
      error: 'Erreur',
    };
    return labels[type] || type;
  };

  if (!thoughts || thoughts.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden font-mono text-sm shadow-sm">
      {/* Header - Collapsible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-100 hover:bg-gray-150 transition-colors"
        aria-label={expanded ? "Masquer le raisonnement" : "Afficher le raisonnement"}
      >
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-gray-700" />
          <span className="font-semibold text-gray-800">🧠 Raisonnement de l'IA</span>
          <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded-full">
            {thoughts.length} étape{thoughts.length > 1 ? 's' : ''}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-gray-600" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-600" />
        )}
      </button>

      {/* Thought Steps - Collapsible */}
      {expanded && (
        <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
          {thoughts.map((thought, idx) => (
            <div
              key={idx}
              className={`border-l-4 ${getStepColor(thought.type)} bg-white rounded-r-lg p-4 shadow-sm transition-all hover:shadow-md`}
            >
              <div className="flex items-start gap-3">
                {/* Status Icon */}
                <div className="mt-1 flex-shrink-0">
                  {getStepIcon(thought.type, thought.progress)}
                </div>

                <div className="flex-1 min-w-0">
                  {/* Step Header */}
                  <div className="flex items-center justify-between mb-2 gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-semibold text-gray-800">{thought.title}</h4>
                      <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-normal uppercase tracking-wide">
                        {getStepLabel(thought.type)}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500 font-normal flex-shrink-0">
                      {thought.agent}
                    </span>
                  </div>

                  {/* Step Content */}
                  <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap break-words">
                    {thought.content}
                  </p>

                  {/* Progress Bar */}
                  {thought.progress > 0 && thought.progress < 1.0 && thought.type !== 'error' && (
                    <div className="mt-3 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-blue-600 h-full transition-all duration-300 ease-out"
                        style={{ width: `${thought.progress * 100}%` }}
                      />
                    </div>
                  )}

                  {/* Metadata (for debugging) */}
                  {thought.metadata && Object.keys(thought.metadata).length > 0 && (
                    <details className="mt-3">
                      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 select-none">
                        📊 Données techniques
                      </summary>
                      <pre className="mt-2 bg-gray-100 p-2 rounded text-xs overflow-x-auto max-h-40 overflow-y-auto">
                        {JSON.stringify(thought.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer - Trust Layer */}
      <div className="px-4 py-2 bg-gray-100 border-t border-gray-200 text-xs text-gray-600">
        <span className="flex items-center gap-1.5">
          <span className="text-base">💡</span>
          <strong className="font-semibold">Transparence IA:</strong>
          <span>Visualisez le processus de décision de l'IA en temps réel</span>
        </span>
      </div>
    </div>
  );
};

export default ProfessionalCoT;
