/**
 * RichMarkdownRenderer - Rendu markdown professionnel et élégant
 * Support complet: tables, headings, blockquotes, code, listes, liens, images
 * Design: Minimaliste, moderne, haute qualité
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';
import { ExternalLink } from 'lucide-react';

interface RichMarkdownRendererProps {
  content: string;
  className?: string;
}

export function RichMarkdownRenderer({ content, className = '' }: RichMarkdownRendererProps) {
  return (
    <div className={`prose prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings avec design épuré
          h1: ({ node, ...props }) => (
            <h1 className="text-2xl font-semibold text-gray-900 mt-6 mb-4 pb-2 border-b border-gray-200" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-xl font-semibold text-gray-900 mt-5 mb-3" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2" {...props} />
          ),
          h4: ({ node, ...props }) => (
            <h4 className="text-base font-semibold text-gray-800 mt-3 mb-2" {...props} />
          ),
          h5: ({ node, ...props }) => (
            <h5 className="text-sm font-semibold text-gray-700 mt-2 mb-1" {...props} />
          ),
          h6: ({ node, ...props }) => (
            <h6 className="text-sm font-medium text-gray-600 mt-2 mb-1" {...props} />
          ),

          // Paragraphes avec espacement cohérent
          p: ({ node, ...props }) => (
            <p className="text-gray-900 leading-relaxed mb-4" {...props} />
          ),

          // Liens avec icône externe et hover élégant
          a: ({ node, href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 hover:underline inline-flex items-center gap-1 transition-colors"
              {...props}
            >
              {children}
              {href?.startsWith('http') && <ExternalLink className="w-3 h-3 inline opacity-60" />}
            </a>
          ),

          // Code inline et blocks avec syntax highlighting
          code: ({ inline, className, children }: any) => {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : undefined;
            const value = String(children).replace(/\n$/, '');

            return (
              <CodeBlock
                language={language}
                value={value}
                inline={inline}
              />
            );
          },

          // Listes ordonnées
          ol: ({ node, ...props }) => (
            <ol className="list-decimal list-outside ml-6 space-y-2 my-4 text-gray-900" {...props} />
          ),

          // Listes non-ordonnées
          ul: ({ node, ...props }) => (
            <ul className="list-disc list-outside ml-6 space-y-2 my-4 text-gray-900" {...props} />
          ),

          // Items de liste
          li: ({ node, ...props }) => (
            <li className="pl-2" {...props} />
          ),

          // Blockquotes style élégant
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-4 border-blue-500 bg-blue-50 pl-4 pr-4 py-3 my-4 italic text-gray-700 rounded-r-md"
              {...props}
            />
          ),

          // Tableaux style minimaliste
          table: ({ node, ...props }) => (
            <div className="my-6 overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
              <table className="min-w-full divide-y divide-gray-200" {...props} />
            </div>
          ),

          // Header de tableau
          thead: ({ node, ...props }) => (
            <thead className="bg-gray-50" {...props} />
          ),

          // Body de tableau
          tbody: ({ node, ...props }) => (
            <tbody className="bg-white divide-y divide-gray-200" {...props} />
          ),

          // Rows de tableau
          tr: ({ node, ...props }) => (
            <tr className="hover:bg-gray-50 transition-colors" {...props} />
          ),

          // Cellules header
          th: ({ node, ...props }) => (
            <th
              className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
              {...props}
            />
          ),

          // Cellules data
          td: ({ node, ...props }) => (
            <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap" {...props} />
          ),

          // Ligne horizontale
          hr: ({ node, ...props }) => (
            <hr className="my-6 border-t border-gray-200" {...props} />
          ),

          // Strong (gras)
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-gray-900" {...props} />
          ),

          // Emphasis (italique)
          em: ({ node, ...props }) => (
            <em className="italic text-gray-800" {...props} />
          ),

          // Strikethrough (barré)
          del: ({ node, ...props }) => (
            <del className="line-through text-gray-500" {...props} />
          ),

          // Images avec style responsive
          img: ({ node, alt, src, ...props }) => (
            <img
              src={src}
              alt={alt || ''}
              className="rounded-lg shadow-md max-w-full h-auto my-4"
              {...props}
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
