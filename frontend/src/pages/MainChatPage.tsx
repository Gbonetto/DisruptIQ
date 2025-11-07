/**
 * MainChatPage - Interface Unifiée Style ChatGPT/DeepSeek/Le Chat
 * Interface ultra-simple : juste un chat, rien de superflu
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, FileText, X } from 'lucide-react';
import { ChainOfThoughts } from '@/components/ChainOfThoughts';
import { ConversationSidebar } from '@/components/ConversationSidebar';
import { toast } from 'sonner';
import { MessageRenderer } from '@/components/MessageRenderer';
import { DocumentPanel } from '@/components/DocumentPanel/DocumentPanel';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  thoughts?: Thought[];
  sources?: Source[];
  suggestions?: Suggestion[];
  confirmation_required?: ConfirmationData;
  data?: any;  // Store response data (email_draft, emails_available, etc.)
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

interface UploadedFile {
  file: File;
  preview: string;
  documentId?: number;  // Backend document ID for tracking
  filename?: string;     // Sanitized filename from backend
}

export function MainChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentThoughts, setCurrentThoughts] = useState<Thought[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationData | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [conversations, setConversations] = useState<any[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load documents count for header badge
  useEffect(() => {
    const loadDocs = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/documents/');
        const data = await response.json();
        setDocuments(data.documents || []);
      } catch (error) {
        console.error('Failed to load documents count:', error);
      }
    };
    loadDocs();
    // Reload every 5 seconds to keep count updated
    const interval = setInterval(loadDocs, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load conversations
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/`);
        const data = await response.json();
        setConversations(data || []);
      } catch (error) {
        console.error('Failed to load conversations:', error);
      }
    };
    loadConversations();
  }, []);

  // Conversation handlers
  const handleNewConversation = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Nouvelle conversation' })
      });
      const newConv = await response.json();
      setConversations(prev => [newConv, ...prev]);
      setCurrentConversationId(newConv.id);
      setMessages([]);
      toast.success('Nouvelle conversation créée');
    } catch (error) {
      console.error('Failed to create conversation:', error);
      toast.error('Erreur lors de la création');
    }
  };

  const handleSelectConversation = async (id: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`);
      const data = await response.json();
      setCurrentConversationId(id);
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Failed to load conversation:', error);
      toast.error('Erreur lors du chargement');
    }
  };

  const handleRenameConversation = async (id: number, newTitle: string) => {
    try {
      await fetch(`${API_BASE_URL}/api/conversations/${id}/title?title=${encodeURIComponent(newTitle)}`, {
        method: 'PUT'
      });
      setConversations(prev =>
        prev.map(c => c.id === id ? { ...c, title: newTitle } : c)
      );
      toast.success('Conversation renommée');
    } catch (error) {
      console.error('Failed to rename conversation:', error);
      toast.error('Erreur lors du renommage');
    }
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
        method: 'DELETE'
      });
      setConversations(prev => prev.filter(c => c.id !== id));
      if (currentConversationId === id) {
        setCurrentConversationId(undefined);
        setMessages([]);
      }
      toast.success('Conversation supprimée');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      toast.error('Erreur lors de la suppression');
    }
  };

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentThoughts]);

  // Drag & drop handlers (désactivé si panel ouvert)
  const handleDragEnter = (e: React.DragEvent) => {
    if (isPanelOpen) return; // Ne pas intercepter si panel ouvert
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (isPanelOpen) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (isPanelOpen) return;
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    if (isPanelOpen) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    validateAndAddFiles(files);
  };

  // File validation and upload
  const validateAndAddFiles = async (files: File[]) => {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv',
      'text/plain',
      'image/jpeg',
      'image/png',
      'image/jpg'
    ];

    for (const file of files) {
      // Validate size
      if (file.size > maxSize) {
        toast.error(`${file.name} est trop volumineux (max 10MB)`);
        continue;
      }

      // Validate type
      if (!allowedTypes.includes(file.type)) {
        toast.error(`${file.name} n'est pas un type de fichier autorisé`);
        continue;
      }

      // Upload file to backend
      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));

        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            setUploadProgress(prev => ({ ...prev, [file.name]: percentComplete }));
          }
        });

        xhr.addEventListener('load', () => {
          if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            setUploadedFiles(prev => [...prev, {
              file,
              preview: file.name,
              documentId: response.document_id,
              filename: response.filename
            }]);
            setUploadProgress(prev => {
              const newProgress = { ...prev };
              delete newProgress[file.name];
              return newProgress;
            });
            toast.success(`✅ ${file.name} uploadé et indexé`, {
              description: "Vous pouvez maintenant l'interroger",
              duration: 3000
            });
          } else {
            toast.error(`Erreur lors du téléchargement de ${file.name}`);
            setUploadProgress(prev => {
              const newProgress = { ...prev };
              delete newProgress[file.name];
              return newProgress;
            });
          }
        });

        xhr.addEventListener('error', () => {
          toast.error(`Erreur réseau lors du téléchargement de ${file.name}`);
          setUploadProgress(prev => {
            const newProgress = { ...prev };
            delete newProgress[file.name];
            return newProgress;
          });
        });

        xhr.open('POST', `${API_BASE_URL}/api/documents/upload?session_id=default`);
        xhr.send(formData);

      } catch (error) {
        console.error('Upload error:', error);
        toast.error(`Erreur lors du téléchargement de ${file.name}`);
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[file.name];
          return newProgress;
        });
      }
    }
  };

  // Handle file upload from input
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    validateAndAddFiles(files);
  };

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Send message
  const handleSend = async () => {
    if ((!input.trim() && uploadedFiles.length === 0) || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: input || `📎 ${uploadedFiles.length} fichier(s)`,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setCurrentThoughts([]);

    try {
      // Prepare request with files if any
      let messageToSend = input;

      // NOTE: Files are already uploaded in validateAndAddFiles() during drag & drop or file select
      // Here we just add a reference to the uploaded files in the message if user didn't type anything
      if (uploadedFiles.length > 0 && !messageToSend.trim()) {
        const fileNames = uploadedFiles.map(f => f.file.name).join(', ');
        messageToSend = `J'ai uploadé ${uploadedFiles.length} document(s): ${fileNames}. De quoi parle${uploadedFiles.length > 1 ? 'nt' : ''}-il${uploadedFiles.length > 1 ? 's' : ''} ?`;
      }

      // Stream SSE
      const eventSource = new EventSource(
        `${API_BASE_URL}/api/assistant-v2/chat/stream?` +
        new URLSearchParams({
          message: messageToSend,
          session_id: 'default',  // Use default session for state tracking
          conversation_history: JSON.stringify(messages.slice(-5).map(m => ({
            role: m.role,
            content: m.content,
            data: m.data  // Include data for context preservation (email_draft, emails_available, etc.)
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

        // Filter and validate thoughts before adding to message
        const validThoughts = currentThoughts.filter(t =>
          t && typeof t === 'object' && t.id && t.title && t.content
        );

        const assistantMessage: Message = {
          role: 'assistant',
          content: response.message || '',
          thoughts: validThoughts.length > 0 ? validThoughts : undefined,
          sources: Array.isArray(response.sources) ? response.sources : undefined,
          suggestions: Array.isArray(response.suggestions) ? response.suggestions : undefined,
          data: response.data,  // Store full response data for context preservation
          timestamp: new Date()
        };

        setMessages(prev => [...prev, assistantMessage]);
        setCurrentThoughts([]);
        setUploadedFiles([]);
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

  const handleConfirm = () => {
    if (pendingConfirmation) {
      setInput(`CONFIRMER: ${pendingConfirmation.action}`);
      setPendingConfirmation(null);
      handleSend();
    }
  };

  const handleCancel = () => {
    setPendingConfirmation(null);
    toast.info('Action annulée');
  };

  return (
    <div className="flex h-screen bg-retro-dark">
      {/* Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Chat Area */}
      <div
        className="flex-1 flex flex-col bg-retro-dark relative"
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Document Panel */}
        <DocumentPanel isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />

      {/* Drag & Drop Overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-retro-dark bg-opacity-95 z-50 flex items-center justify-center neon-border-cyan animate-neon-pulse">
          <div className="text-center">
            <div className="text-6xl mb-4 animate-pixel-fade-in">📁</div>
            <div className="text-2xl font-semibold text-neon-cyan neon-glow-cyan font-pixel">Déposez vos fichiers ici</div>
            <div className="text-sm text-gray-400 mt-2">PDF, Word, Excel, Images (max 10MB)</div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-neon-violet/30 px-4 py-3 flex items-center justify-between bg-retro-gray/50 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 retro-gradient-cyber rounded-lg flex items-center justify-center text-white font-bold pixel-border-sm animate-pixel-fade-in">
            D
          </div>
          <h1 className="font-semibold text-white text-lg">DisruptIQ</h1>
          <span className="text-neon-cyan text-xs font-pixel ml-2">v2.0</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-400 font-pixel">Assistant Intelligent</div>
          <button
            onClick={() => setIsPanelOpen(!isPanelOpen)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-retro-gray border border-neon-violet/50 rounded-lg hover-neon-violet transition-colors"
          >
            <FileText className="w-4 h-4" />
            <span>Documents</span>
            {documents.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs font-medium bg-neon-violet/20 text-neon-violet rounded pixel-border-sm">
                {documents.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="w-16 h-16 retro-gradient-cyber rounded-full flex items-center justify-center mx-auto mb-4 pixel-border animate-pixel-fade-in">
                <div className="text-3xl">💬</div>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2 neon-glow-cyan">
                Comment puis-je vous aider ?
              </h2>
              <p className="text-gray-400 mb-6">
                Posez-moi une question ou décrivez ce que vous souhaitez faire
              </p>

              {/* Quick examples */}
              <div className="grid grid-cols-2 gap-3 max-w-2xl mx-auto">
                {[
                  "Vérifier cette facture de plomberie",
                  "Générer le digest des emails",
                  "Contacter tous les copropriétaires",
                  "Chercher la procédure dégât des eaux"
                ].map((example, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(example)}
                    className="p-3 text-left text-sm text-white bg-retro-gray border border-neon-violet/30 hover-neon-violet rounded-lg transition-colors pixel-corners animate-pixel-fade-in"
                    style={{ animationDelay: `${i * 0.1}s` }}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, idx) => (
            <div key={idx} className={`${message.role === 'user' ? 'flex justify-end' : ''} animate-pixel-fade-in`}>
              {message.role === 'user' ? (
                /* User message */
                <div className="retro-gradient-sunset text-white rounded-2xl px-4 py-3 max-w-[80%] neon-border-pink">
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>
              ) : (
                /* Assistant message - Clean structure with MessageRenderer */
                <article className="assistant-message" data-message-id={idx}>
                  <MessageRenderer
                    message={message.content}
                    isStreaming={false}
                  />
                </article>
              )}
            </div>
          ))}

          {/* Current thinking (streaming) - Only show if there's no content yet */}
          {isStreaming && currentThoughts.length > 0 && (
            <div className="animate-pixel-fade-in">
              <ChainOfThoughts
                thoughts={currentThoughts}
                isThinking={true}
              />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area - Fixed at bottom */}
      <div className="border-t border-neon-violet/30 bg-retro-gray/50 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto px-4 py-4">
          {/* Upload progress */}
          {Object.keys(uploadProgress).length > 0 && (
            <div className="mb-3 space-y-2">
              {Object.entries(uploadProgress).map(([fileName, progress]) => (
                <div key={fileName} className="bg-retro-gray rounded-lg px-3 py-2 border border-neon-cyan/50">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-white">{fileName}</span>
                    <span className="text-xs text-neon-cyan font-pixel">{Math.round(progress)}%</span>
                  </div>
                  <div className="w-full bg-retro-dark rounded-full h-1.5">
                    <div
                      className="bg-neon-cyan h-1.5 rounded-full transition-all duration-300 animate-neon-pulse"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Uploaded files */}
          {uploadedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {uploadedFiles.map((file, i) => (
                <div key={i} className="flex items-center gap-2 bg-retro-gray border border-neon-green/50 rounded-lg px-3 py-2 pixel-border-sm animate-pixel-fade-in">
                  <FileText className="w-4 h-4 text-neon-green" />
                  <span className="text-sm text-white">{file.preview}</span>
                  <button onClick={() => removeFile(i)} className="text-gray-400 hover:text-neon-pink transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input box */}
          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.jpg,.jpeg,.png"
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-gray-400 hover:text-neon-cyan hover:bg-retro-gray rounded-lg transition-colors border border-transparent hover:border-neon-cyan/50"
              disabled={isStreaming}
            >
              <Paperclip className="w-5 h-5" />
            </button>

            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Posez votre question ou décrivez votre demande..."
                className="w-full px-4 py-3 pr-12 bg-retro-gray text-white border border-neon-violet/50 rounded-2xl focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan resize-none placeholder-gray-500 transition-all"
                rows={1}
                disabled={isStreaming}
                style={{
                  minHeight: '48px',
                  maxHeight: '200px',
                  height: 'auto'
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = target.scrollHeight + 'px';
                }}
              />
            </div>

            {isStreaming ? (
              <button
                onClick={handleStop}
                className="p-3 bg-neon-pink hover:animate-neon-pulse text-white rounded-xl transition-colors pixel-border-sm"
              >
                <div className="w-4 h-4 bg-white rounded-sm" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() && uploadedFiles.length === 0}
                className="p-3 retro-gradient-cyber text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:animate-neon-pulse pixel-border-sm"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Hint text */}
          <div className="mt-2 text-xs text-gray-500 text-center font-pixel">
            Tapez votre demande en langage naturel • Shift + Enter pour nouvelle ligne
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}

export default MainChatPage;
