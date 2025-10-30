import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { digestApi, emailApi, chatApi, documentApi, adminApi } from '@/lib/api'

// Digest hooks
export const useDigest = () => {
  return useMutation({
    mutationFn: digestApi.generate,
  })
}

export const useLatestDigest = () => {
  return useQuery({
    queryKey: ['digest', 'latest'],
    queryFn: () => digestApi.getLatest().then(res => res.data),
  })
}

// Email generation hooks
export const useGenerateEmail = () => {
  return useMutation({
    mutationFn: ({ prompt, context }: { prompt: string; context?: any }) =>
      emailApi.generate(prompt, context).then(res => res.data),
  })
}

export const useEmailSuggestions = () => {
  return useQuery({
    queryKey: ['email', 'suggestions'],
    queryFn: () => emailApi.getSuggestions().then(res => res.data),
  })
}

// Chat hooks
export const useChat = () => {
  return useMutation({
    mutationFn: ({ message, history }: { message: string; history?: any[] }) =>
      chatApi.ask(message, history).then(res => res.data),
  })
}

// Document hooks
export const useUploadDocument = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => documentApi.upload(file).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export const useDocuments = () => {
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => documentApi.list().then(res => res.data),
  })
}

// Admin hooks
export const useStats = () => {
  return useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => adminApi.getStats().then(res => res.data),
  })
}

export const useVendors = (filters?: any) => {
  return useQuery({
    queryKey: ['vendors', filters],
    queryFn: () => adminApi.listVendors(filters).then(res => res.data),
  })
}

export const useImportVendors = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => adminApi.importVendors(file).then(res => res.data),
    onSuccess: () => {
      // Refresh vendors list and stats after successful import
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] })
    },
  })
}
