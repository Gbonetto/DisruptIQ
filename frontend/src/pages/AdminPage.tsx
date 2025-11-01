import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/pagination'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { useStats, useVendors } from '@/hooks/useApi'
import { adminApi } from '@/lib/api'
import { Upload, Users, FileText, Mail, Database, AlertCircle, RefreshCw, Search, Trash2, AlertTriangle } from 'lucide-react'
import { useState, useMemo, useEffect } from 'react'
import { toast } from 'sonner'

export function AdminPage() {
  const { data: stats, error: statsError } = useStats()
  const { data: vendors, error: vendorsError, isLoading: vendorsLoading } = useVendors()
  const [isReindexing, setIsReindexing] = useState(false)

  // Search and filter state
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [indexedFilter, setIndexedFilter] = useState<string>('all')

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  // Danger Zone - Dialog states
  const [deleteVendorsDialog, setDeleteVendorsDialog] = useState(false)
  const [deleteDocumentsDialog, setDeleteDocumentsDialog] = useState(false)
  const [deleteEmailsDialog, setDeleteEmailsDialog] = useState(false)
  const [resetAllDialog, setResetAllDialog] = useState(false)
  const [reindexDialog, setReindexDialog] = useState(false)
  const [isDangerActionLoading, setIsDangerActionLoading] = useState(false)

  // Debounce search term (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm)
    }, 300)

    return () => clearTimeout(timer)
  }, [searchTerm])

  // Get unique categories for filter dropdown
  const categories = useMemo<string[]>(() => {
    if (!vendors) return []
    const uniqueCategories = new Set<string>(vendors.map((v: any) => v.category).filter(Boolean))
    return Array.from(uniqueCategories).sort()
  }, [vendors])

  // Filter vendors based on search and filters
  const filteredVendors = useMemo(() => {
    if (!vendors) return []

    return vendors.filter((vendor: any) => {
      // Search filter (name, email, company, category)
      const searchLower = debouncedSearchTerm.toLowerCase()
      const matchesSearch = !searchLower ||
        vendor.name?.toLowerCase().includes(searchLower) ||
        vendor.email?.toLowerCase().includes(searchLower) ||
        vendor.company_name?.toLowerCase().includes(searchLower) ||
        vendor.category?.toLowerCase().includes(searchLower)

      // Category filter
      const matchesCategory = categoryFilter === 'all' || vendor.category === categoryFilter

      // Indexed status filter
      const matchesIndexed =
        indexedFilter === 'all' ||
        (indexedFilter === 'indexed' && vendor.is_indexed) ||
        (indexedFilter === 'not_indexed' && !vendor.is_indexed)

      return matchesSearch && matchesCategory && matchesIndexed
    })
  }, [vendors, debouncedSearchTerm, categoryFilter, indexedFilter])

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchTerm, categoryFilter, indexedFilter])

  // Paginate filtered vendors
  const paginatedVendors = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return filteredVendors.slice(startIndex, endIndex)
  }, [filteredVendors, currentPage, itemsPerPage])

  // Calculate total pages
  const totalPages = Math.ceil(filteredVendors.length / itemsPerPage)

  const handleReindexVendors = async () => {
    setIsReindexing(true)
    setReindexDialog(false)
    const toastId = toast.loading('Réindexation en cours...')

    try {
      const response = await adminApi.reindexVendors()
      console.log('Reindex successful:', response.data)

      toast.success(
        `Réindexation terminée! ${response.data.indexed} fournisseur(s) indexé(s)${response.data.failed > 0 ? ` · ${response.data.failed} erreur(s)` : ''}`,
        { id: toastId, duration: 5000 }
      )

      // Refresh the page to show updated statuses
      setTimeout(() => window.location.reload(), 1500)
    } catch (error: any) {
      console.error('Reindex failed:', error)
      toast.error(
        `Erreur de réindexation: ${error?.response?.data?.detail || 'Une erreur est survenue'}`,
        { id: toastId }
      )
    } finally {
      setIsReindexing(false)
    }
  }

  const handleImportVendors = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.csv'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        const toastId = toast.loading(`Import de ${file.name} en cours...`)

        try {
          console.log('Importing vendors:', file.name)
          const response = await adminApi.importVendors(file)
          console.log('Import successful:', response.data)

          // Build detailed success message
          let message = `Import réussi!\n\n`
          message += `✅ ${response.data.vendors_created} fournisseur(s) créé(s)\n`

          if (response.data.vendors_skipped > 0) {
            message += `⏭️ ${response.data.vendors_skipped} fournisseur(s) ignoré(s) (déjà existant et indexé)\n`
          }

          if (response.data.vendors_reindexed > 0) {
            message += `🔄 ${response.data.vendors_reindexed} fournisseur(s) réindexé(s) (existait mais pas dans Qdrant)\n`
          }

          if (response.data.vendors_indexed !== undefined) {
            message += `🔍 ${response.data.vendors_indexed} fournisseur(s) indexé(s) pour l'assistant\n`
          }

          if (response.data.index_errors > 0) {
            message += `⚠️ ${response.data.index_errors} erreur(s) d'indexation\n`
          }

          if (response.data.error_count > 0) {
            message += `\n⚠️ ${response.data.error_count} erreur(s) d'import détectée(s)`
          }

          toast.success(message, {
            id: toastId,
            duration: 6000,
            style: { whiteSpace: 'pre-line' }
          })

          // Refresh the page to show new vendors
          setTimeout(() => window.location.reload(), 1500)
        } catch (error: any) {
          console.error('Import failed:', error)
          const errorMessage = error?.response?.data?.detail || 'Erreur lors de l\'import du fichier CSV. Vérifiez le format du fichier.'
          toast.error(`Erreur d'import: ${errorMessage}`, {
            id: toastId,
            duration: 8000
          })
        }
      }
    }
    input.click()
  }

  // Danger Zone - Delete handlers
  const handleDeleteAllVendors = async () => {
    setIsDangerActionLoading(true)
    const toastId = toast.loading('Suppression de tous les fournisseurs...')

    try {
      const response = await adminApi.deleteAllVendors()
      console.log('Delete vendors successful:', response.data)

      toast.success(
        `✅ ${response.data.postgres_deleted || 0} fournisseur(s) supprimé(s)\n🗄️ PostgreSQL et Qdrant vidés`,
        { id: toastId, duration: 5000, style: { whiteSpace: 'pre-line' } }
      )

      setDeleteVendorsDialog(false)
      setTimeout(() => window.location.reload(), 1500)
    } catch (error: any) {
      console.error('Delete vendors failed:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Une erreur est survenue'
      toast.error(
        `Erreur de suppression: ${errorMessage}`,
        { id: toastId }
      )
    } finally {
      setIsDangerActionLoading(false)
    }
  }

  const handleDeleteAllDocuments = async () => {
    setIsDangerActionLoading(true)
    const toastId = toast.loading('Suppression de tous les documents...')

    try {
      const response = await adminApi.deleteAllDocuments()
      console.log('Delete documents successful:', response.data)

      toast.success(
        `✅ ${response.data.postgres_deleted || 0} document(s) supprimé(s)\n🗄️ Base de données vidée`,
        { id: toastId, duration: 5000, style: { whiteSpace: 'pre-line' } }
      )

      setDeleteDocumentsDialog(false)
      setTimeout(() => window.location.reload(), 1500)
    } catch (error: any) {
      console.error('Delete documents failed:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Une erreur est survenue'
      toast.error(
        `Erreur de suppression: ${errorMessage}`,
        { id: toastId }
      )
    } finally {
      setIsDangerActionLoading(false)
    }
  }

  const handleDeleteAllEmails = async () => {
    setIsDangerActionLoading(true)
    const toastId = toast.loading('Suppression de tous les emails...')

    try {
      const response = await adminApi.deleteAllEmails()
      console.log('Delete emails successful:', response.data)

      toast.success(
        `✅ ${response.data.postgres_deleted || 0} email(s) supprimé(s)\n🗄️ Base de données vidée`,
        { id: toastId, duration: 5000, style: { whiteSpace: 'pre-line' } }
      )

      setDeleteEmailsDialog(false)
      setTimeout(() => window.location.reload(), 1500)
    } catch (error: any) {
      console.error('Delete emails failed:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Une erreur est survenue'
      toast.error(
        `Erreur de suppression: ${errorMessage}`,
        { id: toastId }
      )
    } finally {
      setIsDangerActionLoading(false)
    }
  }

  const handleResetAllData = async () => {
    setIsDangerActionLoading(true)
    const toastId = toast.loading('⚠️ Réinitialisation complète du système...')

    try {
      const response = await adminApi.resetAllData()
      console.log('Reset all data successful:', response.data)

      const details = response.data.details || {}
      let message = `🔥 Réinitialisation complète terminée!\n\n`

      if (details.vendors?.postgres_deleted) {
        message += `✅ ${details.vendors.postgres_deleted} fournisseur(s) supprimé(s)\n`
      }
      if (details.documents?.postgres_deleted) {
        message += `✅ ${details.documents.postgres_deleted} document(s) supprimé(s)\n`
      }
      if (details.emails?.postgres_deleted) {
        message += `✅ ${details.emails.postgres_deleted} email(s) supprimé(s)\n`
      }

      toast.success(message, { id: toastId, duration: 6000, style: { whiteSpace: 'pre-line' } })

      setResetAllDialog(false)
      setTimeout(() => window.location.reload(), 2000)
    } catch (error: any) {
      console.error('Reset all data failed:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Une erreur est survenue'
      toast.error(
        `Erreur de réinitialisation: ${errorMessage}`,
        { id: toastId }
      )
    } finally {
      setIsDangerActionLoading(false)
    }
  }

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-3xl font-bold mb-6">Administration</h1>

      {/* Error display for stats */}
      {statsError && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-800">
          <AlertCircle className="w-5 h-5" />
          <span>Erreur de chargement des statistiques: {(statsError as any)?.message || 'Erreur inconnue'}</span>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Emails</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_emails || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_documents || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Fournisseurs</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_vendors || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Utilisateurs</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_users || 1}</div>
          </CardContent>
        </Card>
      </div>

      {/* Vendor Management */}
      <Card>
        <CardHeader>
          <CardTitle>Gestion des Fournisseurs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex gap-2">
              <Button onClick={handleImportVendors}>
                <Upload className="w-4 h-4 mr-2" />
                Importer CSV
              </Button>
              <Button
                onClick={() => setReindexDialog(true)}
                variant="outline"
                disabled={isReindexing}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isReindexing ? 'animate-spin' : ''}`} />
                {isReindexing ? 'Réindexation...' : 'Réindexer tout'}
              </Button>
            </div>

            {/* Search and Filters */}
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
              <div className="relative flex-1 w-full">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Rechercher par nom, email, entreprise, catégorie..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex gap-2 w-full sm:w-auto">
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="w-full sm:w-[180px] h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="all">Toutes catégories</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                <select
                  value={indexedFilter}
                  onChange={(e) => setIndexedFilter(e.target.value)}
                  className="w-full sm:w-[160px] h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="all">Tous statuts</option>
                  <option value="indexed">Indexés</option>
                  <option value="not_indexed">Non indexés</option>
                </select>
              </div>
            </div>

            {/* Results count */}
            {vendors && vendors.length > 0 && (
              <div className="text-sm text-muted-foreground">
                {filteredVendors.length === vendors.length ? (
                  <span>{vendors.length} fournisseur(s) total</span>
                ) : (
                  <span>
                    {filteredVendors.length} sur {vendors.length} fournisseur(s)
                  </span>
                )}
              </div>
            )}

            {/* Error display for vendors */}
            {vendorsError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-800">
                <AlertCircle className="w-5 h-5" />
                <span>Erreur de chargement des fournisseurs: {(vendorsError as any)?.message || 'Erreur inconnue'}</span>
              </div>
            )}

            {/* Loading state */}
            {vendorsLoading && (
              <div className="text-center py-8 text-muted-foreground">
                Chargement des fournisseurs...
              </div>
            )}

            {/* Vendors table */}
            {!vendorsLoading && !vendorsError && (
              <div className="border rounded-lg overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-muted">
                    <tr>
                      <th className="px-4 py-2 text-left">Nom</th>
                      <th className="px-4 py-2 text-left">Entreprise</th>
                      <th className="px-4 py-2 text-left">Catégorie</th>
                      <th className="px-4 py-2 text-left">Email</th>
                      <th className="px-4 py-2 text-center">Indexé</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedVendors && paginatedVendors.length > 0 ? (
                      paginatedVendors.map((vendor: any) => (
                        <tr key={vendor.id} className="border-t">
                          <td className="px-4 py-2">{vendor.name}</td>
                          <td className="px-4 py-2">{vendor.company_name}</td>
                          <td className="px-4 py-2">{vendor.category}</td>
                          <td className="px-4 py-2">{vendor.email}</td>
                          <td className="px-4 py-2 text-center">
                            {vendor.is_indexed ? (
                              <span className="inline-flex items-center gap-1 text-green-600 text-sm">
                                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                                Oui
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-orange-600 text-sm">
                                <span className="w-2 h-2 bg-orange-500 rounded-full"></span>
                                Non
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                          {vendors && vendors.length > 0
                            ? 'Aucun résultat pour cette recherche.'
                            : 'Aucun fournisseur. Importez un fichier CSV pour commencer.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {filteredVendors.length > 0 && (
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={filteredVendors.length}
                itemsPerPage={itemsPerPage}
                onPageChange={setCurrentPage}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="mt-8 border-destructive">
        <CardHeader className="bg-destructive/5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <CardTitle className="text-destructive">Danger Zone</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground mb-6">
              Ces actions sont <strong>irréversibles</strong> et supprimeront définitivement les données de la base de données. Utilisez avec précaution.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Delete All Vendors */}
              <div className="p-4 border border-destructive/20 rounded-lg bg-destructive/5">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Trash2 className="h-4 w-4" />
                  Supprimer tous les fournisseurs
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Supprime tous les fournisseurs de PostgreSQL et Qdrant ({stats?.total_vendors || 0} fournisseur(s))
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteVendorsDialog(true)}
                  disabled={!stats?.total_vendors}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Supprimer les fournisseurs
                </Button>
              </div>

              {/* Delete All Documents */}
              <div className="p-4 border border-destructive/20 rounded-lg bg-destructive/5">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Trash2 className="h-4 w-4" />
                  Supprimer tous les documents
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Supprime tous les documents de la base de données ({stats?.total_documents || 0} document(s))
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteDocumentsDialog(true)}
                  disabled={!stats?.total_documents}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Supprimer les documents
                </Button>
              </div>

              {/* Delete All Emails */}
              <div className="p-4 border border-destructive/20 rounded-lg bg-destructive/5">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Trash2 className="h-4 w-4" />
                  Supprimer tous les emails
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Supprime tous les emails de la base de données ({stats?.total_emails || 0} email(s))
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteEmailsDialog(true)}
                  disabled={!stats?.total_emails}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Supprimer les emails
                </Button>
              </div>

              {/* Reset All Data */}
              <div className="p-4 border border-destructive rounded-lg bg-destructive/10">
                <h3 className="font-semibold mb-2 flex items-center gap-2 text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                  Réinitialisation complète
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  <strong>ATTENTION :</strong> Supprime TOUTES les données (vendors, documents, emails)
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setResetAllDialog(true)}
                  className="bg-red-600 hover:bg-red-700"
                >
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Réinitialiser tout
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation Dialogs */}
      <ConfirmDialog
        open={deleteVendorsDialog}
        onOpenChange={setDeleteVendorsDialog}
        onConfirm={handleDeleteAllVendors}
        title="Supprimer tous les fournisseurs ?"
        description={`Vous êtes sur le point de supprimer ${stats?.total_vendors || 0} fournisseur(s) de PostgreSQL et Qdrant. Cette action est irréversible. Voulez-vous continuer ?`}
        confirmText="Oui, supprimer"
        cancelText="Annuler"
        isLoading={isDangerActionLoading}
      />

      <ConfirmDialog
        open={deleteDocumentsDialog}
        onOpenChange={setDeleteDocumentsDialog}
        onConfirm={handleDeleteAllDocuments}
        title="Supprimer tous les documents ?"
        description={`Vous êtes sur le point de supprimer ${stats?.total_documents || 0} document(s) de la base de données. Cette action est irréversible. Voulez-vous continuer ?`}
        confirmText="Oui, supprimer"
        cancelText="Annuler"
        isLoading={isDangerActionLoading}
      />

      <ConfirmDialog
        open={deleteEmailsDialog}
        onOpenChange={setDeleteEmailsDialog}
        onConfirm={handleDeleteAllEmails}
        title="Supprimer tous les emails ?"
        description={`Vous êtes sur le point de supprimer ${stats?.total_emails || 0} email(s) de la base de données. Cette action est irréversible. Voulez-vous continuer ?`}
        confirmText="Oui, supprimer"
        cancelText="Annuler"
        isLoading={isDangerActionLoading}
      />

      <ConfirmDialog
        open={resetAllDialog}
        onOpenChange={setResetAllDialog}
        onConfirm={handleResetAllData}
        title="⚠️ RÉINITIALISATION COMPLÈTE ⚠️"
        description={`ATTENTION : Vous êtes sur le point de supprimer TOUTES les données :\n\n• ${stats?.total_vendors || 0} fournisseur(s)\n• ${stats?.total_documents || 0} document(s)\n• ${stats?.total_emails || 0} email(s)\n\nCette action est IRRÉVERSIBLE et videra complètement la base de données. Êtes-vous absolument certain ?`}
        confirmText="Oui, tout supprimer"
        cancelText="Non, annuler"
        isLoading={isDangerActionLoading}
      />

      <ConfirmDialog
        open={reindexDialog}
        onOpenChange={setReindexDialog}
        onConfirm={handleReindexVendors}
        title="Réindexer tous les fournisseurs ?"
        description={`Vous êtes sur le point de réindexer tous les fournisseurs (${stats?.total_vendors || 0}) dans Qdrant. Cette opération peut prendre quelques secondes. Voulez-vous continuer ?`}
        confirmText="Oui, réindexer"
        cancelText="Annuler"
        variant="default"
        isLoading={isReindexing}
      />
    </div>
  )
}
