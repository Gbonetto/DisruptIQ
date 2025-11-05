/**
 * MainChatPageV2 - Modern 3-Column Chat Interface
 * Layout: ConversationSidebar | Chat (bubbles) | DocumentPanel
 * Style: WhatsApp/iMessage/Claude - Messages user à droite, assistant à gauche
 */

import { useState, useRef, useEffect } from 'react';
import { FileText } from 'lucide-react';
import { toast } from 'sonner';
import { DocumentPanel } from '@/components/DocumentPanel/DocumentPanel';
import { ConversationSidebar } from '@/components/chat/ConversationSidebar';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChainOfThoughts } from '@/components/ChainOfThoughts';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  thoughts?: Thought[];
  sources?: Source[];
  suggestions?: Suggestion[];
  confirmation_required?: ConfirmationData;
  table_data?: any[];
  timestamp: Date;
}

interface Thought {
  id: string;
  type: 'analyzing' | 'classifying' | 'planning' | 'executing' | 'processing' | 'synthesizing' | 'completed' | 'error';
  timestamp: string;
  agent?: string;
  title: string;
  content: string;
  data?: any;
  progress?: number;
}

interface Source {
  type: 'sql' | 'rag' | 'web';
  title: string;
  content: string;
  metadata?: any;
}

interface Suggestion {
  label: string;
  action: string;
  icon?: string;
}

interface ConfirmationData {
  action: string;
  impact: string[];
  preview: string;
}

interface Conversation {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  messageCount: number;
}

export function MainChatPageV2() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentThoughts, setCurrentThoughts] = useState<Thought[]>([]);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationData | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(true); // Open by default in 3-col layout
  const [documents, setDocuments] = useState<any[]>([]);

  // Conversations (mock pour l'instant)
  const [conversations, _setConversations] = useState<Conversation[]>([
    {
      id: '1',
      title: 'Analyse facture plomberie',
      preview: 'Vérifier la facture de plomberie...',
      timestamp: new Date(Date.now() - 3600000),
      messageCount: 5
    },
    {
      id: '2',
      title: 'Digest emails',
      preview: 'Générer le digest des emails...',
      timestamp: new Date(Date.now() - 7200000),
      messageCount: 3
    }
  ]);
  const [activeConversationId, setActiveConversationId] = useState<string | undefined>();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load documents count
  useEffect(() => {
    const loadDocs = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents/`);
        const data = await response.json();
        setDocuments(data.documents || []);
      } catch (error) {
        console.error('Failed to load documents:', error);
      }
    };
    loadDocs();
    const interval = setInterval(loadDocs, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentThoughts]);

  // Send message
  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setCurrentThoughts([]);

    try {
      // Stream SSE
      const eventSource = new EventSource(
        `${API_BASE_URL}/api/assistant-v2/chat/stream?` +
        new URLSearchParams({
          message: input,
          session_id: 'default',
          conversation_history: JSON.stringify(messages.slice(-5).map(m => ({
            role: m.role,
            content: m.content
          })))
        })
      );

      eventSourceRef.current = eventSource;

      // Thought events
      eventSource.addEventListener('thought', (e) => {
        const thought: Thought = JSON.parse(e.data);
        setCurrentThoughts(prev => [...prev, thought]);
      });

      // Confirmation required
      eventSource.addEventListener('confirmation_required', (e) => {
        const confirmationData: ConfirmationData = JSON.parse(e.data);
        setPendingConfirmation(confirmationData);
      });

      // Final response
      eventSource.addEventListener('response', (e) => {
        const response = JSON.parse(e.data);

        const assistantMessage: Message = {
          role: 'assistant',
          content: response.message,
          thoughts: currentThoughts,
          sources: response.sources,
          suggestions: response.suggestions,
          table_data: response.table_data,
          timestamp: new Date()
        };

        setMessages(prev => [...prev, assistantMessage]);
        setCurrentThoughts([]);
        setIsStreaming(false);
        eventSource.close();
      });

      // Errors
      eventSource.addEventListener('error', () => {
        toast.error('Erreur de connexion');
        setIsStreaming(false);
        eventSource.close();
      });

    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Erreur lors de l\'envoi');
      setIsStreaming(false);
    }
  };

  const handleStop = () => {
    eventSourceRef.current?.close();
    setIsStreaming(false);
    setCurrentThoughts([]);
    toast.info('Arrêté');
  };

  const handleSuggestionClick = (suggestion: Suggestion) => {
    setInput(suggestion.action);
  };

  const handleNewConversation = () => {
    setMessages([]);
    setCurrentThoughts([]);
    setActiveConversationId(undefined);
    toast.success('Nouvelle conversation');
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    // TODO: Load conversation messages from backend
    toast.info('Chargement de la conversation...');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left: Conversation Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        userName="Utilisateur"
        onSettingsClick={() => toast.info('Paramètres (à venir)')}
        onAdminClick={() => window.location.href = '/admin'}
        onLogoutClick={() => toast.info('Déconnexion (à venir)')}
      />

      {/* Center: Chat Area */}
      <div className="flex-1 flex flex-col bg-white">
        {/* Header */}
        <header className="h-16 border-b border-gray-200 px-6 flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">DisruptIQ Assistant</h1>
            <p className="text-xs text-gray-500">Powered by AI</p>
          </div>
          <button
            onClick={() => setIsPanelOpen(!isPanelOpen)}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg transition-colors"
          >
            <FileText className="w-4 h-4" />
            <span>Documents</span>
            {documents.length > 0 && (
              <span className="px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded">
                {documents.length}
              </span>
            )}
          </button>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="max-w-4xl mx-auto">
            {/* Empty state */}
            {messages.length === 0 && (
              <div className="text-center py-12">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <span className="text-4xl">💬</span>
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                  Comment puis-je vous aider ?
                </h2>
                <p className="text-gray-500 mb-8">
                  Posez-moi une question ou décrivez ce que vous souhaitez faire
                </p>

                {/* Quick actions */}
                <div className="grid grid-cols-2 gap-3 max-w-2xl mx-auto">
                  {[
                    { text: "Analyser une facture", icon: "📄" },
                    { text: "Générer le digest emails", icon: "📧" },
                    { text: "Rechercher un document", icon: "🔍" },
                    { text: "Contacter les copropriétaires", icon: "👥" }
                  ].map((action, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(action.text)}
                      className="p-4 text-left bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 rounded-xl transition-all group"
                    >
                      <div className="text-2xl mb-2">{action.icon}</div>
                      <div className="text-sm font-medium text-gray-700 group-hover:text-gray-900">
                        {action.text}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((message, idx) => (
              <ChatMessage
                key={idx}
                role={message.role}
                content={message.content}
                timestamp={message.timestamp}
                thoughts={message.thoughts}
                sources={message.sources}
                table_data={message.table_data}
                onCopy={() => toast.success('Message copié')}
                onRegenerate={message.role === 'assistant' ? () => toast.info('Régénération (à venir)') : undefined}
              />
            ))}

            {/* Current thinking (streaming) */}
            {isStreaming && currentThoughts.length > 0 && (
              <div className="mb-6">
                <div className="flex items-start gap-3 max-w-[85%]">
                  <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-600 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0 mt-1">
                    AI
                  </div>
                  <div className="flex-1">
                    <ChainOfThoughts
                      thoughts={currentThoughts}
                      isThinking={true}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Suggestions */}
            {messages.length > 0 && messages[messages.length - 1].suggestions && (
              <div className="flex flex-wrap gap-2 mb-6 max-w-[85%]">
                {messages[messages.length - 1].suggestions!.map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="px-4 py-2 text-sm bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 rounded-full transition-colors shadow-sm"
                  >
                    {suggestion.icon && <span className="mr-2">{suggestion.icon}</span>}
                    {suggestion.label}
                  </button>
                ))}
              </div>
            )}

            {/* Confirmation dialog */}
            {pendingConfirmation && (
              <div className="mb-6 max-w-[85%]">
                <div className="bg-amber-50 border-2 border-amber-200 rounded-xl p-5 shadow-sm">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="text-2xl">⚠️</div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-amber-900 mb-2">
                        Confirmation requise
                      </h3>
                      <p className="text-sm text-amber-800 mb-3">
                        {pendingConfirmation.action}
                      </p>
                      <ul className="text-sm text-amber-700 space-y-1">
                        {pendingConfirmation.impact.map((item, i) => (
                          <li key={i}>• {item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => {
                        setInput(`CONFIRMER: ${pendingConfirmation.action}`);
                        setPendingConfirmation(null);
                        handleSend();
                      }}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      Confirmer
                    </button>
                    <button
                      onClick={() => {
                        setPendingConfirmation(null);
                        toast.info('Action annulée');
                      }}
                      className="px-4 py-2 bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium transition-colors"
                    >
                      Annuler
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          placeholder="Posez votre question..."
        />
      </div>

      {/* Right: Document Panel */}
      <DocumentPanel isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />
    </div>
  );
}
