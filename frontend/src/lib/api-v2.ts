/**
 * API Service for Assistant V2
 * Handles conversations, streaming SSE, and multi-agent orchestration
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ============================================================================
// TYPES
// ============================================================================

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
  data?: any;
}

export interface Thought {
  id: string;
  type:
    // General phases
    | 'analyzing' | 'classifying' | 'planning' | 'executing' | 'waiting'
    | 'processing' | 'synthesizing' | 'completed' | 'error' | 'warning'
    // SQL Agent
    | 'sql_generating' | 'sql_executing' | 'sql_results'
    // RAG Agent
    | 'rag_searching' | 'rag_retrieving' | 'rag_reranking' | 'rag_results'
    // Web Agent
    | 'web_searching' | 'web_fetching' | 'web_results'
    // Legal Agent
    | 'legal_searching' | 'legal_analyzing' | 'legal_results'
    // Email Agent
    | 'email_drafting' | 'email_sending' | 'email_sent'
    // Workflow Agent (N8N)
    | 'workflow_triggering' | 'workflow_sending' | 'workflow_success' | 'workflow_error'
    // Digest Agent
    | 'digest_fetching' | 'digest_classifying' | 'digest_generating'
    // Table Generation
    | 'table_generating' | 'table_exporting'
    // OCR Agent
    | 'ocr_processing' | 'ocr_extracting'
    // Intent & Fusion
    | 'intent_detected' | 'fusion_combining'
    // Legacy
    | 'searching';
  timestamp: string;
  agent?: string;
  title: string;
  content: string;
  data?: {
    query?: string;         // SQL query
    tables?: string[];      // SQL tables
    rowCount?: number;      // SQL row count
    documents?: string[];   // RAG documents
    chunks?: number;        // RAG chunks count
    url?: string;           // Web URL
    domain?: string;        // Web domain
    domains?: string[];     // Web domains list
    confidence?: number;    // Score
    intent?: string;        // Intent type
    recipients_count?: number; // Email recipients
    subject?: string;       // Email subject
    status?: string;        // Workflow status
    urgent_count?: number;  // Digest urgent count
    important_count?: number; // Digest important count
    routine_count?: number; // Digest routine count
    [key: string]: any;
  };
  progress?: number;
}

export interface Citation {
  id: number;
  type: 'sql' | 'rag' | 'web';
  title: string;
  content: string;
  url?: string;
  metadata?: Record<string, any>;
}

export interface AssistantResponse {
  success: boolean;
  message: string;
  data?: any;
  agents_used?: string[];
  suggestions?: string[];
  sources?: Citation[];
  session_id?: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  session_id: string;
  message_count: number;
  preview?: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant';
  content: string;
  thoughts?: Thought[];
  sources?: Citation[];
  suggestions?: string[];
  data?: any;
  timestamp: string;
}

export interface ConversationWithMessages {
  conversation: Conversation;
  messages: Message[];
}

// ============================================================================
// AXIOS INSTANCE
// ============================================================================

const apiV2 = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
  },
});

// Add auth token if needed
apiV2.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ============================================================================
// ASSISTANT V2 API
// ============================================================================

export const assistantV2Api = {
  /**
   * Send a chat message (non-streaming)
   */
  chat: async (
    message: string,
    conversationHistory: AssistantMessage[] = [],
    sessionId?: string
  ): Promise<AssistantResponse> => {
    const response = await apiV2.post('/api/assistant-v2/chat', {
      message,
      conversation_history: conversationHistory,
      session_id: sessionId,
    });
    return response.data;
  },

  /**
   * Get available capabilities (agents, workflows)
   */
  getCapabilities: async () => {
    const response = await apiV2.get('/api/assistant-v2/capabilities');
    return response.data;
  },

  /**
   * Get available templates
   */
  getTemplates: async () => {
    const response = await apiV2.get('/api/assistant-v2/templates');
    return response.data;
  },

  /**
   * Create SSE connection for streaming chat
   * Returns EventSource instance
   */
  streamChat: (
    message: string,
    conversationHistory: AssistantMessage[] = [],
    sessionId: string = 'default',
    activeDocumentIds: number[] = [],
    selectedSources: string[] = [],
    uiContext?: Record<string, any>  // ← NEW: UI Context for bypass optimization
  ): EventSource => {
    const params = new URLSearchParams({
      message,
      conversation_history: JSON.stringify(conversationHistory),
      session_id: sessionId,
    });

    // Add active document IDs if provided
    if (activeDocumentIds.length > 0) {
      params.append('active_document_ids', JSON.stringify(activeDocumentIds));
    }

    // Add selected sources if provided
    if (selectedSources.length > 0) {
      params.append('selected_sources', JSON.stringify(selectedSources));
    }

    // Add UI context if provided (Sprint 1 - Level 0 Optimization)
    if (uiContext && Object.keys(uiContext).length > 0) {
      params.append('ui_context', JSON.stringify(uiContext));
      console.log('[API] Sending UI context for bypass optimization:', uiContext);
    }

    const eventSource = new EventSource(
      `${API_BASE_URL}/api/assistant-v2/chat/stream?${params.toString()}`
    );

    return eventSource;
  },
};

// ============================================================================
// CONVERSATIONS API
// ============================================================================

export const conversationsApi = {
  /**
   * Create a new conversation
   */
  create: async (title?: string, sessionId?: string): Promise<Conversation> => {
    const response = await apiV2.post('/api/conversations/', {
      title,
      session_id: sessionId,
    });
    return response.data;
  },

  /**
   * List all conversations (most recent first)
   */
  list: async (limit: number = 50, offset: number = 0): Promise<Conversation[]> => {
    const response = await apiV2.get('/api/conversations/', {
      params: { limit, offset },
      headers: { 'Cache-Control': 'no-cache' },  // Prevent stale data after deletion
    });
    return response.data;
  },

  /**
   * Get conversation with all messages
   */
  get: async (conversationId: number): Promise<ConversationWithMessages> => {
    const response = await apiV2.get(`/api/conversations/${conversationId}`);
    return response.data;
  },

  /**
   * Add a message to a conversation
   */
  addMessage: async (
    conversationId: number,
    role: 'user' | 'assistant',
    content: string,
    thoughts?: Thought[],
    sources?: Citation[],
    suggestions?: string[],
    data?: any
  ): Promise<Message> => {
    const response = await apiV2.post(`/api/conversations/${conversationId}/messages`, {
      role,
      content,
      thoughts,
      sources,
      suggestions,
      data,
    });
    return response.data;
  },

  /**
   * Delete a conversation
   */
  delete: async (conversationId: number): Promise<{ success: boolean; message: string }> => {
    const response = await apiV2.delete(`/api/conversations/${conversationId}`);
    return response.data;
  },

  /**
   * Update conversation title
   */
  updateTitle: async (conversationId: number, title: string): Promise<{ success: boolean; title: string }> => {
    const response = await apiV2.put(`/api/conversations/${conversationId}/title`, null, {
      params: { title },
    });
    return response.data;
  },
};

// ============================================================================
// STREAMING HELPERS
// ============================================================================

export interface StreamEventHandlers {
  onThought?: (thought: Thought) => void;
  onResponse?: (response: AssistantResponse) => void;
  onError?: (error: any) => void;
  onClose?: () => void;
}

/**
 * Helper to setup SSE event listeners
 */
export const setupStreamListeners = (
  eventSource: EventSource,
  handlers: StreamEventHandlers
): void => {
  // Track if we've received a successful response
  let responseReceived = false;

  // Log connection status
  eventSource.onopen = () => {
    console.log('[SSE] Connection opened, readyState:', eventSource.readyState);
  };

  // Log ALL messages (including unnamed events)
  eventSource.onmessage = (e: MessageEvent) => {
    console.log('[SSE] Generic message received:', e.data);
  };

  // Handle thought events
  if (handlers.onThought) {
    eventSource.addEventListener('thought', (e: MessageEvent) => {
      try {
        console.log('[SSE] Thought event received:', e.data);
        const thought: Thought = JSON.parse(e.data);
        console.log('[SSE] Parsed thought:', thought);
        handlers.onThought!(thought);
      } catch (error) {
        console.error('Failed to parse thought event:', error, e.data);
      }
    });
  }

  // Handle response event (final message)
  if (handlers.onResponse) {
    eventSource.addEventListener('response', (e: MessageEvent) => {
      try {
        console.log('[SSE] Response event received:', e.data?.substring(0, 200));
        const response: AssistantResponse = JSON.parse(e.data);
        responseReceived = true; // Mark that we got a successful response
        console.log('[SSE] Response parsed successfully');
        handlers.onResponse!(response);
      } catch (error) {
        console.error('Failed to parse response event:', error, e.data);
      }
    });
  }

  // Handle errors
  eventSource.onerror = (e) => {
    console.error('[SSE] Error event:', {
      event: e,
      readyState: eventSource.readyState,
      // 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
      readyStateText: ['CONNECTING', 'OPEN', 'CLOSED'][eventSource.readyState],
      url: eventSource.url,
      responseReceived
    });

    // If we already received a response, this is just a normal connection close
    if (responseReceived) {
      console.log('[SSE] Normal close after response');
      if (handlers.onClose) {
        handlers.onClose();
      }
      return;
    }

    // Otherwise, it's a real error
    console.error('[SSE] Real error - no response received yet');
    if (handlers.onError) {
      handlers.onError(e);
    }
    if (handlers.onClose) {
      handlers.onClose();
    }
  };
};

// ============================================================================
// EXPORT
// ============================================================================

export default {
  assistantV2Api,
  conversationsApi,
  setupStreamListeners,
};
