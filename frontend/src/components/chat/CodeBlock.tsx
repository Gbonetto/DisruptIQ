/**
 * CodeBlock - Code syntax highlighted avec bouton copy élégant
 * Style: Minimaliste, moderne, inspired by Linear & Vercel
 */

import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeBlockProps {
  language?: string;
  value: string;
  inline?: boolean;
}

export function CodeBlock({ language, value, inline }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Inline code (pas de syntax highlighting, juste style)
  if (inline) {
    return (
      <code className="px-1.5 py-0.5 mx-0.5 bg-gray-100 text-gray-800 rounded text-[0.9em] font-mono border border-gray-200">
        {value}
      </code>
    );
  }

  // Block code avec syntax highlighting
  return (
    <div className="group relative my-4 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header avec language badge + copy button */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <div className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          {language || 'code'}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-white rounded-md transition-all duration-200 opacity-0 group-hover:opacity-100"
          aria-label="Copier le code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-green-600" />
              <span className="text-green-600 font-medium">Copié</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copier</span>
            </>
          )}
        </button>
      </div>

      {/* Code content avec syntax highlighting */}
      <div className="overflow-x-auto">
        <SyntaxHighlighter
          language={language || 'text'}
          style={oneLight}
          customStyle={{
            margin: 0,
            padding: '1rem',
            background: '#FAFAFA',
            fontSize: '0.875rem',
            lineHeight: '1.5',
          }}
          codeTagProps={{
            style: {
              fontFamily: '"JetBrains Mono", "Fira Code", Consolas, Monaco, "Courier New", monospace',
            },
          }}
        >
          {value}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}
