import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface ActiveDocumentsContextType {
  activeDocumentIds: number[];
  setActiveDocumentIds: (ids: number[]) => void;
}

const ActiveDocumentsContext = createContext<ActiveDocumentsContextType | undefined>(undefined);

const ACTIVE_DOCS_KEY = 'active_document_ids';

export const ActiveDocumentsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Initialize from localStorage
  const [activeDocumentIds, setActiveDocumentIds] = useState<number[]>(() => {
    const saved = localStorage.getItem(ACTIVE_DOCS_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        console.log('[ActiveDocumentsContext] Restored from localStorage:', parsed);
        return parsed;
      } catch (e) {
        console.error('[ActiveDocumentsContext] Failed to parse localStorage:', e);
        return [];
      }
    }
    return [];
  });

  // Sync to localStorage whenever activeDocumentIds changes
  useEffect(() => {
    localStorage.setItem(ACTIVE_DOCS_KEY, JSON.stringify(activeDocumentIds));
    console.log('[ActiveDocumentsContext] Saved to localStorage:', activeDocumentIds);
  }, [activeDocumentIds]);

  return (
    <ActiveDocumentsContext.Provider value={{ activeDocumentIds, setActiveDocumentIds }}>
      {children}
    </ActiveDocumentsContext.Provider>
  );
};

export const useActiveDocuments = () => {
  const context = useContext(ActiveDocumentsContext);
  if (context === undefined) {
    throw new Error('useActiveDocuments must be used within an ActiveDocumentsProvider');
  }
  return context;
};
