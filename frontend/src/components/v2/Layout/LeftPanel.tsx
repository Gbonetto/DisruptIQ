import React, { useState } from 'react';
import { Clock, User, MoreVertical, Edit2, Trash2, MessageSquare, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface Conversation {
  id: string;
  title: string;
  timestamp: string;
}

interface LeftPanelProps {
  conversations?: Conversation[];
  currentConversationId?: string;
  onSelectConversation?: (id: string) => void;
  onNewChat?: () => void;
  onRenameConversation?: (id: string, newTitle: string) => void;
  onDeleteConversation?: (id: string) => void;
}

export const LeftPanel: React.FC<LeftPanelProps> = ({
  conversations = [],
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onDeleteConversation,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteDialog, setDeleteDialog] = useState<{ open: boolean; id: string; title: string }>({
    open: false,
    id: '',
    title: '',
  });

  const handleRename = (conv: Conversation) => {
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const handleSaveRename = (id: string) => {
    if (editTitle.trim() && onRenameConversation) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const openDeleteDialog = (id: string, title: string) => {
    setDeleteDialog({ open: true, id, title });
  };

  const confirmDelete = () => {
    if (onDeleteConversation) {
      onDeleteConversation(deleteDialog.id);
    }
    setDeleteDialog({ open: false, id: '', title: '' });
  };

  return (
    <aside className="w-[280px] border-r border-border bg-background flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <Button
          onClick={onNewChat}
          className="w-full"
          size="sm"
        >
          <MessageSquare className="w-4 h-4 mr-2" />
          Nouvelle conversation
        </Button>
      </div>

      {/* Conversations list - Simple overflow-y-auto comme ChatGPT */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-hide">
        <div className="flex flex-col gap-1 p-2">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              Aucune conversation
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`
                  group relative flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all duration-200
                  hover:bg-secondary
                  ${
                    currentConversationId === conv.id
                      ? 'bg-secondary text-foreground border-l-[3px] border-l-primary font-medium'
                      : 'text-muted-foreground border-l-[3px] border-l-transparent'
                  }
                `}
                onClick={() => onSelectConversation?.(conv.id)}
              >
                {/* Content - Title + Timestamp (icône retirée pour gagner de l'espace) */}
                <div className="flex-1 min-w-0">
                  {editingId === conv.id ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onBlur={() => handleSaveRename(conv.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRename(conv.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full text-sm font-medium bg-background border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary"
                      autoFocus
                    />
                  ) : (
                    <div className="text-sm font-medium truncate" title={conv.title}>
                      {conv.title}
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                    <Clock className="w-3 h-3" />
                    {conv.timestamp}
                  </div>
                </div>

                {/* Menu burger - Visible au hover comme ChatGPT */}
                <div className="invisible group-hover:visible flex-shrink-0">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 hover:bg-accent rounded-md transition-colors"
                        aria-label="Options de conversation"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRename(conv);
                        }}
                        className="cursor-pointer"
                      >
                        <Edit2 className="w-4 h-4 mr-2" />
                        Renommer
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          openDeleteDialog(conv.id, conv.title);
                        }}
                        className="cursor-pointer text-destructive focus:text-destructive"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Supprimer
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* User profile (optional footer) */}
      <div className="p-4 border-t border-border">
        <button className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-secondary transition-colors text-sm">
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1 text-left">
            <div className="font-medium">Utilisateur</div>
          </div>
        </button>
      </div>

      {/* Dialog de confirmation de suppression */}
      <AlertDialog open={deleteDialog.open} onOpenChange={(open: boolean) => !open && setDeleteDialog({ open: false, id: '', title: '' })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              Supprimer la conversation
            </AlertDialogTitle>
            <AlertDialogDescription>
              Êtes-vous sûr de vouloir supprimer la conversation <strong>"{deleteDialog.title}"</strong> ?
              <br />
              <span className="text-destructive">Cette action est irréversible.</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive hover:bg-destructive/90">
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
};
