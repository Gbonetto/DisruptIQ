import { useState, useEffect } from 'react'
import { Dashboard } from '@/components/Dashboard'
import { useDigest } from '@/hooks/useApi'
import { digestApi } from '@/lib/api'

export function DashboardPage() {
  const [digest, setDigest] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const generateDigest = useDigest()

  // Load latest digest on mount
  useEffect(() => {
    const loadLatestDigest = async () => {
      try {
        setIsLoading(true)
        const result = await digestApi.getLatest()
        if (result.data) {
          setDigest(result.data)
        }
      } catch (error) {
        console.error('Failed to load latest digest:', error)
        // If no digest exists, that's okay - user can generate one
      } finally {
        setIsLoading(false)
      }
    }

    loadLatestDigest()
  }, [])

  const handleGenerateDigest = async () => {
    try {
      const result = await generateDigest.mutateAsync()
      setDigest(result.data)
    } catch (error) {
      console.error('Failed to generate digest:', error)
    }
  }

  return (
    <div className="container mx-auto py-6">
      <Dashboard
        digest={digest}
        loading={isLoading || generateDigest.isPending}
        onRefresh={handleGenerateDigest}
      />
    </div>
  )
}
