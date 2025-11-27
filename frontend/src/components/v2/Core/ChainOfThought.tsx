/**
 * ChainOfThought - Composant de visualisation de la chaîne de pensée
 * Style DeepSeek avec animations fluides et affichage en temps réel
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, ChevronDown, Brain, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

// === Types ===
export type ThoughtType =
  // General phases
  | 'analyzing' | 'classifying' | 'planning' | 'executing' | 'waiting'
  | 'processing' | 'synthesizing' | 'completed' | 'error' | 'warning'
  // SQL Agent
  | 'sql_generating' | 'sql_executing' | 'sql_results'
  // RAG Agent
  | 'rag_searching' | 'rag_retrieving' | 'rag_reranking' | 'rag_results'
  // Web Agent
  | 'web_searching' | 'web_fetching' | 'web_results'
  // Legal Agent
  | 'legal_searching' | 'legal_analyzing' | 'legal_results'
  // Email Agent
  | 'email_drafting' | 'email_sending' | 'email_sent'
  // Workflow Agent (N8N)
  | 'workflow_triggering' | 'workflow_sending' | 'workflow_success' | 'workflow_error'
  // Digest Agent
  | 'digest_fetching' | 'digest_classifying' | 'digest_generating'
  // Table Generation
  | 'table_generating' | 'table_exporting'
  // OCR Agent
  | 'ocr_processing' | 'ocr_extracting'
  // Intent & Fusion
  | 'intent_detected' | 'fusion_combining'
  // Legacy
  | 'searching';

export interface ThoughtStep {
  id: string;
  type: ThoughtType;
  title: string;
  content: string;
  agent?: string;
  timestamp?: string;
  progress?: number;
  data?: {
    query?: string;      // SQL query
    tables?: string[];   // SQL tables
    rowCount?: number;   // SQL row count
    documents?: string[]; // RAG documents
    chunks?: number;     // RAG chunks count
    url?: string;        // Web URL
    domain?: string;     // Web domain
    confidence?: number; // Score de confiance
    [key: string]: any;
  };
}

export interface ChainOfThoughtProps {
  steps: ThoughtStep[];
  isStreaming?: boolean;
  startTime?: number;
  className?: string;
}

// === Configuration des agents ===
const AGENT_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  sql_agent: {
    icon: '🗄️',
    label: 'SQL',
    color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
  },
  rag_agent: {
    icon: '📄',
    label: 'Documents',
    color: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20'
  },
  web_agent: {
    icon: '🌐',
    label: 'Web',
    color: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20'
  },
  legal_agent: {
    icon: '⚖️',
    label: 'Juridique',
    color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
  },
  email_agent: {
    icon: '📧',
    label: 'Email',
    color: 'bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/20'
  },
  workflow_agent: {
    icon: '⚡',
    label: 'N8N',
    color: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20'
  },
  digest_agent: {
    icon: '📊',
    label: 'Digest',
    color: 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20'
  },
  table_agent: {
    icon: '📋',
    label: 'Tableau',
    color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
  },
  ocr_agent: {
    icon: '👁️',
    label: 'OCR',
    color: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20'
  },
  orchestrator: {
    icon: '🎯',
    label: 'Orchestrateur',
    color: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20'
  },
  intent_classifier: {
    icon: '🧭',
    label: 'Classification',
    color: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20'
  },
  fusion_agent: {
    icon: '🔀',
    label: 'Fusion',
    color: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
  },
  system: {
    icon: '⚙️',
    label: 'Système',
    color: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20'
  }
};

// === Mapping type -> agent ===
const getAgentFromType = (type: ThoughtType, agent?: string): string => {
  if (agent) {
    const normalized = agent.toLowerCase().replace(/\s+/g, '_');
    if (AGENT_CONFIG[normalized]) return normalized;
  }

  // Inférer l'agent depuis le type
  if (type.startsWith('sql_')) return 'sql_agent';
  if (type.startsWith('rag_')) return 'rag_agent';
  if (type.startsWith('web_')) return 'web_agent';
  if (type.startsWith('legal_')) return 'legal_agent';
  if (type.startsWith('email_')) return 'email_agent';
  if (type.startsWith('workflow_')) return 'workflow_agent';
  if (type.startsWith('digest_')) return 'digest_agent';
  if (type.startsWith('table_')) return 'table_agent';
  if (type.startsWith('ocr_')) return 'ocr_agent';
  if (type === 'intent_detected' || type === 'classifying') return 'intent_classifier';
  if (type === 'fusion_combining') return 'fusion_agent';

  return 'orchestrator';
};

const getAgentConfig = (type: ThoughtType, agent?: string) => {
  const agentKey = getAgentFromType(type, agent);
  return AGENT_CONFIG[agentKey] || AGENT_CONFIG.system;
};

// === Composant principal ===
export const ChainOfThought: React.FC<ChainOfThoughtProps> = ({
  steps,
  isStreaming = false,
  startTime,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculer le temps écoulé
  useEffect(() => {
    if (!startTime) return;

    const updateTime = () => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  }, [startTime, isStreaming]);

  // Auto-collapse quand terminé
  useEffect(() => {
    if (!isStreaming && steps.length > 0) {
      const timer = setTimeout(() => {
        setIsExpanded(false);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, steps.length]);

  // Auto-scroll vers le bas pendant le streaming
  useEffect(() => {
    if (isStreaming && containerRef.current && isExpanded) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [steps, isStreaming, isExpanded]);

  if (steps.length === 0) return null;

  const isCompleted = !isStreaming;
  const displayTime = elapsedTime || Math.floor((Date.now() - (startTime || Date.now())) / 1000);

  return (
    <div className={`my-3 ${className}`}>
      {/* Header collapsed - Style DeepSeek */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-all duration-200 group"
      >
        {/* Icône cerveau avec animation */}
        <motion.div
          animate={isStreaming ? { scale: [1, 1.1, 1] } : {}}
          transition={{ duration: 1.5, repeat: isStreaming ? Infinity : 0 }}
          className="flex items-center justify-center w-5 h-5"
        >
          <Brain className={`w-4 h-4 ${isStreaming ? 'text-primary' : 'text-muted-foreground'}`} />
        </motion.div>

        {/* Texte "Réfléchi pendant X secondes" */}
        <span className="text-[13px]">
          {isStreaming ? (
            <>Réflexion en cours...</>
          ) : (
            <>Réfléchi pendant {displayTime} seconde{displayTime > 1 ? 's' : ''}</>
          )}
        </span>

        {/* Chevron */}
        <motion.div
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronRight className="w-4 h-4" />
        </motion.div>

        {/* Indicateur de streaming */}
        {isStreaming && (
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-2 h-2 rounded-full bg-primary"
          />
        )}
      </button>

      {/* Contenu expandable */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div
              ref={containerRef}
              className="mt-2 pl-2 border-l-2 border-muted/50 space-y-1 max-h-[400px] overflow-y-auto"
            >
              {steps.map((step, index) => (
                <ThoughtStepItem
                  key={step.id}
                  step={step}
                  isLast={index === steps.length - 1}
                  isStreaming={isStreaming && index === steps.length - 1}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// === Composant pour une étape ===
interface ThoughtStepItemProps {
  step: ThoughtStep;
  isLast: boolean;
  isStreaming: boolean;
}

const ThoughtStepItem: React.FC<ThoughtStepItemProps> = ({ step, isLast, isStreaming }) => {
  const [isDetailExpanded, setIsDetailExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const agentConfig = getAgentConfig(step.type, step.agent);

  const hasExpandableContent = step.data?.query || step.data?.documents?.length;

  const handleCopy = () => {
    const text = step.data?.query || step.content;
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success('Copié dans le presse-papier');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="group py-1"
    >
      <div className="flex items-start gap-2">
        {/* Badge agent */}
        <span
          className={`flex-shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${agentConfig.color}`}
        >
          <span>{agentConfig.icon}</span>
          <span className="uppercase tracking-wide">{agentConfig.label}</span>
        </span>

        {/* Contenu principal */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {/* Titre/Contenu */}
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              {step.title || step.content}
            </p>

            {/* Indicateur de streaming sur le dernier élément */}
            {isStreaming && isLast && (
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1, repeat: Infinity }}
                className="inline-block w-1.5 h-4 bg-primary/60 rounded-sm"
              />
            )}
          </div>

          {/* Détails expandables (SQL query, documents) */}
          {hasExpandableContent && (
            <div className="mt-1">
              <button
                onClick={() => setIsDetailExpanded(!isDetailExpanded)}
                className="flex items-center gap-1 text-[11px] text-muted-foreground/70 hover:text-muted-foreground transition-colors"
              >
                {isDetailExpanded ? (
                  <ChevronDown className="w-3 h-3" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
                <span>
                  {step.data?.query ? 'Voir la requête SQL' : `${step.data?.documents?.length} document(s)`}
                </span>
              </button>

              <AnimatePresence>
                {isDetailExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    {/* Requête SQL */}
                    {step.data?.query && (
                      <div className="mt-2 relative group/code">
                        <pre className="text-[11px] bg-slate-900 text-slate-100 p-3 rounded-md overflow-x-auto font-mono">
                          <code>{step.data.query}</code>
                        </pre>
                        <button
                          onClick={handleCopy}
                          className="absolute top-2 right-2 p-1 rounded bg-slate-700 hover:bg-slate-600 opacity-0 group-hover/code:opacity-100 transition-opacity"
                        >
                          {copied ? (
                            <Check className="w-3 h-3 text-green-400" />
                          ) : (
                            <Copy className="w-3 h-3 text-slate-300" />
                          )}
                        </button>
                      </div>
                    )}

                    {/* Documents RAG */}
                    {step.data?.documents && step.data.documents.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {step.data.documents.map((doc, i) => (
                          <div
                            key={i}
                            className="text-[11px] text-muted-foreground/80 flex items-center gap-1"
                          >
                            <span className="text-purple-500">📄</span>
                            <span>{doc}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* URL Web */}
                    {step.data?.url && (
                      <div className="mt-2 text-[11px] text-green-600 dark:text-green-400 flex items-center gap-1">
                        <span>🔗</span>
                        <span className="font-mono truncate">{step.data.domain || step.data.url}</span>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Métadonnées inline (row count, confidence, etc.) */}
          {(step.data?.rowCount !== undefined || step.data?.chunks !== undefined || step.data?.confidence !== undefined) && (
            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground/60">
              {step.data?.rowCount !== undefined && (
                <span>{step.data.rowCount} résultat{step.data.rowCount > 1 ? 's' : ''}</span>
              )}
              {step.data?.chunks !== undefined && (
                <span>{step.data.chunks} passage{step.data.chunks > 1 ? 's' : ''}</span>
              )}
              {step.data?.confidence !== undefined && (
                <span>{Math.round(step.data.confidence * 100)}% pertinence</span>
              )}
              {step.data?.tables && step.data.tables.length > 0 && (
                <span className="font-mono">
                  {step.data.tables.join(', ')}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default ChainOfThought;
