import React, { useState, useEffect, useRef } from 'react';
import { Database, FileText, Search, TrendingUp, ArrowDown } from 'lucide-react';
import { MainLayout } from '@/components/v2/Layout/MainLayout';
import { SmartCardsGrid } from '@/components/v2/Core/SmartCard';
import { ChainOfThought, type ThoughtStep } from '@/components/v2/Core/ChainOfThought';
import { SourceCitationFooter } from '@/components/v2/Core/SourceCitation';
import { DataTable } from '@/components/v2/Core/DataTable';
import { RichMarkdown } from '@/components/v2/Core/RichMarkdown';
import { MessageLoadingSkeleton } from '@/components/v2/Core/LoadingSkeleton';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import {
  assistantV2Api,
  conversationsApi,
  setupStreamListeners,
  type Conversation,
  type Message,
  type Thought,
} from '@/lib/api-v2';
import { useActiveDocuments } from '@/contexts/ActiveDocumentsContext';
import { SourceSelector } from '@/components/SourceSelector';
import { useUIContext } from '@/hooks/useUIContext';

export const MainChatPageV2: React.FC = () => {
  const { activeDocumentIds } = useActiveDocuments();
  const { buildContext } = useUIContext();

  // State
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentThoughts, setCurrentThoughts] = useState<Thought[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);

  // Ref to track current thoughts for use in callbacks (avoids stale closure)
  const thoughtsRef = useRef<Thought[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll to bottom when messages change (smooth scroll)
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages, currentThoughts]);

  // Detect if user scrolled up
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom && messages.length > 0);
    };

    scrollContainer.addEventListener('scroll', handleScroll);
    return () => scrollContainer.removeEventListener('scroll', handleScroll);
  }, [messages.length]);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputValue]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversations from backend
  const loadConversations = async () => {
    try {
      const data = await conversationsApi.list(50, 0);
      setConversations(data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
      toast.error('Erreur lors du chargement des conversations');
    }
  };

  // Normalize message to ensure all arrays are defined (not null)
  const normalizeMessage = (msg: Message): Message => ({
    ...msg,
    thoughts: Array.isArray(msg.thoughts) ? msg.thoughts : [],
    sources: Array.isArray(msg.sources) ? msg.sources : [],
    suggestions: Array.isArray(msg.suggestions) ? msg.suggestions : [],
  });

  // Load a specific conversation
  const loadConversation = async (conversationId: number) => {
    try {
      const data = await conversationsApi.get(conversationId);
      setCurrentConversationId(conversationId);
      // Normalize messages to ensure arrays are never null
      setMessages(data.messages.map(normalizeMessage));
    } catch (error) {
      console.error('Failed to load conversation:', error);
      toast.error('Erreur lors du chargement de la conversation');
    }
  };

  // Create a new conversation
  const createNewConversation = async () => {
    try {
      const newConv = await conversationsApi.create();
      setConversations(prev => [newConv, ...prev]);
      setCurrentConversationId(newConv.id);
      setMessages([]);
      setInputValue('');
    } catch (error) {
      console.error('Failed to create conversation:', error);
      toast.error('Erreur lors de la création de la conversation');
    }
  };

  // Rename conversation
  const handleRenameConversation = async (id: string, newTitle: string) => {
    const convId = parseInt(id);
    try {
      await conversationsApi.updateTitle(convId, newTitle);
      setConversations(prev =>
        prev.map(conv => conv.id === convId ? { ...conv, title: newTitle } : conv)
      );
      toast.success('Conversation renommée');
    } catch (error) {
      console.error('Failed to rename conversation:', error);
      toast.error('Erreur lors du renommage');
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (id: string) => {
    const convId = parseInt(id);
    try {
      await conversationsApi.delete(convId);
      setConversations(prev => prev.filter(conv => conv.id !== convId));
      if (currentConversationId === convId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
      toast.success('Conversation supprimée');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      toast.error('Erreur lors de la suppression');
    }
  };

  // Select conversation
  const handleSelectConversation = (id: string) => {
    loadConversation(parseInt(id));
  };

  // Smart cards for empty state
  const smartCards = [
    {
      icon: Database,
      title: 'Combien de copropriétaires dans l\'Immeuble A?',
      description: 'Interrogez la base de données',
      onClick: () => setInputValue('Combien de copropriétaires dans l\'Immeuble A?'),
    },
    {
      icon: FileText,
      title: 'Envoyer email pour dégât des eaux',
      description: 'Générer un email automatique',
      onClick: () => setInputValue('Envoyer un email aux copropriétaires concernant un dégât des eaux'),
    },
    {
      icon: Search,
      title: 'Demander devis aux jardiniers',
      description: 'Contacter des professionnels',
      onClick: () => setInputValue('Demander des devis aux jardiniers pour l\'entretien des espaces verts'),
    },
    {
      icon: TrendingUp,
      title: 'Procédure assemblée générale',
      description: 'Consulter la documentation',
      onClick: () => setInputValue('Quelle est la procédure pour organiser une assemblée générale?'),
    },
  ];

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setCurrentThoughts([]);
    thoughtsRef.current = []; // Reset ref too

    try {
      // Create conversation if none exists
      let conversationId = currentConversationId;
      if (!conversationId) {
        const newConv = await conversationsApi.create();
        setConversations(prev => [newConv, ...prev]);
        setCurrentConversationId(newConv.id);
        conversationId = newConv.id;
      }

      // Add user message to conversation
      const userMsg = await conversationsApi.addMessage(
        conversationId,
        'user',
        userMessage
      );
      // Normalize even user messages for consistency
      setMessages(prev => [...prev, normalizeMessage(userMsg)]);

      // Prepare conversation history for backend
      const history = messages.map(m => ({
        role: m.role,
        content: m.content,
        data: m.data,
      }));

      // Build UI context for bypass optimization (Sprint 1 - Level 0)
      const uiContext = buildContext();

      // Start SSE streaming with active document IDs, selected sources, and UI context
      console.log('[MainChatPageV2] About to create EventSource...');
      console.log('[MainChatPageV2] Params:', { userMessage: userMessage.substring(0, 50), historyLen: history.length, conversationId, activeDocumentIds, selectedSources, uiContext });

      let eventSource: EventSource;
      try {
        eventSource = assistantV2Api.streamChat(
          userMessage,
          history,
          conversationId.toString(),
          activeDocumentIds,
          selectedSources,
          uiContext  // ← NEW: Pass UI context for bypass
        );
        console.log('[MainChatPageV2] EventSource created successfully');
      } catch (err) {
        console.error('[MainChatPageV2] EventSource creation FAILED:', err);
        throw err;
      }
      eventSourceRef.current = eventSource;

      console.log('[MainChatPageV2] EventSource URL:', eventSource.url);
      console.log('[MainChatPageV2] EventSource readyState:', eventSource.readyState);

      // Setup event listeners
      setupStreamListeners(eventSource, {
        onThought: (thought) => {
          console.log('[MainChatPageV2] Received thought:', thought);
          setCurrentThoughts(prev => {
            const newThoughts = [...prev, thought];
            thoughtsRef.current = newThoughts; // Keep ref in sync
            console.log('[MainChatPageV2] Updating thoughts, count:', newThoughts.length);
            return newThoughts;
          });
        },

        onResponse: async (response) => {
          // Save assistant message to database
          try {
            // Transform sources to Citation format (defensive: ensure array)
            const sourcesArray = Array.isArray(response.sources) ? response.sources : [];
            const formattedSources = sourcesArray.map((source: any, index: number) => {
              // Determine a descriptive title - check ALL possible fields
              let title = 'Document';
              if (source.type === 'sql') {
                title = source.title || 'Base de données';
              } else {
                // For RAG/web: check filename, title, document, name (in order)
                title = source.filename || source.title || source.document || source.name || 'Document';
              }

              // Build metadata with additional context
              const metadata: any = { score: source.score };

              // For SQL sources, add table names if available
              if (source.type === 'sql' && source.tables) {
                metadata.tables = source.tables;
              }

              // For RAG sources, the content is already in excerpt/text
              // We'll display it as citation.content

              return {
                id: index + 1,
                type: source.type === 'document' ? 'rag' : source.type,
                title: title,
                content: source.excerpt || source.text || '',
                metadata: metadata
              };
            });

            // Use ref to get current thoughts (avoids stale closure issue)
            const thoughtsToSave = thoughtsRef.current || [];
            const suggestionsArray = Array.isArray(response.suggestions) ? response.suggestions : [];
            console.log('[MainChatPageV2] Saving message with thoughts:', thoughtsToSave.length);

            const assistantMsg = await conversationsApi.addMessage(
              conversationId!,
              'assistant',
              response.message,
              thoughtsToSave,
              formattedSources,
              suggestionsArray,
              response.data
            );
            // Normalize the message to ensure arrays are never null
            setMessages(prev => [...prev, normalizeMessage(assistantMsg)]);
          } catch (error) {
            console.error('Failed to save assistant message:', error);
          }

          // Clear temporary state - thoughts are now saved in the message
          setCurrentThoughts([]);
          thoughtsRef.current = []; // Reset ref too
          setIsLoading(false);
          eventSource.close();

          // Reload conversations to update preview/count
          loadConversations();
        },

        onError: (error) => {
          console.error('SSE Error détaillé:', {
            error,
            readyState: eventSource.readyState,
            url: eventSource.url
          });

          // Ne montrer l'erreur que si ce n'est pas juste une fermeture normale
          if (eventSource.readyState !== EventSource.CLOSED) {
            toast.error('Erreur lors de la communication avec le serveur');
          }

          setIsLoading(false);
          setCurrentThoughts([]);
          thoughtsRef.current = [];
          eventSource.close();
        },

        onClose: () => {
          setIsLoading(false);
        },
      });
    } catch (error) {
      console.error('Send message error:', error);
      toast.error('Erreur lors de l\'envoi du message');
      setIsLoading(false);
    }
  };

  // Stop streaming
  const handleStopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsLoading(false);
      setCurrentThoughts([]);
      thoughtsRef.current = [];
      toast.info('Traitement arrêté');
    }
  };

  // Helper to format conversation for LeftPanel
  const formatConversationsForPanel = () => {
    return conversations.map(conv => ({
      id: conv.id.toString(),
      title: conv.title || 'Nouvelle conversation',
      timestamp: formatTimestamp(conv.updated_at),
    }));
  };

  // Helper to format timestamp
  const formatTimestamp = (isoDate: string): string => {
    const date = new Date(isoDate);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'À l\'instant';
    if (diffMins < 60) return `Il y a ${diffMins} min`;
    if (diffHours < 24) return `Il y a ${diffHours}h`;
    if (diffDays < 7) return `Il y a ${diffDays} jour${diffDays > 1 ? 's' : ''}`;
    return date.toLocaleDateString('fr-FR');
  };

  return (
    <MainLayout
      conversations={formatConversationsForPanel()}
      currentConversationId={currentConversationId?.toString()}
      onNewChat={createNewConversation}
      onSelectConversation={handleSelectConversation}
      onRenameConversation={handleRenameConversation}
      onDeleteConversation={handleDeleteConversation}
    >
      {/* Chat area */}
      <div className="flex-1 flex flex-col h-full relative">
        {/* Messages area */}
        <ScrollArea className="flex-1 scroll-smooth" ref={scrollAreaRef}>
          <div ref={scrollContainerRef} className="h-full overflow-y-auto">
          <div className="w-full flex justify-center px-6">
            <div className="w-full max-w-4xl overflow-hidden">
          {messages.length === 0 ? (
            // Empty state with smart cards
            <div className="flex flex-col items-center justify-center h-full py-12">
              <div className="w-full max-w-2xl space-y-8">
                {/* Welcome message */}
                <div className="text-center space-y-2">
                  <h1 className="text-3xl font-semibold text-foreground">
                    Bonjour, comment puis-je vous aider ?
                  </h1>
                  <p className="text-muted-foreground">
                    Choisissez une suggestion ou posez votre question
                  </p>
                </div>

                {/* Smart cards */}
                <SmartCardsGrid cards={smartCards} />
              </div>
            </div>
          ) : (
            // Messages
            <div className="space-y-6 py-6">
              {messages.map((message, index) => (
                <div key={message.id || index}>
                  {message.role === 'user' ? (
                    // User message
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-primary text-primary-foreground break-words overflow-hidden">
                        <p className="text-sm leading-relaxed break-words">{message.content}</p>
                        <p className="text-xs text-primary-foreground/70 mt-1">
                          {new Date(message.timestamp).toLocaleTimeString('fr-FR')}
                        </p>
                      </div>
                    </div>
                  ) : (
                    // Assistant message with rich content - Fade-in animation
                    <div className="flex justify-start animate-slideUp">
                      <div className="w-full space-y-4 break-words overflow-hidden">
                        {/* Chain of Thought */}
                        {message.thoughts && message.thoughts.length > 0 && (
                          <ChainOfThought
                            steps={message.thoughts.map(t => ({
                              id: t.id,
                              type: t.type as ThoughtStep['type'],
                              title: t.title,
                              content: t.content,
                              agent: t.agent,
                              timestamp: t.timestamp,
                              data: t.data,
                            }))}
                            isStreaming={false}
                          />
                        )}

                        {/* Main response with Rich Markdown */}
                        <div className="rounded-2xl px-4 py-3 bg-secondary text-foreground break-words overflow-hidden">
                          <RichMarkdown content={message.content} />
                        </div>

                        {/* Data Table (if present in message.data) */}
                        {message.data?.table && (
                          <DataTable
                            title={message.data.table.title}
                            headers={message.data.table.headers}
                            rows={message.data.table.rows}
                          />
                        )}

                        {/* Source Citations */}
                        {message.sources && message.sources.length > 0 && (
                          <div className="rounded-2xl px-4 py-3 bg-secondary/50">
                            <SourceCitationFooter citations={message.sources} />
                          </div>
                        )}

                        {/* Suggestions */}
                        {message.suggestions && message.suggestions.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {message.suggestions.map((suggestion, i) => (
                              <Button
                                key={i}
                                variant="outline"
                                size="sm"
                                onClick={() => setInputValue(suggestion)}
                                className="text-xs"
                              >
                                {suggestion}
                              </Button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Current streaming thoughts - shown during active streaming ONLY */}
              {isLoading && currentThoughts.length > 0 && (
                <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                  <div className="space-y-4">
                    <ChainOfThought
                      steps={currentThoughts.map(t => ({
                        id: t.id,
                        type: t.type as ThoughtStep['type'],
                        title: t.title,
                        content: t.content,
                        agent: t.agent,
                        timestamp: t.timestamp,
                        data: t.data,
                      }))}
                      isStreaming={true}
                      startTime={currentThoughts[0]?.timestamp ? new Date(currentThoughts[0].timestamp).getTime() : Date.now()}
                    />
                    <MessageLoadingSkeleton />
                  </div>
                </div>
              )}

              {/* Loading skeleton */}
              {isLoading && currentThoughts.length === 0 && <MessageLoadingSkeleton />}

              {/* Invisible element for auto-scroll */}
              <div ref={messagesEndRef} />
            </div>
          )}
            </div>
          </div>
          </div>
        </ScrollArea>

        {/* Scroll to bottom button */}
        {showScrollButton && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-24 right-8 z-10 p-3 bg-primary text-primary-foreground rounded-full shadow-lg hover:shadow-xl transition-all hover:scale-110 animate-fadeIn"
            aria-label="Descendre en bas"
          >
            <ArrowDown className="w-5 h-5" />
          </button>
        )}

        {/* Input area */}
        <div className="border-t border-border p-6 bg-background">
          <div className="w-full flex justify-center">
            <div className="w-full max-w-4xl">
              {/* Input row with integrated source selector */}
              <div className="flex gap-2 items-end">
                {/* Source Selector - ChatGPT style, left of textarea */}
                <div className="flex items-end pb-2">
                  <SourceSelector
                    selectedSources={selectedSources}
                    onChange={setSelectedSources}
                  />
                </div>

                {/* Textarea */}
                <Textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !isLoading) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Posez votre question... (Entrée pour envoyer, Maj+Entrée pour nouvelle ligne)"
                  className="flex-1 min-h-[44px] max-h-[200px] resize-none"
                  disabled={isLoading}
                  rows={1}
                />

                {/* Send/Stop button */}
                {isLoading ? (
                  <Button onClick={handleStopStreaming} variant="destructive" size="default">
                    Arrêter
                  </Button>
                ) : (
                  <Button onClick={handleSendMessage} disabled={!inputValue.trim()} size="default">
                    Envoyer
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
};
