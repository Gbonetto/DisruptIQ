/**
 * AssistantPage - AI Assistant interface with RAG and SQL modes
 * Interact with the intelligent assistant for property management
 */

import React, { useState } from 'react';
import { Bot, Send, Loader2, Sparkles, MessageSquare, User, Database, FileSearch } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { chatApi, api } from '@/lib/api';

type AssistantMode = 'rag' | 'sql';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: Array<{ text: string; metadata?: { title?: string; [key: string]: any } }>;
  sqlQuery?: string;
  tableData?: any[];
}

const quickActionsRAG = [
  {
    label: 'Résumer les derniers emails',
    prompt: 'Peux-tu me faire un résumé des emails importants reçus aujourd\'hui ?',
  },
  {
    label: 'Trouver un plombier',
    prompt: 'Je cherche un plombier disponible rapidement pour une urgence.',
  },
  {
    label: 'Statut des copropriétés',
    prompt: 'Quel est le statut actuel de toutes mes copropriétés ?',
  },
  {
    label: 'Générer un rapport',
    prompt: 'Peux-tu générer un rapport mensuel des activités ?',
  },
];

const quickActionsSQL = [
  {
    label: 'Nombre total d\'emails',
    prompt: 'Combien d\'emails avons-nous en base de données ?',
  },
  {
    label: 'Emails urgents',
    prompt: 'Liste les 10 derniers emails urgents',
  },
  {
    label: 'Professionnels actifs',
    prompt: 'Combien de professionnels actifs avons-nous ?',
  },
  {
    label: 'Documents récents',
    prompt: 'Liste les 5 derniers documents uploadés',
  },
];

export const AssistantPage: React.FC = () => {
  const [mode, setMode] = useState<AssistantMode>('rag');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Bonjour ! Je suis votre assistant IA pour la gestion de copropriétés. Comment puis-je vous aider aujourd\'hui ?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationHistory, setConversationHistory] = useState<any[]>([]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const userInput = input;
    setInput('');
    setIsLoading(true);

    try {
      if (mode === 'rag') {
        // RAG Mode - Use /api/chat/ask
        // Backend returns: { message: string, sources: array, session_id: string }
        const response = await chatApi.ask(userInput, conversationHistory);

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.message || 'Désolé, je n\'ai pas pu générer une réponse.',
          timestamp: new Date(),
          sources: response.data.sources || [],
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // Update conversation history
        setConversationHistory(prev => [
          ...prev,
          { role: 'user', content: userInput },
          { role: 'assistant', content: response.data.message },
        ]);

      } else {
        // SQL Mode - Use /api/assistant/sql-query
        const response = await api.post('/api/assistant/sql-query', {
          query: userInput,
          operation_type: 'SELECT',
        });

        const data = response.data;

        let content = '';
        if (data.success) {
          if (data.explanation) {
            content = data.explanation + '\n\n';
          }
          if (data.results && data.results.length > 0) {
            content += `📊 Résultats (${data.row_count} ligne${data.row_count > 1 ? 's' : ''})`;
          } else {
            content += 'Aucun résultat trouvé.';
          }
        } else {
          content = data.error || 'Erreur lors de l\'exécution de la requête SQL.';
        }

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content,
          timestamp: new Date(),
          sqlQuery: data.sql,
          tableData: data.results || [],
        };

        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (error: any) {
      console.error('Error sending message:', error);

      let errorContent = 'Désolé, une erreur s\'est produite. Veuillez réessayer.';

      if (error.response?.data?.detail) {
        errorContent = error.response.data.detail;
      } else if (error.name === 'AbortError') {
        errorContent = 'La réponse a pris trop de temps. L\'assistant IA peut être temporairement indisponible.';
      }

      toast.error('Erreur lors de la communication avec l\'assistant');

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: errorContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAction = (prompt: string) => {
    setInput(prompt);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleModeChange = (newMode: AssistantMode) => {
    setMode(newMode);
    setMessages([
      {
        id: Date.now().toString(),
        role: 'assistant',
        content: newMode === 'rag'
          ? 'Mode RAG activé. Je peux maintenant répondre à vos questions en utilisant vos documents indexés et l\'IA.'
          : 'Mode SQL activé. Je peux maintenant interroger directement votre base de données avec des requêtes SQL naturelles.',
        timestamp: new Date(),
      },
    ]);
    setConversationHistory([]);
  };

  const quickActions = mode === 'rag' ? quickActionsRAG : quickActionsSQL;

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Bot className="h-8 w-8 text-purple-600" />
          Assistant IA
        </h1>
        <p className="text-gray-500 mt-1">
          Posez vos questions et obtenez des réponses intelligentes sur votre gestion immobilière
        </p>
      </div>

      {/* Mode Selector */}
      <Card className="border-purple-200 bg-purple-50">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-purple-900 mb-1">Mode de l'assistant</p>
              <p className="text-sm text-purple-700">
                {mode === 'rag'
                  ? 'Recherche dans vos documents avec l\'IA (RAG)'
                  : 'Requêtes SQL sur votre base de données'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant={mode === 'rag' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleModeChange('rag')}
                className={mode === 'rag' ? 'bg-purple-600' : ''}
              >
                <FileSearch className="h-4 w-4 mr-2" />
                RAG
              </Button>
              <Button
                variant={mode === 'sql' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleModeChange('sql')}
                className={mode === 'sql' ? 'bg-blue-600' : ''}
              >
                <Database className="h-4 w-4 mr-2" />
                SQL
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Messages échangés</CardDescription>
            <CardTitle className="text-3xl">{messages.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Mode actuel</CardDescription>
            <CardTitle className="text-xl">
              <Badge
                variant="success"
                className={`flex items-center gap-1 w-fit ${mode === 'rag' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}
              >
                {mode === 'rag' ? <FileSearch className="h-3 w-3" /> : <Database className="h-3 w-3" />}
                {mode === 'rag' ? 'RAG' : 'SQL'}
              </Badge>
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Modèle IA</CardDescription>
            <CardTitle className="text-lg text-gray-600">GPT-4</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Chat Interface */}
      <Card className="flex-1 flex flex-col min-h-[500px]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Conversation
          </CardTitle>
          <CardDescription>
            {mode === 'rag'
              ? 'L\'assistant utilise vos documents indexés pour répondre précisément'
              : 'L\'assistant génère des requêtes SQL pour interroger votre base de données'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col gap-4">
          {/* Messages */}
          <ScrollArea className="flex-1 pr-4">
            <div className="space-y-4">
              {messages.map((message) => (
                <div key={message.id}>
                  <div
                    className={`flex gap-3 ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                        <Bot className="h-4 w-4 text-purple-600" />
                      </div>
                    )}
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-900'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                      {/* SQL Query display */}
                      {message.sqlQuery && (
                        <div className="mt-2 p-2 bg-gray-800 text-green-400 rounded text-xs font-mono">
                          SQL: {message.sqlQuery}
                        </div>
                      )}

                      {/* Table data display */}
                      {message.tableData && message.tableData.length > 0 && (
                        <div className="mt-2 overflow-x-auto">
                          <table className="min-w-full text-xs border border-gray-300">
                            <thead className="bg-gray-200">
                              <tr>
                                {Object.keys(message.tableData[0]).map((key) => (
                                  <th key={key} className="px-2 py-1 border border-gray-300 text-left font-semibold">
                                    {key}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {message.tableData.slice(0, 10).map((row, idx) => (
                                <tr key={idx} className="hover:bg-gray-50">
                                  {Object.values(row).map((val: any, vidx) => (
                                    <td key={vidx} className="px-2 py-1 border border-gray-300">
                                      {String(val)}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {message.tableData.length > 10 && (
                            <p className="text-xs text-gray-500 mt-1">
                              ... et {message.tableData.length - 10} ligne(s) supplémentaire(s)
                            </p>
                          )}
                        </div>
                      )}

                      {/* Sources display */}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-2 text-xs text-gray-600">
                          <p className="font-semibold">Sources:</p>
                          <ul className="list-disc list-inside">
                            {message.sources.map((source, idx) => (
                              <li key={idx}>
                                {source.metadata?.title || 'Document'}: {source.text.substring(0, 100)}...
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <p
                        className={`text-xs mt-1 ${
                          message.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                        }`}
                      >
                        {message.timestamp.toLocaleTimeString('fr-FR', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                    {message.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                        <User className="h-4 w-4 text-blue-600" />
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                    <Bot className="h-4 w-4 text-purple-600" />
                  </div>
                  <div className="bg-gray-100 rounded-lg p-3">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-600" />
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Quick Actions */}
          {messages.length === 1 && (
            <div className="space-y-2">
              <p className="text-sm text-gray-600 font-medium">Actions rapides :</p>
              <div className="grid grid-cols-2 gap-2">
                {quickActions.map((action, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    onClick={() => handleQuickAction(action.prompt)}
                    className="text-left justify-start h-auto py-2"
                  >
                    <Sparkles className="h-3 w-3 mr-2 flex-shrink-0" />
                    <span className="text-xs">{action.label}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Posez votre question... (Entrée pour envoyer, Shift+Entrée pour nouvelle ligne)"
              className="min-h-[60px] max-h-[120px]"
              disabled={isLoading}
            />
            <Button
              onClick={handleSendMessage}
              disabled={isLoading || !input.trim()}
              className="h-[60px]"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Info */}
      <Card className="border-purple-200 bg-purple-50">
        <CardContent className="p-4">
          <p className="text-sm text-purple-900">
            <strong>💡 Conseil :</strong> {mode === 'rag'
              ? 'L\'assistant RAG recherche dans vos documents indexés pour vous donner des réponses précises et contextuelles.'
              : 'L\'assistant SQL peut interroger votre base de données avec un langage naturel. Demandez des statistiques, des listes, des comptes, etc.'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
