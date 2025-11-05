/**
 * MainChatPage - Interface Unifiée Style ChatGPT/DeepSeek/Le Chat
 * Interface ultra-simple : juste un chat, rien de superflu
 */

import { useState, useRef, useEffect } from 'react';
import { FileText, X } from 'lucide-react';
import { toast } from 'sonner';
import { DocumentPanel } from '@/components/DocumentPanel/DocumentPanel';
import { ConversationSidebar } from '@/components/chat/ConversationSidebar';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  thoughts?: Thought[];
  sources?: Source[];
  suggestions?: Suggestion[];
  confirmation_required?: ConfirmationData;
  table_data?: any[];  // Données tabulaires pour rendu avec DataTable
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
    <div
      className="flex flex-col h-screen bg-white relative"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Document Panel */}
      <DocumentPanel isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />

      {/* Drag & Drop Overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-blue-50 bg-opacity-90 z-50 flex items-center justify-center border-4 border-dashed border-blue-500">
          <div className="text-center">
            <div className="text-6xl mb-4">📁</div>
            <div className="text-2xl font-semibold text-blue-600">Déposez vos fichiers ici</div>
            <div className="text-sm text-blue-500 mt-2">PDF, Word, Excel, Images (max 10MB)</div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">
            D
          </div>
          <h1 className="font-semibold text-gray-900">DisruptIQ</h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500">Assistant Intelligent</div>
          <button
            onClick={() => setIsPanelOpen(!isPanelOpen)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-colors"
          >
            <FileText className="w-4 h-4" />
            <span>Documents</span>
            {documents.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs font-medium bg-indigo-100 text-indigo-700 rounded">
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
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <div className="text-3xl">💬</div>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Comment puis-je vous aider ?
              </h2>
              <p className="text-gray-500 mb-6">
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
                    className="p-3 text-left text-sm text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, idx) => (
            <div key={idx} className={`${message.role === 'user' ? 'flex justify-end' : ''}`}>
              {message.role === 'user' ? (
                /* User message */
                <div className="bg-blue-600 text-white rounded-2xl px-4 py-3 max-w-[80%]">
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>
              ) : (
                /* Assistant message */
                <div className="space-y-3 max-w-full">
                  {/* Chain of Thoughts */}
                  {message.thoughts && message.thoughts.length > 0 && (
                    <ChainOfThoughts
                      thoughts={message.thoughts}
                      isThinking={false}
                      collapsed={true}
                    />
                  )}

                  {/* Main response with Rich Markdown */}
                  <RichMarkdownRenderer content={message.content} />

                  {/* Data Table if present */}
                  {message.table_data && message.table_data.length > 0 && (
                    <DataTable
                      data={message.table_data}
                      caption="Résultats"
                      enableExport={true}
                      enableSearch={true}
                      enableSort={true}
                    />
                  )}

                  {/* Sources with elegant footnote style */}
                  <SourceCitation sources={message.sources || []} />

                  {/* Contextual suggestions */}
                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {message.suggestions.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => handleSuggestionClick(suggestion)}
                          className="px-3 py-1.5 text-sm bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 rounded-full transition-colors"
                        >
                          {suggestion.icon && <span className="mr-1">{suggestion.icon}</span>}
                          {suggestion.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Confirmation required */}
                  {message.confirmation_required && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-3">
                      <div className="flex items-start gap-2">
                        <div className="text-amber-600 mt-0.5">⚠️</div>
                        <div className="flex-1">
                          <div className="font-medium text-amber-900 mb-1">
                            Confirmation requise
                          </div>
                          <div className="text-sm text-amber-800 mb-2">
                            {message.confirmation_required.action}
                          </div>
                          <div className="text-xs text-amber-700 space-y-1">
                            {message.confirmation_required.impact.map((item, i) => (
                              <div key={i}>• {item}</div>
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={handleConfirm}
                          className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium"
                        >
                          Confirmer
                        </button>
                        <button
                          onClick={handleCancel}
                          className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg text-sm font-medium"
                        >
                          Annuler
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Current thinking (streaming) */}
          {isStreaming && currentThoughts.length > 0 && (
            <ChainOfThoughts
              thoughts={currentThoughts}
              isThinking={true}
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area - Fixed at bottom */}
      <div className="border-t border-gray-200 bg-white">
        <div className="max-w-3xl mx-auto px-4 py-4">
          {/* Upload progress */}
          {Object.keys(uploadProgress).length > 0 && (
            <div className="mb-3 space-y-2">
              {Object.entries(uploadProgress).map(([fileName, progress]) => (
                <div key={fileName} className="bg-blue-50 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-blue-900">{fileName}</span>
                    <span className="text-xs text-blue-600">{Math.round(progress)}%</span>
                  </div>
                  <div className="w-full bg-blue-200 rounded-full h-1.5">
                    <div
                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
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
                <div key={i} className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                  <FileText className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-900">{file.preview}</span>
                  <button onClick={() => removeFile(i)} className="text-green-400 hover:text-green-600">
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
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
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
                className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-2xl focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none"
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
                className="p-3 bg-red-600 hover:bg-red-700 text-white rounded-xl transition-colors"
              >
                <div className="w-4 h-4 bg-white rounded-sm" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() && uploadedFiles.length === 0}
                className="p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Hint text */}
          <div className="mt-2 text-xs text-gray-400 text-center">
            Tapez votre demande en langage naturel • Shift + Enter pour nouvelle ligne
          </div>
        </div>
      </div>
    </div>
  );
}

export default MainChatPage;
