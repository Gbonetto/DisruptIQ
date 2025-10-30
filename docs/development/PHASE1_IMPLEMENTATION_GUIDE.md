# 🚀 Phase 1 - Guide d'Implémentation Complet

## 📋 Vue d'Ensemble

Ce guide fournit toutes les modifications nécessaires pour implémenter la Phase 1 des finitions V1 :
1. ✅ Toast notifications (Sonner) - INSTALLÉ
2. Danger Zone Admin avec suppressions
3. Recherche + filtres vendors
4. Pagination de la liste
5. Auto-refresh Dashboard
6. Badges de notification

---

## 1. Configuration Sonner (Toast Notifications)

### Installation
```bash
cd frontend
npm install sonner  # ✅ DÉJÀ FAIT
```

### Étape 1.1 : Ajouter le Toaster au Layout Principal

**Fichier** : `frontend/src/App.tsx`

```typescript
import { Toaster } from 'sonner'

function App() {
  return (
    <>
      {/* Existing routes */}
      <Toaster
        position="top-right"
        expand={true}
        richColors
        closeButton
      />
    </>
  )
}
```

### Étape 1.2 : Remplacer les Alerts par des Toasts dans AdminPage

**Fichier** : `frontend/src/pages/AdminPage.tsx`

```typescript
import { toast } from 'sonner'

// Dans handleImportVendors, remplacer:
// alert(message)

// Par:
toast.success('Import réussi !', {
  description: `✅ ${response.data.vendors_created} créés\n🔍 ${response.data.vendors_indexed} indexés`,
  duration: 5000
})

// Pour les erreurs, remplacer:
// alert(`❌ Erreur...`)

// Par:
toast.error('Erreur d\'import', {
  description: errorMessage,
  duration: 7000
})
```

### Étape 1.3 : Toasts dans handleReindexVendors

```typescript
const handleReindexVendors = async () => {
  const confirmed = await new Promise((resolve) => {
    toast('Confirmation requise', {
      description: 'Voulez-vous réindexer tous les fournisseurs ?',
      action: {
        label: 'Confirmer',
        onClick: () => resolve(true)
      },
      cancel: {
        label: 'Annuler',
        onClick: () => resolve(false)
      },
      duration: Infinity
    })
  })

  if (!confirmed) return

  setIsReindexing(true)
  try {
    const response = await adminApi.reindexVendors()

    toast.success('Réindexation terminée', {
      description: `🔍 ${response.data.indexed} fournisseurs indexés`,
      duration: 5000
    })

    window.location.reload()
  } catch (error: any) {
    toast.error('Erreur de réindexation', {
      description: error?.response?.data?.detail || 'Une erreur est survenue',
      duration: 7000
    })
  } finally {
    setIsReindexing(false)
  }
}
```

---

## 2. Danger Zone Admin (Suppressions)

### Étape 2.1 : Ajouter la Section Danger Zone

**Fichier** : `frontend/src/pages/AdminPage.tsx`

Ajouter après la section "Gestion des Fournisseurs" :

```typescript
import { Trash2, AlertTriangle } from 'lucide-react'

// Dans le render, après le dernier </Card>:

{/* Danger Zone */}
<Card className="border-red-200 bg-red-50/30">
  <CardHeader>
    <CardTitle className="text-red-700 flex items-center gap-2">
      <AlertTriangle className="w-5 h-5" />
      Zone Dangereuse
    </CardTitle>
  </CardHeader>
  <CardContent>
    <div className="space-y-4">
      <p className="text-sm text-red-600">
        ⚠️ Les actions ci-dessous sont <strong>irréversibles</strong>. Toutes les données supprimées seront perdues définitivement.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Button
          variant="destructive"
          onClick={handleDeleteAllVendors}
          className="justify-start"
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Supprimer tous les fournisseurs
        </Button>

        <Button
          variant="destructive"
          onClick={handleDeleteAllDocuments}
          className="justify-start"
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Supprimer tous les documents
        </Button>

        <Button
          variant="destructive"
          onClick={handleDeleteAllEmails}
          className="justify-start"
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Supprimer tous les emails
        </Button>

        <Button
          variant="destructive"
          onClick={handleResetAllData}
          className="justify-start bg-red-700 hover:bg-red-800"
        >
          <AlertTriangle className="w-4 h-4 mr-2" />
          RESET COMPLET
        </Button>
      </div>

      <div className="mt-4 p-3 bg-white border border-red-200 rounded">
        <p className="text-xs text-gray-600">
          <strong>Note:</strong> La suppression des fournisseurs efface les données de PostgreSQL ET Qdrant.
          Le reset complet supprime TOUT : vendors, documents, emails.
        </p>
      </div>
    </div>
  </CardContent>
</Card>
```

### Étape 2.2 : Ajouter les Handlers de Suppression

```typescript
const [isDeleting, setIsDeleting] = useState(false)

const handleDeleteAllVendors = async () => {
  const confirmed = await new Promise((resolve) => {
    toast.warning('Supprimer TOUS les fournisseurs ?', {
      description: 'Cette action est irréversible !',
      action: {
        label: 'SUPPRIMER',
        onClick: () => resolve(true)
      },
      cancel: {
        label: 'Annuler',
        onClick: () => resolve(false)
      },
      duration: Infinity
    })
  })

  if (!confirmed) return

  setIsDeleting(true)
  try {
    const response = await adminApi.deleteAllVendors()
    toast.success('Fournisseurs supprimés', {
      description: `${response.data.postgres_deleted} supprimés de PostgreSQL, ${response.data.qdrant_deleted} de Qdrant`
    })
    window.location.reload()
  } catch (error: any) {
    toast.error('Erreur de suppression', {
      description: error?.response?.data?.detail || 'Échec de la suppression'
    })
  } finally {
    setIsDeleting(false)
  }
}

const handleDeleteAllDocuments = async () => {
  const confirmed = await new Promise((resolve) => {
    toast.warning('Supprimer TOUS les documents ?', {
      description: 'Cette action est irréversible !',
      action: {
        label: 'SUPPRIMER',
        onClick: () => resolve(true)
      },
      cancel: {
        label: 'Annuler',
        onClick: () => resolve(false)
      },
      duration: Infinity
    })
  })

  if (!confirmed) return

  setIsDeleting(true)
  try {
    const response = await adminApi.deleteAllDocuments()
    toast.success('Documents supprimés', {
      description: `${response.data.postgres_deleted} documents supprimés`
    })
    window.location.reload()
  } catch (error: any) {
    toast.error('Erreur de suppression', {
      description: error?.response?.data?.detail || 'Échec de la suppression'
    })
  } finally {
    setIsDeleting(false)
  }
}

const handleDeleteAllEmails = async () => {
  const confirmed = await new Promise((resolve) => {
    toast.warning('Supprimer TOUS les emails ?', {
      description: 'Cette action est irréversible !',
      action: {
        label: 'SUPPRIMER',
        onClick: () => resolve(true)
      },
      cancel: {
        label: 'Annuler',
        onClick: () => resolve(false)
      },
      duration: Infinity
    })
  })

  if (!confirmed) return

  setIsDeleting(true)
  try {
    const response = await adminApi.deleteAllEmails()
    toast.success('Emails supprimés', {
      description: `${response.data.postgres_deleted} emails supprimés`
    })
    window.location.reload()
  } catch (error: any) {
    toast.error('Erreur de suppression', {
      description: error?.response?.data?.detail || 'Échec de la suppression'
    })
  } finally {
    setIsDeleting(false)
  }
}

const handleResetAllData = async () => {
  const confirmed = await new Promise((resolve) => {
    toast.error('🚨 RESET COMPLET DU SYSTÈME 🚨', {
      description: 'TOUTES les données seront supprimées définitivement !',
      action: {
        label: 'JE CONFIRME',
        onClick: () => resolve(true)
      },
      cancel: {
        label: 'Annuler',
        onClick: () => resolve(false)
      },
      duration: Infinity
    })
  })

  if (!confirmed) return

  setIsDeleting(true)
  try {
    const response = await adminApi.resetAllData()
    toast.success('Reset complet effectué', {
      description: 'Toutes les données ont été supprimées'
    })
    setTimeout(() => window.location.reload(), 2000)
  } catch (error: any) {
    toast.error('Erreur de reset', {
      description: error?.response?.data?.detail || 'Échec du reset'
    })
  } finally {
    setIsDeleting(false)
  }
}
```

---

## 3. Recherche et Filtres Vendors

### Étape 3.1 : Ajouter l'État de Recherche

**Fichier** : `frontend/src/pages/AdminPage.tsx`

```typescript
const [searchTerm, setSearchTerm] = useState('')
const [selectedCategory, setSelectedCategory] = useState('all')
const [selectedCity, setSelectedCity] = useState('all')

// Filtrer les vendors
const filteredVendors = vendors?.filter((vendor: any) => {
  const matchesSearch =
    vendor.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    vendor.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    vendor.email.toLowerCase().includes(searchTerm.toLowerCase())

  const matchesCategory =
    selectedCategory === 'all' || vendor.category === selectedCategory

  const matchesCity =
    selectedCity === 'all' || vendor.city === selectedCity

  return matchesSearch && matchesCategory && matchesCity
}) || []

// Extraire les catégories et villes uniques
const categories = [...new Set(vendors?.map((v: any) => v.category) || [])]
const cities = [...new Set(vendors?.map((v: any) => v.city) || [])]
```

### Étape 3.2 : Ajouter les Contrôles de Recherche

Avant la table, ajouter :

```typescript
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

// Dans le render, avant la table:

<div className="flex flex-col md:flex-row gap-3 mb-4">
  <div className="relative flex-1">
    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
    <Input
      type="text"
      placeholder="Rechercher par nom, entreprise ou email..."
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      className="pl-10"
    />
  </div>

  <Select value={selectedCategory} onValueChange={setSelectedCategory}>
    <SelectTrigger className="w-full md:w-48">
      <SelectValue placeholder="Catégorie" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">Toutes catégories</SelectItem>
      {categories.map((cat) => (
        <SelectItem key={cat} value={cat}>
          {cat}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>

  <Select value={selectedCity} onValueChange={setSelectedCity}>
    <SelectTrigger className="w-full md:w-48">
      <SelectValue placeholder="Ville" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">Toutes villes</SelectItem>
      {cities.map((city) => (
        <SelectItem key={city} value={city}>
          {city}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
</div>

<p className="text-sm text-gray-600 mb-2">
  {filteredVendors.length} fournisseur(s) trouvé(s)
  {(searchTerm || selectedCategory !== 'all' || selectedCity !== 'all') &&
    ` (sur ${vendors?.length || 0} total)`
  }
</p>
```

### Étape 3.3 : Utiliser filteredVendors dans la Table

Remplacer `vendors.map()` par `filteredVendors.map()` dans le tbody.

---

## 4. Pagination

### Étape 4.1 : Ajouter l'État de Pagination

```typescript
const [currentPage, setCurrentPage] = useState(1)
const [itemsPerPage, setItemsPerPage] = useState(25)

// Calculer la pagination
const indexOfLastItem = currentPage * itemsPerPage
const indexOfFirstItem = indexOfLastItem - itemsPerPage
const currentVendors = filteredVendors.slice(indexOfFirstItem, indexOfLastItem)
const totalPages = Math.ceil(filteredVendors.length / itemsPerPage)
```

### Étape 4.2 : Ajouter les Contrôles de Pagination

Après la table :

```typescript
import { ChevronLeft, ChevronRight } from 'lucide-react'

<div className="flex items-center justify-between mt-4">
  <div className="flex items-center gap-2">
    <span className="text-sm text-gray-600">Afficher:</span>
    <Select
      value={itemsPerPage.toString()}
      onValueChange={(val) => {
        setItemsPerPage(Number(val))
        setCurrentPage(1)
      }}
    >
      <SelectTrigger className="w-20">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="10">10</SelectItem>
        <SelectItem value="25">25</SelectItem>
        <SelectItem value="50">50</SelectItem>
        <SelectItem value="100">100</SelectItem>
      </SelectContent>
    </Select>
  </div>

  <div className="flex items-center gap-2">
    <Button
      variant="outline"
      size="sm"
      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
      disabled={currentPage === 1}
    >
      <ChevronLeft className="w-4 h-4" />
    </Button>

    <span className="text-sm text-gray-600">
      Page {currentPage} sur {totalPages}
    </span>

    <Button
      variant="outline"
      size="sm"
      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
      disabled={currentPage === totalPages}
    >
      <ChevronRight className="w-4 h-4" />
    </Button>
  </div>

  <span className="text-sm text-gray-600">
    {indexOfFirstItem + 1}-{Math.min(indexOfLastItem, filteredVendors.length)} sur {filteredVendors.length}
  </span>
</div>
```

### Étape 4.3 : Utiliser currentVendors dans la Table

Remplacer `filteredVendors.map()` par `currentVendors.map()`.

---

## 5. Auto-refresh Dashboard

**Fichier** : `frontend/src/pages/DashboardPage.tsx`

```typescript
useEffect(() => {
  const loadLatestDigest = async () => {
    // ... existing code
  }

  loadLatestDigest()

  // Auto-refresh every hour
  const intervalId = setInterval(() => {
    console.log('Auto-refreshing digest...')
    loadLatestDigest()
  }, 60 * 60 * 1000) // 1 hour

  // Cleanup on unmount
  return () => clearInterval(intervalId)
}, [])
```

---

## 6. Badges de Notification

### Étape 6.1 : Créer un Hook pour les Stats

**Nouveau fichier** : `frontend/src/hooks/useUrgentCount.ts`

```typescript
import { useState, useEffect } from 'react'
import { digestApi } from '@/lib/api'

export function useUrgentCount() {
  const [urgentCount, setUrgentCount] = useState(0)

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const response = await digestApi.getLatest()
        if (response.data) {
          setUrgentCount(response.data.urgent.count || 0)
        }
      } catch (error) {
        console.error('Failed to fetch urgent count:', error)
      }
    }

    fetchCount()

    // Refresh every 5 minutes
    const interval = setInterval(fetchCount, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  return urgentCount
}
```

### Étape 6.2 : Ajouter le Badge dans la Sidebar

**Fichier** : `frontend/src/components/Layout.tsx` (ou votre fichier de layout)

```typescript
import { useUrgentCount } from '@/hooks/useUrgentCount'

function Sidebar() {
  const urgentCount = useUrgentCount()

  return (
    <nav>
      <Link to="/" className="flex items-center justify-between">
        <span>Dashboard</span>
        {urgentCount > 0 && (
          <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 ml-2">
            {urgentCount}
          </span>
        )}
      </Link>
      {/* ... other links */}
    </nav>
  )
}
```

---

## 🎯 Checklist d'Implémentation

- [ ] Toaster ajouté à App.tsx
- [ ] Tous les alert() remplacés par toast()
- [ ] Danger Zone ajoutée dans AdminPage
- [ ] Handlers de suppression implémentés
- [ ] Recherche vendors fonctionnelle
- [ ] Filtres catégorie/ville fonctionnels
- [ ] Pagination ajoutée
- [ ] Auto-refresh Dashboard (1h)
- [ ] Hook useUrgentCount créé
- [ ] Badges de notification dans sidebar

---

## 🧪 Tests à Effectuer

1. **Toasts**
   - Import CSV → toast de succès
   - Réindexation → toast de confirmation puis succès
   - Erreur → toast d'erreur

2. **Danger Zone**
   - Supprimer vendors → confirmation → suppression
   - Vérifier PostgreSQL ET Qdrant vides

3. **Recherche**
   - Taper "jean" → filtrage instantané
   - Sélectionner catégorie → filtrage
   - Combiner recherche + filtres

4. **Pagination**
   - Changer items/page
   - Naviguer entre pages
   - Vérifier compteurs

5. **Auto-refresh**
   - Attendre 1h → digest se recharge
   - Vérifier console pour "Auto-refreshing..."

6. **Badges**
   - Emails urgents → badge apparaît
   - Nombre correct affiché
   - Rafraîchissement toutes les 5min

---

## 📚 Ressources

- [Sonner Documentation](https://sonner.emilkowal.ski/)
- [Shadcn/ui Components](https://ui.shadcn.com/)
- [React Hooks Guide](https://react.dev/reference/react)

---

**Dernière mise à jour** : 30 octobre 2025
**Statut** : Guide complet Phase 1 - Prêt pour implémentation
