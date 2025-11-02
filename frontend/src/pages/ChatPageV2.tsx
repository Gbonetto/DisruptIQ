/**
 * ChatPage V2 - Multi-Agent Assistant with Chain of Thoughts
 * Real-time streaming of AI reasoning (DeepSeek-style)
 */

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, Sparkles, Copy, RefreshCw } from 'lucide-react';
import { ChainOfThoughts } from '@/components/ChainOfThoughts';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  agents_used?: string[];
  suggestions?: string[];
  thoughts?: Thought[];
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

export function ChatPageV2() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentThoughts, setCurrentThoughts] = useState<Thought[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentThoughts]);

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
      // Use Server-Sent Events for streaming
      const eventSource = new EventSource(
        `${API_BASE_URL}/api/assistant-v2/chat/stream?` +
        new URLSearchParams({
          message: input,
          conversation_history: JSON.stringify(messages.slice(-5).map(m => ({
            role: m.role,
            content: m.content
          })))
        })
      );

      eventSourceRef.current = eventSource;

      // Handle thought events
      eventSource.addEventListener('thought', (e) => {
        const thought: Thought = JSON.parse(e.data);
        setCurrentThoughts(prev => [...prev, thought]);
      });

      // Handle final response
      eventSource.addEventListener('response', (e) => {
        const response = JSON.parse(e.data);

        const assistantMessage: Message = {
          role: 'assistant',
          content: response.message,
          agents_used: response.agents_used,
          suggestions: response.suggestions,
          thoughts: currentThoughts,
          timestamp: new Date()
        };

        setMessages(prev => [...prev, assistantMessage]);
        setCurrentThoughts([]);
        setIsStreaming(false);
        eventSource.close();
      });

      // Handle errors
      eventSource.addEventListener('error', (e) => {
        console.error('SSE Error:', e);
        toast.error('Erreur de connexion au streaming');
        setIsStreaming(false);
        eventSource.close();
      });

      eventSource.onerror = () => {
        setIsStreaming(false);
        eventSource.close();
      };

    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Erreur lors de l\'envoi du message');
      setIsStreaming(false);
    }
  };

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsStreaming(false);
      setCurrentThoughts([]);
      toast.info('Traitement arrêté');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copié dans le presse-papier');
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  return (
    <div className="container mx-auto py-6 max-w-5xl">
      <Card className="h-[calc(100vh-8rem)] flex flex-col">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-purple-600" />
              Assistant Multi-Agent DisruptIQ
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              Chain of Thoughts • v2.0
            </Badge>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Assistant intelligent avec raisonnement transparent
          </p>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <Sparkles className="w-16 h-16 text-purple-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-4">
                Posez-moi une question ou demandez-moi d'effectuer une action
              </p>
              <div className="grid grid-cols-2 gap-2 max-w-2xl mx-auto">
                {[
                  "Combien de copropriétaires dans l'Immeuble A?",
                  "Envoyer email pour dégât des eaux",
                  "Demander devis aux jardiniers",
                  "Procédure assemblée générale"
                ].map((example, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    size="sm"
                    onClick={() => setInput(example)}
                    className="text-left justify-start"
                  >
                    {example}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, idx) => (
            <div key={idx}>
              {/* User Message */}
              {message.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="bg-purple-600 text-white rounded-lg px-4 py-3 max-w-[80%]">
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <p className="text-xs text-purple-200 mt-1">
                      {message.timestamp.toLocaleTimeString('fr-FR')}
                    </p>
                  </div>
                </div>
              ) : (
                /* Assistant Message */
                <div className="flex flex-col gap-2">
                  {/* Chain of Thoughts */}
                  {message.thoughts && message.thoughts.length > 0 && (
                    <ChainOfThoughts
                      thoughts={message.thoughts}
                      isThinking={false}
                      collapsed={true}
                    />
                  )}

                  {/* Response */}
                  <div className="bg-gray-100 rounded-lg px-4 py-3 max-w-[90%]">
                    <div className="flex items-start justify-between mb-2">
                      <p className="text-sm whitespace-pre-wrap flex-1">{message.content}</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(message.content)}
                        className="ml-2"
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>

                    {/* Agents Used */}
                    {message.agents_used && message.agents_used.length > 0 && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        <span className="text-xs text-gray-500">Agents:</span>
                        {message.agents_used.map((agent, i) => (
                          <Badge key={i} variant="secondary" className="text-xs">
                            {agent.replace('_', ' ')}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {/* Suggestions */}
                    {message.suggestions && message.suggestions.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <p className="text-xs text-gray-500 font-medium">Suggestions:</p>
                        <div className="flex flex-wrap gap-2">
                          {message.suggestions.map((suggestion, i) => (
                            <Button
                              key={i}
                              variant="outline"
                              size="sm"
                              onClick={() => handleSuggestionClick(suggestion)}
                              className="text-xs"
                            >
                              {suggestion}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}

                    <p className="text-xs text-gray-400 mt-2">
                      {message.timestamp.toLocaleTimeString('fr-FR')}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Current Thoughts (while streaming) */}
          {isStreaming && currentThoughts.length > 0 && (
            <ChainOfThoughts
              thoughts={currentThoughts}
              isThinking={true}
            />
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        <CardFooter className="border-t p-4">
          <div className="flex w-full gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Posez votre question..."
              className="flex-1 px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              disabled={isStreaming}
            />

            {isStreaming ? (
              <Button onClick={handleStop} variant="destructive">
                <RefreshCw className="w-4 h-4 mr-2" />
                Arrêter
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!input.trim()}>
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>

          {isStreaming && (
            <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Assistant en train de réfléchir...</span>
            </div>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}

export default ChatPageV2;
