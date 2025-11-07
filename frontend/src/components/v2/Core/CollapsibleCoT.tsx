import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

export interface CoTStep {
  id: string;
  title: string;
  content: string;
  status: 'pending' | 'active' | 'completed';
  timestamp?: string;
}

export interface CollapsibleCoTProps {
  steps: CoTStep[];
  isCollapsed?: boolean;
  onToggle?: () => void;
}

export const CollapsibleCoT: React.FC<CollapsibleCoTProps> = ({
  steps,
  isCollapsed: controlledCollapsed,
  onToggle,
}) => {
  const [internalCollapsed, setInternalCollapsed] = useState(false);

  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;

  const handleToggle = () => {
    if (onToggle) {
      onToggle();
    } else {
      setInternalCollapsed(!internalCollapsed);
    }
  };

  const completedSteps = steps.filter(s => s.status === 'completed').length;
  const progress = (completedSteps / steps.length) * 100;

  const getStatusIcon = (status: CoTStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'active':
        return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
      case 'pending':
        return <Circle className="w-4 h-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="border border-border rounded-xl bg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={handleToggle}
        className="w-full p-4 flex items-center justify-between hover:bg-accent/50 transition-colors"
      >
        <div className="flex items-center gap-3 flex-1">
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-5 h-5 text-muted-foreground" />
          )}
          <div className="text-left">
            <h3 className="text-sm font-semibold text-foreground">
              Chain of Thought
            </h3>
            <p className="text-xs text-muted-foreground">
              {completedSteps} / {steps.length} étapes complétées
            </p>
          </div>
        </div>

        {/* Progress indicator */}
        <div className="w-32">
          <Progress value={progress} className="h-2" />
        </div>
      </button>

      {/* Steps */}
      {!isCollapsed && (
        <div className="border-t border-border">
          <div className="p-4 space-y-3">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className={`
                  flex gap-3 p-3 rounded-lg transition-all
                  ${step.status === 'active' ? 'bg-primary/5 border border-primary/20' : ''}
                  ${step.status === 'completed' ? 'opacity-75' : ''}
                `}
              >
                {/* Status icon */}
                <div className="flex-shrink-0 mt-0.5">
                  {getStatusIcon(step.status)}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h4 className="text-sm font-medium text-foreground">
                      {index + 1}. {step.title}
                    </h4>
                    {step.timestamp && (
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {step.timestamp}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {step.content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
