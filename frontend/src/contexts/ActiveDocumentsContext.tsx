import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ActiveDocumentsContextType {
  activeDocumentIds: number[];
  setActiveDocumentIds: (ids: number[]) => void;
}

const ActiveDocumentsContext = createContext<ActiveDocumentsContextType | undefined>(undefined);

export const ActiveDocumentsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [activeDocumentIds, setActiveDocumentIds] = useState<number[]>([]);

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
