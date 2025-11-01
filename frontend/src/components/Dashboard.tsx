import { EmailCard } from './EmailCard'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { RefreshCw, Loader2, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { fr } from 'date-fns/locale'
import { toast } from 'sonner'
import { webhookApi } from '@/lib/api'

interface DashboardProps {
  digest: {
    date: string
    total_emails: number
    urgent: { count: number; emails: any[] }
    important: { count: number; emails: any[] }
    routine: { count: number; emails: any[] }
  } | null
  loading: boolean
  onRefresh: () => void
  lastUpdated?: Date | null
}

export function Dashboard({ digest, loading, onRefresh, lastUpdated }: DashboardProps) {
  // N8N Actions handlers
  const handleNotifyNeighbors = async (email: any) => {
    const toastId = toast.loading('Notification des voisins en cours...')
    try {
      await webhookApi.notifyNeighbors({
        email_id: email.id,
        subject: email.subject,
        sender: email.sender,
        body: email.snippet || email.body,
        urgency: email.urgency
      })
      toast.success('✅ Voisins notifiés avec succès!', { id: toastId })
    } catch (error: any) {
      console.error('Notify neighbors failed:', error)
      toast.error(`Erreur: ${error?.response?.data?.detail || 'Échec de la notification'}`, { id: toastId })
    }
  }

  const handleArchiveDocument = async (email: any) => {
    const toastId = toast.loading('Archivage du document...')
    try {
      await webhookApi.archiveDocument({
        email_id: email.id,
        subject: email.subject,
        attachments: email.attachments || []
      })
      toast.success('✅ Document archivé avec succès!', { id: toastId })
    } catch (error: any) {
      console.error('Archive document failed:', error)
      toast.error(`Erreur: ${error?.response?.data?.detail || 'Échec de l\'archivage'}`, { id: toastId })
    }
  }

  const handleSendToVendors = async (email: any) => {
    const toastId = toast.loading('Envoi aux fournisseurs...')
    try {
      await webhookApi.sendVendorEmails({
        email_id: email.id,
        subject: email.subject,
        body: email.snippet || email.body,
        urgency: email.urgency
      })
      toast.success('✅ Emails envoyés aux fournisseurs!', { id: toastId })
    } catch (error: any) {
      console.error('Send to vendors failed:', error)
      toast.error(`Erreur: ${error?.response?.data?.detail || 'Échec de l\'envoi'}`, { id: toastId })
    }
  }

  // Add actions to emails based on urgency
  const enrichEmailWithActions = (email: any) => {
    const actions = []

    if (email.urgency === 'urgent') {
      actions.push({
        id: 'notify-neighbors',
        label: 'Notifier voisins',
        onClick: () => handleNotifyNeighbors(email)
      })
    }

    if (email.urgency === 'important') {
      actions.push({
        id: 'send-vendors',
        label: 'Envoyer aux fournisseurs',
        onClick: () => handleSendToVendors(email)
      })
    }

    if (email.attachments && email.attachments.length > 0) {
      actions.push({
        id: 'archive-document',
        label: 'Archiver document',
        onClick: () => handleArchiveDocument(email)
      })
    }

    return { ...email, actions }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="ml-2">Chargement du digest...</span>
      </div>
    )
  }

  if (!digest) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">
              Aucun digest disponible
            </p>
            <Button onClick={onRefresh}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Générer le digest
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">Digest Quotidien</h1>
          <p className="text-muted-foreground">
            {new Date(digest.date).toLocaleDateString('fr-FR', {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
          </p>
          {lastUpdated && (
            <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
              <Clock className="w-3 h-3" />
              Dernière mise à jour : {formatDistanceToNow(lastUpdated, { locale: fr, addSuffix: true })}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg border border-muted">
          <RefreshCw className="w-4 h-4 text-primary animate-spin" style={{ animationDuration: '3s' }} />
          <div className="text-sm">
            <p className="font-medium">Mise à jour automatique</p>
            <p className="text-xs text-muted-foreground">Toutes les heures</p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-urgent/10 border-urgent/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              🔴 Urgents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{digest.urgent.count}</p>
          </CardContent>
        </Card>

        <Card className="bg-important/10 border-important/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              🟠 Importants
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{digest.important.count}</p>
          </CardContent>
        </Card>

        <Card className="bg-routine/10 border-routine/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              🟢 Routine
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{digest.routine.count}</p>
          </CardContent>
        </Card>
      </div>

      {/* Urgent Emails */}
      {digest.urgent.count > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-4">🔴 Urgents</h2>
          <div className="space-y-4">
            {digest.urgent.emails.map((email: any) => (
              <EmailCard key={email.id || email.message_id} email={enrichEmailWithActions(email)} />
            ))}
          </div>
        </div>
      )}

      {/* Important Emails */}
      {digest.important.count > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-4">🟠 Importants</h2>
          <div className="space-y-4">
            {digest.important.emails.map((email: any) => (
              <EmailCard key={email.id || email.message_id} email={enrichEmailWithActions(email)} />
            ))}
          </div>
        </div>
      )}

      {/* Routine Emails */}
      {digest.routine.count > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-4">🟢 Routine</h2>
          <div className="space-y-4">
            {digest.routine.emails.slice(0, 5).map((email: any) => (
              <EmailCard key={email.id || email.message_id} email={enrichEmailWithActions(email)} />
            ))}
          </div>
          {digest.routine.count > 5 && (
            <p className="text-center text-muted-foreground mt-4">
              + {digest.routine.count - 5} autres emails
            </p>
          )}
        </div>
      )}
    </div>
  )
}
