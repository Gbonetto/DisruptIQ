import React, { useState } from 'react';
import { Header } from './Header';
import { LeftPanel } from './LeftPanel';
import { RightPanel } from './RightPanel';

interface MainLayoutProps {
  children: React.ReactNode;
  conversations?: any[];
  currentConversationId?: string;
  onSelectConversation?: (id: string) => void;
  onNewChat?: () => void;
  onRenameConversation?: (id: string, newTitle: string) => void;
  onDeleteConversation?: (id: string) => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onDeleteConversation,
}) => {
  const [isDocumentPanelOpen, setIsDocumentPanelOpen] = useState(false);

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <Header onToggleDocuments={() => setIsDocumentPanelOpen(!isDocumentPanelOpen)} />

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar - Conversations */}
        <LeftPanel
          conversations={conversations}
          currentConversationId={currentConversationId}
          onSelectConversation={onSelectConversation}
          onNewChat={onNewChat}
          onRenameConversation={onRenameConversation}
          onDeleteConversation={onDeleteConversation}
        />

        {/* Center - Main chat area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Chat area with max-width and centered */}
          <div className="flex-1 flex justify-center overflow-hidden">
            <div className="w-full max-w-[800px] flex flex-col">
              {children}
            </div>
          </div>
        </main>

        {/* Right sidebar - Documents (conditional) */}
        <RightPanel
          isOpen={isDocumentPanelOpen}
          onClose={() => setIsDocumentPanelOpen(false)}
        />
      </div>
    </div>
  );
};
