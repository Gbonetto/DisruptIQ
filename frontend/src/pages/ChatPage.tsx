import { useState } from 'react'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Send, Loader2, Sparkles } from 'lucide-react'
import { useChat, useEmailSuggestions } from '@/hooks/useApi'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const chat = useChat()
  const { data: suggestions } = useEmailSuggestions()

  const handleSend = async () => {
    if (!input.trim()) return

    const userMessage: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')

    try {
      const result = await chat.mutateAsync({
        message: input,
        history: messages,
      })

      const assistantMessage: Message = {
        role: 'assistant',
        content: result.message,
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Chat error:', error)
    }
  }

  const handleSuggestionClick = (prompt: string) => {
    setInput(prompt)
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      <Card className="h-[calc(100vh-8rem)]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-primary" />
            Assistant DisruptIQ
          </CardTitle>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground mb-4">
                Posez-moi une question ou générez un email
              </p>

              {suggestions && (
                <div className="space-y-2">
                  <p className="text-sm font-semibold mb-3">Suggestions :</p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {suggestions.suggestions?.map((sug: any) => (
                      <Badge
                        key={sug.id}
                        variant="outline"
                        className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors"
                        onClick={() => handleSuggestionClick(sug.prompt)}
                      >
                        {sug.label}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}

          {chat.isPending && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-4 py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            </div>
          )}
        </CardContent>

        <CardFooter>
          <div className="flex w-full gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Votre message..."
              className="flex-1 px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={chat.isPending}
            />
            <Button onClick={handleSend} disabled={chat.isPending || !input.trim()}>
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}
