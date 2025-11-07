import React, { useState } from 'react';
import { X, FileText, Database } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RAGTab } from '@/components/DocumentPanel/RAGTab';
import { SQLTab } from '@/components/DocumentPanel/SQLTab';

interface RightPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'rag' | 'sql';

export const RightPanel: React.FC<RightPanelProps> = ({
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('rag');

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop for mobile */}
      <div
        className="fixed inset-0 bg-black/20 z-40 lg:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <aside className="w-[400px] border-l border-border bg-background flex flex-col fixed right-0 top-0 h-screen z-50 lg:relative lg:z-0">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-secondary/30">
          <h2 className="font-semibold text-foreground">Document Manager</h2>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border bg-secondary/20">
          <button
            onClick={() => setActiveTab('rag')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'rag'
                ? 'text-primary border-b-2 border-primary bg-background'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary/30'
            }`}
          >
            <FileText className="w-4 h-4" />
            RAG Documents
          </button>
          <button
            onClick={() => setActiveTab('sql')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'sql'
                ? 'text-primary border-b-2 border-primary bg-background'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary/30'
            }`}
          >
            <Database className="w-4 h-4" />
            SQL Tables
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'rag' ? <RAGTab /> : <SQLTab />}
        </div>
      </aside>
    </>
  );
};
