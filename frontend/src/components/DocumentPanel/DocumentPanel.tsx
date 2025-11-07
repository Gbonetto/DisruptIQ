import { useState } from 'react';
import { X, FileText, Database, ChevronRight } from 'lucide-react';
import { RAGTab } from './RAGTab';
import { SQLTab } from './SQLTab';

interface DocumentPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'rag' | 'sql';

export function DocumentPanel({ isOpen, onClose }: DocumentPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('rag');

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-[450px] bg-retro-gray border-l border-neon-violet/30 shadow-2xl z-50 flex flex-col animate-pixel-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neon-violet/30 retro-gradient-cyber">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-neon-cyan" />
          <h2 className="text-lg font-semibold text-white font-pixel">Document Manager</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-retro-dark rounded-lg transition-colors border border-transparent hover:border-neon-pink/50"
          aria-label="Close panel"
        >
          <X className="w-5 h-5 text-neon-pink" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-neon-violet/30 bg-retro-dark/50">
        <button
          onClick={() => setActiveTab('rag')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 pixel-border-sm ${
            activeTab === 'rag'
              ? 'text-neon-cyan border-b-2 border-neon-cyan bg-retro-dark neon-glow-cyan'
              : 'text-gray-400 hover:text-white hover-neon-violet'
          }`}
        >
          <FileText className="w-4 h-4" />
          RAG Documents
        </button>
        <button
          onClick={() => setActiveTab('sql')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 pixel-border-sm ${
            activeTab === 'sql'
              ? 'text-neon-cyan border-b-2 border-neon-cyan bg-retro-dark neon-glow-cyan'
              : 'text-gray-400 hover:text-white hover-neon-violet'
          }`}
        >
          <Database className="w-4 h-4" />
          SQL Tables
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {activeTab === 'rag' ? <RAGTab /> : <SQLTab />}
      </div>
    </div>
  );
}

interface ToggleButtonProps {
  isOpen: boolean;
  onClick: () => void;
}

export function DocumentPanelToggle({ isOpen, onClick }: ToggleButtonProps) {
  return (
    <button
      onClick={onClick}
      className="fixed right-4 top-4 z-40 p-3 retro-gradient-cyber text-white rounded-lg shadow-lg hover:animate-neon-pulse transition-all hover:scale-105 pixel-border-sm"
      aria-label={isOpen ? 'Close document panel' : 'Open document panel'}
    >
      {isOpen ? (
        <ChevronRight className="w-5 h-5" />
      ) : (
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5" />
          <span className="text-sm font-medium font-pixel">Documents</span>
        </div>
      )}
    </button>
  );
}
