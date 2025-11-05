/**
 * ConversationSidebar - Sidebar gauche avec historique conversations + user menu
 * Style: Minimaliste, moderne, inspiré Claude.ai/ChatGPT
 */

import { useState } from 'react';
import { Plus, MessageSquare, Settings, LayoutDashboard, LogOut, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Conversation {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  messageCount: number;
}

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  userName?: string;
  onSettingsClick?: () => void;
  onAdminClick?: () => void;
  onLogoutClick?: () => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  userName = 'Utilisateur',
  onSettingsClick,
  onAdminClick,
  onLogoutClick,
}: ConversationSidebarProps) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  return (
    <div className="w-64 h-screen bg-gray-50 border-r border-gray-200 flex flex-col">
      {/* Header avec bouton Nouvelle conversation */}
      <div className="p-4 border-b border-gray-200">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Nouvelle conversation</span>
        </button>
      </div>

      {/* Liste des conversations */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {conversations.length === 0 ? (
          <div className="text-center py-8 px-4">
            <MessageSquare className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">Aucune conversation</p>
          </div>
        ) : (
          <div className="space-y-1">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors group ${
                  activeConversationId === conversation.id
                    ? 'bg-white shadow-sm border border-gray-200'
                    : 'hover:bg-white hover:shadow-sm'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {conversation.title}
                    </div>
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {conversation.preview}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-gray-400">
                        {formatRelativeTime(conversation.timestamp)}
                      </span>
                      <span className="text-xs text-gray-400">
                        • {conversation.messageCount} msg
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* User Menu en bas */}
      <div className="border-t border-gray-200 p-2 relative">
        <button
          onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
          className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white rounded-lg transition-colors group"
        >
          {/* Avatar */}
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
            {userName.charAt(0).toUpperCase()}
          </div>

          {/* User info */}
          <div className="flex-1 min-w-0 text-left">
            <div className="text-sm font-medium text-gray-900 truncate">
              {userName}
            </div>
            <div className="text-xs text-gray-500">
              Gérer le compte
            </div>
          </div>

          {/* Chevron */}
          <ChevronDown
            className={`w-4 h-4 text-gray-400 transition-transform ${
              isUserMenuOpen ? 'rotate-180' : ''
            }`}
          />
        </button>

        {/* Dropdown menu */}
        <AnimatePresence>
          {isUserMenuOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsUserMenuOpen(false)}
              />

              {/* Menu */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.15 }}
                className="absolute bottom-full left-2 right-2 mb-2 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20"
              >
                {onSettingsClick && (
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      onSettingsClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <Settings className="w-4 h-4 text-gray-500" />
                    <span>Paramètres</span>
                  </button>
                )}

                {onAdminClick && (
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      onAdminClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <LayoutDashboard className="w-4 h-4 text-gray-500" />
                    <span>Interface Admin</span>
                  </button>
                )}

                <div className="h-px bg-gray-200 my-1" />

                {onLogoutClick && (
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      onLogoutClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Déconnexion</span>
                  </button>
                )}
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// Helper: Format relative time
function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'maintenant';
  if (diffMins < 60) return `${diffMins}min`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}j`;

  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}
