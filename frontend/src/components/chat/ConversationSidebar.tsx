/**
 * ConversationSidebar - Sidebar gauche avec historique conversations + user menu
 * Style: Minimaliste, moderne, inspiré Claude.ai/ChatGPT
 */

import { useState } from 'react';
import { Plus, MessageSquare, Settings, LayoutDashboard, LogOut, ChevronDown, MoreVertical, Edit2, Trash2 } from 'lucide-react';
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
  onRenameConversation?: (id: string, newTitle: string) => void;
  onDeleteConversation?: (id: string) => void;
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
  onRenameConversation,
  onDeleteConversation,
  userName = 'Utilisateur',
  onSettingsClick,
  onAdminClick,
  onLogoutClick,
}: ConversationSidebarProps) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState('');

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
              <div
                key={conversation.id}
                className={`relative rounded-lg transition-colors group ${
                  activeConversationId === conversation.id
                    ? 'bg-white shadow-sm border border-gray-200'
                    : 'hover:bg-white hover:shadow-sm'
                }`}
              >
                <button
                  onClick={() => onSelectConversation(conversation.id)}
                  className="w-full text-left px-3 py-2.5"
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0 pr-6">
                      {renamingId === conversation.id ? (
                        <input
                          type="text"
                          value={renameTitle}
                          onChange={(e) => setRenameTitle(e.target.value)}
                          onBlur={() => {
                            if (renameTitle.trim() && onRenameConversation) {
                              onRenameConversation(conversation.id, renameTitle.trim());
                            }
                            setRenamingId(null);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              if (renameTitle.trim() && onRenameConversation) {
                                onRenameConversation(conversation.id, renameTitle.trim());
                              }
                              setRenamingId(null);
                            } else if (e.key === 'Escape') {
                              setRenamingId(null);
                            }
                          }}
                          onClick={(e) => e.stopPropagation()}
                          autoFocus
                          className="w-full text-sm font-medium text-gray-900 bg-white border border-blue-500 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      ) : (
                        <>
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
                        </>
                      )}
                    </div>
                  </div>
                </button>

                {/* 3-dot menu button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenMenuId(openMenuId === conversation.id ? null : conversation.id);
                  }}
                  className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-gray-100 transition-opacity"
                >
                  <MoreVertical className="w-4 h-4 text-gray-500" />
                </button>

                {/* Dropdown menu */}
                <AnimatePresence>
                  {openMenuId === conversation.id && (
                    <>
                      {/* Backdrop */}
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setOpenMenuId(null)}
                      />

                      {/* Menu */}
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.1 }}
                        className="absolute top-8 right-2 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20 min-w-[160px]"
                      >
                        {onRenameConversation && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setRenameTitle(conversation.title);
                              setRenamingId(conversation.id);
                              setOpenMenuId(null);
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                          >
                            <Edit2 className="w-4 h-4 text-gray-500" />
                            <span>Renommer</span>
                          </button>
                        )}

                        {onDeleteConversation && (
                          <>
                            <div className="h-px bg-gray-200 my-1" />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (window.confirm('Êtes-vous sûr de vouloir supprimer cette conversation ?')) {
                                  onDeleteConversation(conversation.id);
                                }
                                setOpenMenuId(null);
                              }}
                              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                              <span>Supprimer</span>
                            </button>
                          </>
                        )}
                      </motion.div>
                    </>
                  )}
                </AnimatePresence>
              </div>
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
