import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface RichMarkdownProps {
  content: string;
  className?: string;
}

export const RichMarkdown: React.FC<RichMarkdownProps> = ({ content, className = '' }) => {
  return (
    <div className={`prose prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
        // Headings with elegant styling
        h1: ({ node, ...props }) => (
          <h1 className="text-2xl font-bold text-foreground mt-6 mb-4 pb-2 border-b border-border" {...props} />
        ),
        h2: ({ node, ...props }) => (
          <h2 className="text-xl font-semibold text-foreground mt-5 mb-3 flex items-center gap-2" {...props}>
            <span className="w-1 h-6 bg-primary rounded-full" />
            {props.children}
          </h2>
        ),
        h3: ({ node, ...props }) => (
          <h3 className="text-lg font-semibold text-foreground mt-4 mb-2" {...props} />
        ),
        h4: ({ node, ...props }) => (
          <h4 className="text-base font-semibold text-foreground mt-3 mb-2" {...props} />
        ),

        // Paragraphs
        p: ({ node, ...props }) => (
          <p className="text-sm leading-relaxed text-foreground mb-3" {...props} />
        ),

        // Lists with better spacing
        ul: ({ node, ...props }) => (
          <ul className="list-disc list-inside space-y-1 mb-3 text-foreground" {...props} />
        ),
        ol: ({ node, ...props }) => (
          <ol className="list-decimal list-inside space-y-1 mb-3 text-foreground" {...props} />
        ),
        li: ({ node, ...props }) => (
          <li className="text-sm leading-relaxed ml-2" {...props} />
        ),

        // Blockquotes with accent
        blockquote: ({ node, ...props }) => (
          <blockquote
            className="border-l-4 border-primary bg-primary/5 pl-4 py-2 my-3 italic text-muted-foreground"
            {...props}
          />
        ),

        // Code blocks with syntax highlighting
        code: ({ node, inline, className, children, ...props }: any) => {
          const match = /language-(\w+)/.exec(className || '');
          return !inline && match ? (
            <div className="my-3 rounded-lg overflow-hidden border border-border">
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                className="text-xs"
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            </div>
          ) : (
            <code
              className="px-1.5 py-0.5 rounded bg-secondary text-primary font-mono text-xs"
              {...props}
            >
              {children}
            </code>
          );
        },

        // Tables with smooth scroll for overflow
        table: ({ node, ...props }) => (
          <div className="my-4 overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full divide-y divide-border" {...props} />
          </div>
        ),
        thead: ({ node, ...props }) => (
          <thead className="bg-secondary/50" {...props} />
        ),
        tbody: ({ node, ...props }) => (
          <tbody className="divide-y divide-border bg-background" {...props} />
        ),
        tr: ({ node, ...props }) => (
          <tr className="hover:bg-secondary/30 transition-colors" {...props} />
        ),
        th: ({ node, ...props }) => (
          <th
            className="px-4 py-2 text-left text-xs font-semibold text-foreground uppercase tracking-wider"
            {...props}
          />
        ),
        td: ({ node, ...props }) => (
          <td className="px-4 py-2 text-sm text-foreground" {...props} />
        ),

        // Links with hover effect
        a: ({ node, ...props }) => (
          <a
            className="text-primary hover:text-primary/80 underline underline-offset-2 transition-colors"
            target="_blank"
            rel="noopener noreferrer"
            {...props}
          />
        ),

        // Horizontal rules
        hr: ({ node, ...props }) => (
          <hr className="my-6 border-border" {...props} />
        ),

        // Strong and emphasis
        strong: ({ node, ...props }) => (
          <strong className="font-semibold text-foreground" {...props} />
        ),
        em: ({ node, ...props }) => (
          <em className="italic text-muted-foreground" {...props} />
        ),
      }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
