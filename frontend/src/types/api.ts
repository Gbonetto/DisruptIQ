/**
 * API Types - DisruptIQ Frontend
 * Types pour toutes les réponses et requêtes API
 */

// ==================== DIGEST ====================
export interface DigestEmail {
  id: number
  subject: string
  sender: string
  received_at: string
  category: string
  priority: string
  summary: string
  action_required: boolean
  related_entities?: string[]
}

export interface DigestSection {
  category: string
  emails: DigestEmail[]
  count: number
}

export interface Digest {
  digest_id: string
  date: string
  total_emails: number
  sections: DigestSection[]
  generated_at: string
}

export interface DigestResponse {
  digest: Digest
  message: string
}

// ==================== EMAIL ====================
export interface EmailGenerationContext {
  vendor_name?: string
  situation?: string
  tone?: 'formal' | 'friendly' | 'urgent'
  [key: string]: unknown
}

export interface EmailGenerationResponse {
  email: string
  subject: string
  confidence: number
}

export interface EmailSuggestion {
  id: number
  title: string
  prompt: string
  category: string
}

export interface VendorEmailData {
  vendor_id: number
  template_type: string
  context?: Record<string, unknown>
}

// ==================== CHAT ====================
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

export interface ChatResponse {
  response: string
  confidence: number
  sources?: string[]
  conversation_id: string
}

export interface ChatHistoryResponse {
  session_id: string
  messages: ChatMessage[]
  created_at: string
}

// ==================== DOCUMENTS ====================
export interface Document {
  id: number
  filename: string
  file_path: string
  file_size: number
  mime_type: string
  uploaded_at: string
  category?: string
  is_indexed: boolean
}

export interface DocumentUploadResponse {
  document: Document
  message: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}

// ==================== VENDORS (Professionnels) ====================
export interface Vendor {
  id: number
  name: string
  company_name: string
  email: string
  phone?: string
  siret?: string
  description?: string
  statut: 'active' | 'inactive' | 'blacklisted'
  category: string
  specialties: string[]
  address?: string
  city?: string
  postal_code?: string
  rating?: number
  total_jobs: number
  is_indexed: boolean
  created_at: string
  updated_at?: string
}

export interface VendorFilters {
  category?: string
  statut?: string
  city?: string
  is_indexed?: boolean
  search?: string
  limit?: number
  offset?: number
}

export interface VendorListResponse {
  vendors: Vendor[]
  total: number
  limit: number
  offset: number
}

export interface VendorImportResponse {
  imported_count: number
  failed_count: number
  errors?: string[]
  message: string
}

// ==================== COPROPRIÉTÉS ====================
export interface Copropriete {
  id: number
  nom: string
  adresse: string
  ville: string
  code_postal: string
  nombre_lots: number
  nombre_batiments: number
  annee_construction?: number
  syndic?: string
  type_copropriete: string
  surface_totale?: number
  equipements: string[]
  is_indexed: boolean
  created_at: string
  updated_at?: string
}

export interface CoproprieteListResponse {
  coproprietes: Copropriete[]
  total: number
}

// ==================== COPROPRIÉTAIRES ====================
export interface Coproprietaire {
  id: number
  nom: string
  prenom: string
  email: string
  telephone?: string
  telephone_mobile?: string
  copropriete_id: number
  copropriete_nom?: string
  numero_lot: string
  type_lot: string
  etage?: number
  surface?: number
  statut: string
  statut_special?: string
  est_resident: boolean
  tantiemes?: number
  created_at: string
  updated_at?: string
}

export interface CoproprietaireListResponse {
  coproprietaires: Coproprietaire[]
  total: number
}

// ==================== ADMIN ====================
export interface AdminStats {
  total_vendors: number
  active_vendors: number
  total_emails: number
  processed_emails: number
  total_documents: number
  indexed_documents: number
  total_coproprietes: number
  total_coproprietaires: number
  cache_hits?: number
  cache_misses?: number
  uptime_seconds: number
}

export interface AdminNotification {
  id: number
  type: 'info' | 'warning' | 'error' | 'success'
  title: string
  message: string
  created_at: string
  read: boolean
}

export interface AdminNotificationsResponse {
  notifications: AdminNotification[]
  unread_count: number
}

// ==================== WEBHOOKS ====================
export interface WebhookResponse {
  success: boolean
  message: string
  workflow_id?: string
  execution_id?: string
}

export interface NotifyNeighborsData {
  title: string
  message: string
  urgency: 'low' | 'medium' | 'high'
  copropriete_id?: number
  send_sms?: boolean
}

export interface ArchiveDocumentData {
  document_id: number
  category: string
  tags?: string[]
}

// ==================== ASSISTANT (SQL Agent) ====================
export interface SQLQueryRequest {
  query: string
  operation_type: 'SELECT' | 'INSERT' | 'UPDATE' | 'DELETE'
}

export interface SQLQueryResponse {
  success: boolean
  query: string
  sql?: string
  explanation?: string
  results?: Record<string, unknown>[]
  row_count?: number
  columns?: string[]
  warnings?: string[]
  error?: string
  validation_errors?: string[]
}

export interface TableStatsResponse {
  table_name: string
  total_rows: number
  indexed_rows?: number
  sample_data?: Record<string, unknown>[]
}

export interface DatabaseSchemaResponse {
  schema: string
  allowed_tables: string[]
  allowed_operations: string[]
  dangerous_operations: string[]
  max_results: number
}

// ==================== ERROR RESPONSES ====================
export interface APIError {
  detail: string
  status_code?: number
  error_code?: string
}

// ==================== HEALTH & MONITORING ====================
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  version: string
  services: {
    database: boolean
    redis: boolean
    qdrant: boolean
  }
}
