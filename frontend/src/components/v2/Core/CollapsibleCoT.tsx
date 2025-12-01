import React, { useState, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

export interface CoTStep {
  id: string;
  title: string;
  content: string;
  status: 'pending' | 'active' | 'completed';
  timestamp?: string;
  type?: string;
  agent?: string;
}

// Agent badge configuration
const agentConfig = {
  sql_agent: {
    icon: '🗄️',
    label: 'SQL',
    color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800'
  },
  rag_agent: {
    icon: '📄',
    label: 'RAG',
    color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'
  },
  web_agent: {
    icon: '🌐',
    label: 'Web',
    color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800'
  },
  orchestrator: {
    icon: '🎯',
    label: 'Orchestrator',
    color: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700'
  },
  system: {
    icon: '⚙️',
    label: 'System',
    color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
  },
};

const getAgentBadge = (agentName?: string) => {
  if (!agentName) return agentConfig.system;

  // Normalize agent name
  const normalized = agentName.toLowerCase().replace(/\s+/g, '_');

  // Return matching config or default
  return agentConfig[normalized as keyof typeof agentConfig] || agentConfig.system;
};

export interface CollapsibleCoTProps {
  steps: CoTStep[];
  isCollapsed?: boolean;
  onToggle?: () => void;
  autoCollapse?: boolean; // DeepSeek style: auto-collapse when all completed
}

// Hook pour l'effet typewriter avec fade-in progressif
function useTypewriter(text: string, speed: number = 20) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    if (!text) {
      setDisplayedText('');
      setIsComplete(false);
      setOpacity(0);
      return;
    }

    let currentIndex = 0;
    setDisplayedText('');
    setIsComplete(false);
    setOpacity(0);

    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText(text.slice(0, currentIndex + 1));
        // Augmentation progressive de l'opacité
        setOpacity(Math.min(1, 0.4 + (currentIndex / text.length) * 0.6));
        currentIndex++;
      } else {
        setIsComplete(true);
        setOpacity(1);
        clearInterval(interval);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed]);

  return { displayedText, isComplete, opacity };
}

export const CollapsibleCoT: React.FC<CollapsibleCoTProps> = ({
  steps: rawSteps,
  isCollapsed: controlledCollapsed,
  onToggle,
  autoCollapse = true, // Default to DeepSeek behavior
}) => {
  // Ensure steps is always a valid array (before any hooks)
  const steps = Array.isArray(rawSteps) ? rawSteps : [];

  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0); // Combien de steps sont visibles
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [copiedStepId, setCopiedStepId] = useState<string | null>(null);

  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;

  const handleToggle = () => {
    if (onToggle) {
      onToggle();
    } else {
      setInternalCollapsed(!internalCollapsed);
    }
  };

  const toggleStepExpand = (stepId: string) => {
    setExpandedSteps(prev => {
      const newSet = new Set(prev);
      if (newSet.has(stepId)) {
        newSet.delete(stepId);
      } else {
        newSet.add(stepId);
      }
      return newSet;
    });
  };

  const copyStepToClipboard = (step: CoTStep) => {
    const text = `[${step.agent || 'system'}] ${step.title}\n${step.content}`;
    navigator.clipboard.writeText(text);
    setCopiedStepId(step.id);
    toast.success('Copié dans le presse-papier');
    setTimeout(() => setCopiedStepId(null), 2000);
  };

  // Check if this is a saved message (all completed) vs live streaming
  const allCompleted = steps.length > 0 && steps.every(s => s.status === 'completed');
  const isLiveStreaming = !allCompleted;

  // For saved messages, show all steps immediately. For live streaming, show sequentially
  useEffect(() => {
    const totalSteps = steps.filter(s => s.status !== 'pending').length;

    if (allCompleted && visibleCount !== totalSteps) {
      // Saved message: show all immediately
      setVisibleCount(totalSteps);
    } else if (isLiveStreaming && visibleCount < totalSteps) {
      // Live streaming: show sequentially with animation
      const lastVisibleStep = steps.filter(s => s.status !== 'pending')[visibleCount - 1];
      const estimatedDuration = lastVisibleStep ? lastVisibleStep.title.length * 15 + 300 : 0;

      const timer = setTimeout(() => {
        setVisibleCount(prev => prev + 1);
      }, estimatedDuration);

      return () => clearTimeout(timer);
    }
  }, [steps, visibleCount, allCompleted, isLiveStreaming]);

  const hasActiveStep = steps.some(s => s.status === 'active');

  // DeepSeek style: Auto-collapse when all completed (after 500ms delay)
  useEffect(() => {
    if (autoCollapse && allCompleted && !internalCollapsed && controlledCollapsed === undefined) {
      const timer = setTimeout(() => {
        setInternalCollapsed(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [autoCollapse, allCompleted, internalCollapsed, controlledCollapsed]);

  if (steps.length === 0 || steps.every(s => s.status === 'pending')) {
    return null;
  }

  const completedCount = steps.filter(s => s.status === 'completed').length;

  // Count agent usage for collapsed header
  const agentCounts = steps.reduce((acc, step) => {
    const badge = getAgentBadge(step.agent);
    const key = badge.label;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const agentSummary = Object.entries(agentCounts)
    .filter(([label]) => label !== 'System' && label !== 'Orchestrator')
    .map(([label, count]) => {
      const config = Object.values(agentConfig).find(c => c.label === label);
      return config ? `${config.icon} ${count}` : null;
    })
    .filter(Boolean)
    .join(' • ');

  return (
    <div className="my-3 font-sans text-sm">
      {/* Collapsible header - DeepSeek style */}
      {isCollapsed ? (
        <button
          onClick={handleToggle}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted/50"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="flex items-center gap-1.5">
            💭 Raisonnement ({completedCount} étape{completedCount > 1 ? 's' : ''})
            {agentSummary && (
              <>
                <span className="text-muted-foreground/50">•</span>
                <span className="text-[10px]">{agentSummary}</span>
              </>
            )}
          </span>
        </button>
      ) : (
        <>
          {/* Expanded thoughts */}
          <div className="space-y-1">
            {steps
              .filter(s => s.status !== 'pending')
              .slice(0, visibleCount)
              .map((step, index, visibleArray) => {
                const shouldAnimate = index === visibleArray.length - 1;
                return (
                  <StepItem
                    key={step.id}
                    step={step}
                    isExpanded={expandedSteps.has(step.id)}
                    onToggleExpand={() => toggleStepExpand(step.id)}
                    onCopy={() => copyStepToClipboard(step)}
                    isCopied={copiedStepId === step.id}
                    shouldAnimate={shouldAnimate}
                  />
                );
              })}
          </div>
          {/* Collapse button - shown when all completed */}
          {allCompleted && (
            <button
              onClick={handleToggle}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mt-1 px-2 py-1 rounded hover:bg-muted/50"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              <span>Masquer le raisonnement</span>
            </button>
          )}
        </>
      )}
    </div>
  );
};

// Composant pour chaque étape - Enhanced avec typewriter séquentiel
const StepItem: React.FC<{
  step: CoTStep;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onCopy: () => void;
  isCopied: boolean;
  shouldAnimate: boolean; // New prop to control when to animate
}> = ({ step, isExpanded, onToggleExpand, onCopy, isCopied, shouldAnimate }) => {
  const [hasAnimated, setHasAnimated] = useState(false);
  const [finalText, setFinalText] = useState('');
  const [animationStarted, setAnimationStarted] = useState(false);

  // If step is already completed (saved message), skip animation entirely
  const isSavedMessage = step.status === 'completed' && !shouldAnimate;

  // Start animation ONCE when shouldAnimate becomes true
  useEffect(() => {
    if (shouldAnimate && !animationStarted && !isSavedMessage) {
      setAnimationStarted(true);
    }
  }, [shouldAnimate, animationStarted, isSavedMessage]);

  // Animate only if animation was started and not yet completed, and not a saved message
  const textToAnimate = animationStarted && !hasAnimated && !isSavedMessage ? step.title : '';

  const { displayedText, isComplete, opacity } = useTypewriter(
    textToAnimate,
    15 // Faster typewriter for better UX
  );

  // Save final text when animation completes
  useEffect(() => {
    if (isComplete && animationStarted && !hasAnimated) {
      setHasAnimated(true);
      setFinalText(step.title);
    }
  }, [isComplete, hasAnimated, step.title, animationStarted]);

  // Icon mapping for different step types
  const getIcon = () => {
    if (step.status === 'completed') return '✓';
    if (step.status === 'active') return '→';
    if (step.type === 'error') return '⚠';
    return '•';
  };

  // For saved messages, show text immediately. Otherwise use animated text
  const textToShow = isSavedMessage ? step.title : (hasAnimated ? finalText : displayedText);

  const agentBadge = getAgentBadge(step.agent);

  return (
    <div
      className="group relative py-1 transition-opacity duration-200"
      style={{ opacity: isSavedMessage ? 1 : (shouldAnimate && !hasAnimated ? opacity : 1) }}
    >
      <div className="flex items-start gap-2">
        {/* Agent badge - left indicator */}
        <span
          className={`flex-shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium border ${agentBadge.color} transition-all hover:scale-105`}
          title={`${agentBadge.label} Agent`}
        >
          <span className="text-[10px]">{agentBadge.icon}</span>
          <span className="uppercase tracking-wider">{agentBadge.label}</span>
        </span>

        {/* Content - Style DeepSeek Light: texte normal lisible */}
        <div className="flex-1 min-w-0">
          {/* Texte narratif style DeepSeek - pas italic, bien lisible */}
          <p className="text-[13px] text-muted-foreground/85 font-normal leading-relaxed">
            {textToShow}
            {shouldAnimate && !hasAnimated && !isSavedMessage && (
              <span className="inline-block w-0.5 h-3 bg-muted-foreground/50 ml-1 animate-pulse" />
            )}
          </p>
        </div>

        {/* Copy button - discret */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCopy();
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-1 hover:bg-muted/50 rounded flex-shrink-0"
          title="Copier"
        >
          {isCopied ? (
            <Check className="w-3 h-3 text-green-500" />
          ) : (
            <Copy className="w-3 h-3 text-muted-foreground/40" />
          )}
        </button>
      </div>
    </div>
  );
};
