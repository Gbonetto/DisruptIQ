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
        return <Brain className="h-4 w-4 text-purple-500 animate-pulse" />;
      case 'classifying':
        return <Brain className="h-4 w-4 text-blue-500 animate-pulse" />;
      case 'planning':
        return <Brain className="h-4 w-4 text-indigo-500 animate-pulse" />;
      case 'executing':
        return <Loader2 className="h-4 w-4 text-orange-500 animate-spin" />;
      case 'processing':
        return <Loader2 className="h-4 w-4 text-yellow-500 animate-spin" />;
      case 'synthesizing':
        return <Brain className="h-4 w-4 text-green-500 animate-pulse" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Brain className="h-4 w-4 text-gray-500" />;
    }
  };

  const getThoughtColor = (type: Thought['type']) => {
    switch (type) {
      case 'analyzing': return 'border-l-purple-500 bg-purple-50';
      case 'classifying': return 'border-l-blue-500 bg-blue-50';
      case 'planning': return 'border-l-indigo-500 bg-indigo-50';
      case 'executing': return 'border-l-orange-500 bg-orange-50';
      case 'processing': return 'border-l-yellow-500 bg-yellow-50';
      case 'synthesizing': return 'border-l-green-500 bg-green-50';
      case 'completed': return 'border-l-green-600 bg-green-50';
      case 'error': return 'border-l-red-600 bg-red-50';
      default: return 'border-l-gray-500 bg-gray-50';
    }
  };

  const getAgentBadgeColor = (agent?: string) => {
    if (!agent) return 'bg-gray-100 text-gray-700';

    const colors: Record<string, string> = {
      'orchestrator': 'bg-purple-100 text-purple-700',
      'sql_agent': 'bg-blue-100 text-blue-700',
      'email_agent': 'bg-green-100 text-green-700',
      'rag_agent': 'bg-yellow-100 text-yellow-700',
      'workflow_agent': 'bg-orange-100 text-orange-700',
      'template_agent': 'bg-pink-100 text-pink-700',
    };

    return colors[agent] || 'bg-gray-100 text-gray-700';
  };

  if (thoughts.length === 0 && !isThinking) {
    return null;
  }

  return (
    <Card className="mb-4 overflow-hidden border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-blue-50">
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 bg-white border-b cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2">
          <Brain className={`h-5 w-5 text-purple-600 ${isThinking ? 'animate-pulse' : ''}`} />
          <span className="font-semibold text-gray-900">
            {isThinking ? 'Réflexion en cours...' : 'Chaîne de pensée'}
          </span>
            {thoughts.length > 0 && (
              <Badge variant="outline" className="ml-2">
                {thoughts.length} étape{thoughts.length > 1 ? 's' : ''}
              </Badge>
            )}
        </div>

        <Button variant="ghost" size="sm">
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
                      <span className="font-medium text-sm text-gray-900">
                        {thought.title}
                      </span>
                      {thought.agent && (
                        <Badge className={`text-xs ${getAgentBadgeColor(thought.agent)}`}>
                          {thought.agent.replace('_', ' ')}
                        </Badge>
                      )}
                    </div>

                    {thought.progress !== undefined && thought.progress < 1 && (
                      <span className="text-xs text-gray-500">
                        {Math.round(thought.progress * 100)}%
                      </span>
                    )}
                  </div>

                  {/* Thought Content */}
                  <div className="text-sm text-gray-700 whitespace-pre-wrap ml-6">
                    {thought.content}
                  </div>

                  {/* Progress Bar */}
                  {thought.progress !== undefined && thought.progress < 1 && (
                    <div className="mt-2 ml-6 h-1 bg-gray-200 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-purple-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${thought.progress * 100}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  )}

                  {/* Additional Data (if any) */}
                  {thought.data && Object.keys(thought.data).length > 0 && (
                    <details className="mt-2 ml-6">
                      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                        Détails techniques
                      </summary>
                      <pre className="mt-2 text-xs bg-white p-2 rounded border overflow-x-auto">
                        {JSON.stringify(thought.data, null, 2)}
                      </pre>
                    </details>
                  )}

                  {/* Timestamp */}
                  <div className="text-xs text-gray-400 mt-2 ml-6">
                    {new Date(thought.timestamp).toLocaleTimeString('fr-FR')}
                  </div>
                </motion.div>
              ))}

              {/* Thinking Indicator */}
              {isThinking && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-sm text-gray-500 ml-6"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
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
