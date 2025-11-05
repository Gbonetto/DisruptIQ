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
    <div className="fixed right-0 top-0 h-full w-[450px] bg-white border-l border-gray-200 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-indigo-50 to-white">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-semibold text-gray-900">Document Manager</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          aria-label="Close panel"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 bg-gray-50">
        <button
          onClick={() => setActiveTab('rag')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
            activeTab === 'rag'
              ? 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
          }`}
        >
          <FileText className="w-4 h-4" />
          RAG Documents
        </button>
        <button
          onClick={() => setActiveTab('sql')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
            activeTab === 'sql'
              ? 'text-indigo-600 border-b-2 border-indigo-600 bg-white'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
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
      className="fixed right-4 top-4 z-40 p-3 bg-indigo-600 text-white rounded-lg shadow-lg hover:bg-indigo-700 transition-all hover:scale-105"
      aria-label={isOpen ? 'Close document panel' : 'Open document panel'}
    >
      {isOpen ? (
        <ChevronRight className="w-5 h-5" />
      ) : (
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5" />
          <span className="text-sm font-medium">Documents</span>
        </div>
      )}
    </button>
  );
}
