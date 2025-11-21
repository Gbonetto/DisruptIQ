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

export interface CollapsibleCoTProps {
  steps: CoTStep[];
  isCollapsed?: boolean;
  onToggle?: () => void;
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
  steps,
  isCollapsed: controlledCollapsed,
  onToggle,
}) => {
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

  // Système ULTRA-SIMPLE d'ordre séquentiel basé sur un compteur
  // Chaque step apparaît APRÈS que le précédent ait fini son animation
  useEffect(() => {
    const totalSteps = steps.filter(s => s.status !== 'pending').length;

    // S'il y a plus de steps que ce qu'on affiche, ajouter le prochain après un délai
    if (visibleCount < totalSteps) {
      // Calculer le délai basé sur le dernier step visible
      const lastVisibleStep = steps.filter(s => s.status !== 'pending')[visibleCount - 1];
      const estimatedDuration = lastVisibleStep ? lastVisibleStep.title.length * 15 + 300 : 0;

      const timer = setTimeout(() => {
        setVisibleCount(prev => prev + 1);
      }, estimatedDuration);

      return () => clearTimeout(timer);
    }
  }, [steps, visibleCount]);

  const hasActiveStep = steps.some(s => s.status === 'active');
  const allCompleted = steps.length > 0 && steps.every(s => s.status === 'completed');

  // Ne PLUS auto-collapse - garder le header consultable après la fin
  // (supprimé pour permettre le débogage et voir que tout s'est bien passé)

  if (steps.length === 0 || steps.every(s => s.status === 'pending')) {
    return null;
  }

  return (
    <div className="my-3 font-sans text-sm">
      {/* Style DeepSeek Light: simple liste de thoughts, pas de box */}
      <div className="space-y-1">
        {steps
          .filter(s => s.status !== 'pending')
          .slice(0, visibleCount) // Afficher seulement les N premiers steps
          .map((step, index, visibleArray) => {
            // shouldAnimate = true si c'est le DERNIER step visible
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

  // Start animation ONCE when shouldAnimate becomes true
  useEffect(() => {
    if (shouldAnimate && !animationStarted) {
      setAnimationStarted(true);
    }
  }, [shouldAnimate, animationStarted]);

  // Animate only if animation was started and not yet completed
  const textToAnimate = animationStarted && !hasAnimated ? step.title : '';

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

  const textToShow = hasAnimated ? finalText : displayedText;

  return (
    <div
      className="group relative py-1 transition-opacity duration-200"
      style={{ opacity: shouldAnimate && !hasAnimated ? opacity : 1 }}
    >
      <div className="flex items-start gap-2">
        {/* Content - Style DeepSeek Light: texte normal lisible */}
        <div className="flex-1 min-w-0">
          {/* Texte narratif style DeepSeek - pas italic, bien lisible */}
          <p className="text-[13px] text-muted-foreground/85 font-normal leading-relaxed">
            {textToShow}
            {shouldAnimate && !hasAnimated && (
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
