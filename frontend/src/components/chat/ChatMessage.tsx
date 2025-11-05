/**
 * ChatMessage - Bubble message avec layout left/right
 * User messages: droite (blue bubble)
 * Assistant messages: gauche (white/gray bubble) avec rich content
 */

import { useState } from 'react';
import { Copy, RotateCcw, Check } from 'lucide-react';
import { motion } from 'framer-motion';
import { RichMarkdownRenderer } from './RichMarkdownRenderer';
import { SourceCitation } from './SourceCitation';
import { DataTable } from './DataTable';
import { ChainOfThoughts } from '../ChainOfThoughts';

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

interface Source {
  type: 'sql' | 'rag' | 'web';
  title: string;
  content: string;
  metadata?: any;
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  thoughts?: Thought[];
  sources?: Source[];
  table_data?: any[];
  onCopy?: () => void;
  onRegenerate?: () => void;
}

export function ChatMessage({
  role,
  content,
  timestamp,
  thoughts,
  sources,
  table_data,
  onCopy,
  onRegenerate,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [showActions, setShowActions] = useState(false);

  const handleCopy = async () => {
    if (onCopy) onCopy();
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User message (droite)
  if (role === 'user') {
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-end mb-6"
      >
        <div className="flex items-start gap-3 max-w-[70%]">
          <div className="flex-1 text-right">
            {/* Bubble user */}
            <div className="inline-block bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm shadow-sm">
              <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {content}
              </p>
            </div>

            {/* Timestamp */}
            <div className="text-xs text-gray-400 mt-1 px-2">
              {formatTime(timestamp)}
            </div>
          </div>

          {/* Avatar user */}
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
            U
          </div>
        </div>
      </motion.div>
    );
  }

  // Assistant message (gauche)
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="flex justify-start mb-6"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex items-start gap-3 max-w-[85%]">
        {/* Avatar assistant */}
        <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-600 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0 mt-1">
          AI
        </div>

        <div className="flex-1 min-w-0">
          {/* Chain of Thoughts */}
          {thoughts && thoughts.length > 0 && (
            <div className="mb-3">
              <ChainOfThoughts
                thoughts={thoughts}
                isThinking={false}
                collapsed={true}
              />
            </div>
          )}

          {/* Bubble assistant */}
          <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm shadow-sm p-4">
            {/* Rich markdown content */}
            <RichMarkdownRenderer content={content} />

            {/* Data table si présent */}
            {table_data && table_data.length > 0 && (
              <DataTable
                data={table_data}
                caption="Résultats"
                enableExport={true}
                enableSearch={true}
                enableSort={true}
              />
            )}

            {/* Sources avec style footnote */}
            {sources && sources.length > 0 && (
              <SourceCitation sources={sources} />
            )}
          </div>

          {/* Actions + Timestamp */}
          <div className="flex items-center gap-2 mt-2 px-2">
            {/* Timestamp */}
            <span className="text-xs text-gray-400">
              {formatTime(timestamp)}
            </span>

            {/* Actions (visible au hover) */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: showActions ? 1 : 0 }}
              className="flex items-center gap-1"
            >
              {/* Copy */}
              <button
                onClick={handleCopy}
                className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                title="Copier le message"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-green-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>

              {/* Regenerate */}
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                  title="Régénérer la réponse"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}
            </motion.div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// Helper: Format time
function formatTime(date: Date): string {
  return date.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}
