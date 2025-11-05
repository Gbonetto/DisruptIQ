/**
 * Chain of Thoughts Component - DeepSeek Style
 * Displays real-time AI reasoning steps with streaming
 */

import React, { useState, useEffect } from 'react';
import { Brain, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';

interface Thought {
  id: string;
  type: 'analyzing' | 'classifying' | 'planning' | 'executing' | 'processing' | 'synthesizing' | 'completed' | 'error';
  timestamp: string;
  agent?: string;
  title: string;
  content: string;
  data?: any;
  progress?: number;
}

interface ChainOfThoughtsProps {
  thoughts: Thought[];
  isThinking: boolean;
  collapsed?: boolean;
}

export const ChainOfThoughts: React.FC<ChainOfThoughtsProps> = ({
  thoughts,
  isThinking,
  collapsed = false
}) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);

  // Auto-expand when new thoughts arrive
  useEffect(() => {
    if (thoughts.length > 0 && isThinking) {
      setIsCollapsed(false);
    }
  }, [thoughts.length, isThinking]);

  const getThoughtIcon = (type: Thought['type']) => {
    switch (type) {
      case 'analyzing':
        return <Brain className="h-4 w-4 text-neon-violet animate-pulse" />;
      case 'classifying':
        return <Brain className="h-4 w-4 text-neon-cyan animate-pulse" />;
      case 'planning':
        return <Brain className="h-4 w-4 text-neon-violet animate-pulse" />;
      case 'executing':
        return <Loader2 className="h-4 w-4 text-neon-pink animate-spin" />;
      case 'processing':
        return <Loader2 className="h-4 w-4 text-neon-green animate-spin" />;
      case 'synthesizing':
        return <Brain className="h-4 w-4 text-neon-green animate-pulse" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-neon-green" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-neon-pink" />;
      default:
        return <Brain className="h-4 w-4 text-gray-500" />;
    }
  };

  const getThoughtColor = (type: Thought['type']) => {
    switch (type) {
      case 'analyzing': return 'border-l-neon-violet bg-retro-gray/50';
      case 'classifying': return 'border-l-neon-cyan bg-retro-gray/50';
      case 'planning': return 'border-l-neon-violet bg-retro-gray/50';
      case 'executing': return 'border-l-neon-pink bg-retro-gray/50';
      case 'processing': return 'border-l-neon-green bg-retro-gray/50';
      case 'synthesizing': return 'border-l-neon-green bg-retro-gray/50';
      case 'completed': return 'border-l-neon-green bg-retro-gray/50';
      case 'error': return 'border-l-neon-pink bg-retro-gray/50';
      default: return 'border-l-gray-500 bg-retro-gray/50';
    }
  };

  const getAgentBadgeColor = (agent?: string) => {
    if (!agent) return 'bg-retro-gray/50 text-gray-400 border border-gray-600';

    const colors: Record<string, string> = {
      'orchestrator': 'bg-neon-violet/20 text-neon-violet border border-neon-violet/50',
      'sql_agent': 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50',
      'email_agent': 'bg-neon-green/20 text-neon-green border border-neon-green/50',
      'rag_agent': 'bg-neon-pink/20 text-neon-pink border border-neon-pink/50',
      'workflow_agent': 'bg-neon-violet/20 text-neon-violet border border-neon-violet/50',
      'template_agent': 'bg-neon-pink/20 text-neon-pink border border-neon-pink/50',
    };

    return colors[agent] || 'bg-retro-gray/50 text-gray-400 border border-gray-600';
  };

  if (thoughts.length === 0 && !isThinking) {
    return null;
  }

  return (
    <Card className="mb-4 overflow-hidden border-2 border-neon-violet/50 bg-retro-gray neon-border-violet pixel-corners">
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 bg-retro-gray/80 border-b border-neon-violet/30 cursor-pointer hover:bg-retro-gray transition-colors"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2">
          <Brain className={`h-5 w-5 text-neon-violet ${isThinking ? 'animate-pulse' : ''}`} />
          <span className="font-semibold text-white font-pixel text-sm">
            {isThinking ? 'Réflexion en cours...' : 'Chaîne de pensée'}
          </span>
            {thoughts.length > 0 && (
              <Badge variant="outline" className="ml-2 bg-neon-violet/20 text-neon-violet border-neon-violet/50 pixel-border-sm">
                {thoughts.length} étape{thoughts.length > 1 ? 's' : ''}
              </Badge>
            )}
        </div>

        <Button variant="ghost" size="sm" className="text-gray-400 hover:text-neon-cyan hover:bg-retro-dark">
          {isCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </Button>
      </div>

      {/* Thoughts List */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
              {thoughts.map((thought, index) => (
                <motion.div
                  key={thought.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className={`border-l-4 rounded-r-lg p-3 ${getThoughtColor(thought.type)}`}
                >
                  {/* Thought Header */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getThoughtIcon(thought.type)}
                      <span className="font-medium text-sm text-white">
                        {thought.title}
                      </span>
                      {thought.agent && (
                        <Badge className={`text-xs font-pixel ${getAgentBadgeColor(thought.agent)}`}>
                          {thought.agent.replace('_', ' ')}
                        </Badge>
                      )}
                    </div>

                    {thought.progress !== undefined && thought.progress < 1 && (
                      <span className="text-xs text-neon-cyan font-pixel">
                        {Math.round(thought.progress * 100)}%
                      </span>
                    )}
                  </div>

                  {/* Thought Content */}
                  <div className="text-sm text-gray-300 whitespace-pre-wrap ml-6">
                    {thought.content}
                  </div>

                  {/* Progress Bar */}
                  {thought.progress !== undefined && thought.progress < 1 && (
                    <div className="mt-2 ml-6 h-1 bg-retro-dark rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-neon-violet animate-neon-pulse"
                        initial={{ width: 0 }}
                        animate={{ width: `${thought.progress * 100}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  )}

                  {/* Additional Data (if any) */}
                  {thought.data && typeof thought.data === 'object' && Object.keys(thought.data).length > 0 && (
                    <details className="mt-2 ml-6">
                      <summary className="text-xs text-gray-400 cursor-pointer hover:text-neon-cyan transition-colors font-pixel">
                        Détails techniques
                      </summary>
                      <pre className="mt-2 text-xs bg-retro-dark text-neon-green p-2 rounded border border-neon-green/30 overflow-x-auto">
                        {JSON.stringify(thought.data, null, 2)}
                      </pre>
                    </details>
                  )}

                  {/* Timestamp */}
                  <div className="text-xs text-gray-500 mt-2 ml-6 font-pixel">
                    {new Date(thought.timestamp).toLocaleTimeString('fr-FR')}
                  </div>
                </motion.div>
              ))}

              {/* Thinking Indicator */}
              {isThinking && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-sm text-neon-cyan ml-6 font-pixel"
                >
                  <Loader2 className="h-4 w-4 animate-spin text-neon-cyan" />
                  <span>Traitement en cours...</span>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
};

export default ChainOfThoughts;
