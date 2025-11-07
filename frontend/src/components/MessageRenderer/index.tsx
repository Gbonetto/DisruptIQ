import React from 'react';
import ReactMarkdown from 'react-markdown';

interface MessageRendererProps {
  content: string;
  role: 'user' | 'assistant';
}

export const MessageRenderer: React.FC<MessageRendererProps> = ({ content, role }) => {
  return (
    <div
      className={`rounded-2xl px-4 py-3 ${
        role === 'user'
          ? 'bg-primary text-primary-foreground'
          : 'bg-secondary text-foreground'
      }`}
    >
      <div className="text-sm leading-relaxed prose prose-sm max-w-none">
        <ReactMarkdown>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
};
