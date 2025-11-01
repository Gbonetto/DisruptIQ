import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { digestApi, emailApi, chatApi, documentApi, adminApi } from '@/lib/api'
import type {
  DigestResponse,
  EmailGenerationContext,
  EmailGenerationResponse,
  EmailSuggestion,
  ChatMessage,
  ChatResponse,
  DocumentUploadResponse,
  DocumentListResponse,
  AdminStats,
  VendorFilters,
  VendorListResponse,
  VendorImportResponse,
} from '@/types/api'

// Digest hooks
export const useDigest = () => {
  return useMutation({
    mutationFn: digestApi.generate,
  })
}

export const useLatestDigest = () => {
  return useQuery<DigestResponse>({
    queryKey: ['digest', 'latest'],
    queryFn: () => digestApi.getLatest().then(res => res.data),
  })
}

// Email generation hooks
export const useGenerateEmail = () => {
  return useMutation<EmailGenerationResponse, Error, { prompt: string; context?: EmailGenerationContext }>({
    mutationFn: ({ prompt, context }) =>
      emailApi.generate(prompt, context).then(res => res.data),
  })
}

export const useEmailSuggestions = () => {
  return useQuery<EmailSuggestion[]>({
    queryKey: ['email', 'suggestions'],
    queryFn: () => emailApi.getSuggestions().then(res => res.data),
  })
}

// Chat hooks
export const useChat = () => {
  return useMutation<ChatResponse, Error, { message: string; history?: ChatMessage[] }>({
    mutationFn: ({ message, history }) =>
      chatApi.ask(message, history).then(res => res.data),
  })
}

// Document hooks
export const useUploadDocument = () => {
  const queryClient = useQueryClient()

  return useMutation<DocumentUploadResponse, Error, File>({
    mutationFn: (file: File) => documentApi.upload(file).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export const useDocuments = () => {
  return useQuery<DocumentListResponse>({
    queryKey: ['documents'],
    queryFn: () => documentApi.list().then(res => res.data),
  })
}

// Admin hooks
export const useStats = () => {
  return useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: () => adminApi.getStats().then(res => res.data),
  })
}

export const useVendors = (filters?: VendorFilters) => {
  return useQuery<VendorListResponse>({
    queryKey: ['vendors', filters],
    queryFn: () => adminApi.listVendors(filters).then(res => res.data),
  })
}

export const useImportVendors = () => {
  const queryClient = useQueryClient()

  return useMutation<VendorImportResponse, Error, File>({
    mutationFn: (file: File) => adminApi.importVendors(file).then(res => res.data),
    onSuccess: () => {
      // Refresh vendors list and stats after successful import
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] })
    },
  })
}
