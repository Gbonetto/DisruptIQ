import { EmailCard } from './EmailCard'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { RefreshCw, Loader2 } from 'lucide-react'

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
}

export function Dashboard({ digest, loading, onRefresh }: DashboardProps) {
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
      <div className="flex justify-between items-center">
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
        </div>
        <Button onClick={onRefresh} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Actualiser
        </Button>
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
              <EmailCard key={email.id || email.message_id} email={email} />
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
              <EmailCard key={email.id || email.message_id} email={email} />
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
              <EmailCard key={email.id || email.message_id} email={email} />
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
