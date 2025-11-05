/**
 * ChatInput - Zone de saisie avec textarea auto-expand
 * Style: Moderne, minimaliste, inspiré Claude.ai/ChatGPT
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
  maxRows?: number;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = 'Posez votre question...',
  maxRows = 5,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [rows, setRows] = useState(1);

  // Auto-resize textarea
  useEffect(() => {
    if (!textareaRef.current) return;

    textareaRef.current.style.height = 'auto';
    const scrollHeight = textareaRef.current.scrollHeight;
    const lineHeight = 24; // Approximatif
    const newRows = Math.min(Math.ceil(scrollHeight / lineHeight), maxRows);
    setRows(newRows);
  }, [value, maxRows]);

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sans Shift = Submit
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled && !isStreaming) {
        onSubmit();
      }
    }
  };

  const canSend = value.trim().length > 0 && !disabled && !isStreaming;

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative flex items-end gap-2">
          {/* Textarea avec auto-expand */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder={placeholder}
              rows={rows}
              className={`
                w-full resize-none
                px-4 py-3
                bg-gray-50 border border-gray-300
                rounded-xl
                text-sm text-gray-900 placeholder-gray-500
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                transition-colors
                ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              style={{
                minHeight: '48px',
                maxHeight: `${maxRows * 24 + 24}px`,
              }}
            />

            {/* Hint pour Enter/Shift+Enter */}
            <div className="absolute bottom-1 right-2 text-xs text-gray-400 pointer-events-none">
              {!isStreaming && (
                <span>
                  <kbd className="px-1 py-0.5 bg-gray-200 rounded text-gray-600">Enter</kbd> pour envoyer
                </span>
              )}
            </div>
          </div>

          {/* Bouton Send/Stop */}
          {isStreaming ? (
            // Stop button (pendant streaming)
            <button
              onClick={onStop}
              className="flex-shrink-0 w-12 h-12 flex items-center justify-center bg-red-600 hover:bg-red-700 text-white rounded-xl transition-colors shadow-sm"
              title="Arrêter la génération"
            >
              <Square className="w-5 h-5" />
            </button>
          ) : (
            // Send button
            <button
              onClick={onSubmit}
              disabled={!canSend}
              className={`
                flex-shrink-0 w-12 h-12
                flex items-center justify-center
                rounded-xl
                transition-all
                shadow-sm
                ${
                  canSend
                    ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }
              `}
              title="Envoyer le message"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Compteur de caractères (optionnel) */}
        {value.length > 1000 && (
          <div className="text-xs text-gray-400 mt-2 text-right">
            {value.length} caractères
          </div>
        )}
      </div>
    </div>
  );
}
