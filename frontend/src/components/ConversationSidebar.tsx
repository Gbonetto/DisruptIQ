import React from 'react';
import { MessageSquare, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Conversation {
  id: string;
  title: string;
  timestamp: string;
}

interface ConversationSidebarProps {
  conversations?: Conversation[];
  onNewChat?: () => void;
  onSelectConversation?: (id: string) => void;
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  conversations = [],
  onNewChat,
  onSelectConversation,
}) => {
  return (
    <aside className="w-[280px] border-r border-border bg-background flex flex-col">
      <div className="p-4 border-b border-border">
        <Button onClick={onNewChat} className="w-full" size="sm">
          <Plus className="w-4 h-4 mr-2" />
          Nouvelle conversation
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              onClick={() => onSelectConversation?.(conversation.id)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-accent transition-colors"
            >
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {conversation.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {conversation.timestamp}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
};
