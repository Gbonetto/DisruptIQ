import axios from 'axios'
import type {
  DigestResponse,
  EmailGenerationContext,
  EmailGenerationResponse,
  EmailSuggestion,
  VendorEmailData,
  Email,
  EmailListResponse,
  EmailFilters,
  EmailStatsResponse,
  ChatMessage,
  ChatResponse,
  ChatHistoryResponse,
  DocumentUploadResponse,
  DocumentListResponse,
  NotifyNeighborsData,
  ArchiveDocumentData,
  WebhookResponse,
  AdminStats,
  AdminNotificationsResponse,
  VendorFilters,
  VendorListResponse,
  VendorImportResponse,
} from '@/types/api'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// API functions
export const digestApi = {
  generate: () => api.post<DigestResponse>('/api/digest/generate'),
  generateHtml: () => api.post<{ html: string; message: string }>('/api/digest/generate-html'),
  getLatest: () => api.get<DigestResponse>('/api/digest/latest'),
}

export const emailApi = {
  generate: (prompt: string, context?: EmailGenerationContext) =>
    api.post<EmailGenerationResponse>('/api/email/generate', { prompt, context }),
  generateVendorEmails: (data: VendorEmailData[]) =>
    api.post<{ generated_count: number; emails: EmailGenerationResponse[] }>(
      '/api/email/generate-vendor-emails',
      data
    ),
  getSuggestions: () => api.get<EmailSuggestion[]>('/api/email/suggestions'),
}

export const emailsApi = {
  list: (filters?: EmailFilters) => api.get<EmailListResponse>('/api/emails/', { params: filters }),
  get: (id: number) => api.get<Email>(`/api/emails/${id}`),
  getStats: () => api.get<EmailStatsResponse>('/api/emails/stats/summary'),
  markProcessed: (id: number) => api.patch<{ message: string; email_id: number; processed_at: string }>(`/api/emails/${id}/mark-processed`),
  delete: (id: number) => api.delete<{ message: string; email_id: number }>(`/api/emails/${id}`),
}

export const chatApi = {
  ask: (message: string, history?: ChatMessage[]) =>
    api.post<ChatResponse>('/api/chat/ask', { message, conversation_history: history }),
  getHistory: (sessionId: string) => api.get<ChatHistoryResponse>(`/api/chat/history/${sessionId}`),
  clearHistory: (sessionId: string) => api.delete<{ message: string }>(`/api/chat/history/${sessionId}`),
}

export const documentApi = {
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<DocumentUploadResponse>('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => api.get<DocumentListResponse>('/api/documents/'),
  delete: (id: number) => api.delete<{ message: string }>(`/api/documents/${id}`),
}

export const webhookApi = {
  notifyNeighbors: (data: NotifyNeighborsData) =>
    api.post<WebhookResponse>('/api/webhooks/notify-neighbors', data),
  sendVendorEmails: (data: VendorEmailData[]) =>
    api.post<WebhookResponse>('/api/webhooks/send-vendor-emails', data),
  archiveDocument: (data: ArchiveDocumentData) =>
    api.post<WebhookResponse>('/api/webhooks/archive-document', data),
}

export const adminApi = {
  getStats: () => api.get<AdminStats>('/api/admin/stats'),
  getNotifications: () => api.get<AdminNotificationsResponse>('/api/admin/notifications'),
  importVendors: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<VendorImportResponse>('/api/admin/vendors/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listVendors: (filters?: VendorFilters) =>
    api.get<VendorListResponse>('/api/admin/vendors', { params: filters }),
  reindexVendors: () => api.post<{ message: string; reindexed_count: number }>('/api/admin/vendors/reindex'),

  // Danger Zone - Deletion endpoints
  deleteAllVendors: () =>
    api.delete<{ message: string; deleted_count: number }>('/api/admin/vendors/all', {
      params: { confirm: true },
    }),
  deleteAllDocuments: () =>
    api.delete<{ message: string; deleted_count: number }>('/api/admin/documents/all', {
      params: { confirm: true },
    }),
  deleteAllEmails: () =>
    api.delete<{ message: string; deleted_count: number }>('/api/admin/emails/all', {
      params: { confirm: true },
    }),
  resetAllData: () =>
    api.post<{ message: string }>('/api/admin/reset', null, { params: { confirm: true } }),
}
