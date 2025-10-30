import { Card, CardContent, CardFooter, CardHeader } from './ui/card'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { formatTimeAgo } from '@/lib/utils'
import { Mail, Paperclip } from 'lucide-react'

interface EmailCardProps {
  email: {
    id: number
    subject: string
    sender: string
    body: string
    snippet?: string
    urgency: 'urgent' | 'important' | 'routine'
    attachments?: Array<{ filename: string }>
    received_at: string
    actions?: Array<{ id: string; label: string; onClick: () => void }>
  }
}

export function EmailCard({ email }: EmailCardProps) {
  const urgencyIcons = {
    urgent: '🔴',
    important: '🟠',
    routine: '🟢',
  }

  return (
    <Card className="hover:shadow-lg transition-all">
      <CardHeader>
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1">
            <Badge variant={email.urgency} className="mb-2">
              <span className="mr-1">{urgencyIcons[email.urgency]}</span>
              {email.urgency.toUpperCase()}
            </Badge>
            <h3 className="font-semibold text-lg">{email.subject}</h3>
          </div>
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {formatTimeAgo(email.received_at)}
          </span>
        </div>
      </CardHeader>

      <CardContent>
        <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
          <Mail className="w-4 h-4" />
          <span>{email.sender}</span>
        </div>

        <p className="text-sm text-foreground line-clamp-3">
          {email.snippet || email.body}
        </p>

        {email.attachments && email.attachments.length > 0 && (
          <div className="flex gap-2 mt-3 flex-wrap">
            {email.attachments.map((att, idx) => (
              <Badge key={idx} variant="outline" className="gap-1">
                <Paperclip className="w-3 h-3" />
                {att.filename}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>

      {email.actions && email.actions.length > 0 && (
        <CardFooter className="gap-2">
          {email.actions.map((action) => (
            <Button
              key={action.id}
              size="sm"
              onClick={action.onClick}
              variant="outline"
            >
              {action.label}
            </Button>
          ))}
        </CardFooter>
      )}
    </Card>
  )
}
