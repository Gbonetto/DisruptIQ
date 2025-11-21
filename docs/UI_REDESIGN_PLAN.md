# 🎨 UI/UX Redesign Plan - Style Claude.ai

**Date**: 7 Novembre 2025
**Status**: PRÊT À DÉMARRER
**Objectif**: Interface minimaliste, sobre et élégante inspirée de Claude.ai

---

## ✅ Préparation Complète

### Backend
- ✅ Optimisations critiques complétées (-400ms latency, -50MB memory)
- ✅ Intent Classifier V4 implémenté
- ✅ Tous les changements commités et pushés
- ✅ Backend testé et fonctionnel (health endpoint OK)

### Frontend Actuel
- **Stack**: React + TypeScript + Vite + Tailwind + Radix UI
- **State**: Zustand
- **Animations**: Framer Motion
- **Structure**:
  - `MainChatPage.tsx` - Page principale de chat
  - `ConversationSidebar` - Historique conversations (left panel)
  - `DocumentPanel` - Gestionnaire documents (right panel)
  - `ChainOfThoughts` - CoT actuel
  - `MessageRenderer` - Rendu messages

---

## 🎯 Objectifs du Redesign

### Design System Cible
**Inspiré de Claude.ai et de l'image fournie (Script UI)**

#### Couleurs Pastel
```css
:root {
  /* Background */
  --background: 250 60% 98%;        /* Lavande très pâle #F8F7FC */
  --foreground: 240 10% 10%;         /* Presque noir doux #1A1A1F */

  /* Primary (accents) */
  --primary: 245 55% 65%;            /* Lavande moyen #8B8FD8 */
  --primary-foreground: 250 100% 99%; /* Blanc cassé */

  /* Secondary (backgrounds) */
  --secondary: 250 30% 95%;          /* Lavande ultra-pâle #EFEFF5 */
  --secondary-foreground: 240 8% 15%; /* Gris foncé */

  /* Muted (textes secondaires) */
  --muted: 250 20% 92%;              /* Gris-lavande #E8E8EE */
  --muted-foreground: 240 5% 45%;    /* Gris moyen #6E6E7A */

  /* Accent (highlights) */
  --accent: 280 50% 90%;             /* Rose-lavande pâle #E8D5F2 */
  --accent-foreground: 280 40% 30%;  /* Violet foncé */

  /* Bordures */
  --border: 250 20% 90%;             /* Bordure douce #E3E3EA */
  --ring: 245 55% 65%;               /* Focus ring lavande */

  /* Radius */
  --radius: 0.75rem;                 /* 12px - coins arrondis généreux */
}
```

#### Typographie
```css
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  letter-spacing: -0.011em; /* Légèrement condensé */
}

h1, h2, h3 { font-weight: 600; }
p { font-weight: 400; }
```

### Layout Structure

#### Header
```
┌─────────────────────────────────────────────────────────┐
│  Logo DisruptIQ              [Toggle Documents] 📄      │
│  60px height, minimal, background-secondary             │
└─────────────────────────────────────────────────────────┘
```

#### Main Layout
```
┌──────────┬───────────────────────────┬──────────────┐
│          │                           │              │
│  Left    │       Center              │    Right     │
│  Panel   │       Chat                │    Panel     │
│  280px   │       max-w-800px         │    320px     │
│          │       centered            │    (slide)   │
│          │                           │              │
│  History │   Smart Cards (empty)     │   Document   │
│  + User  │   Messages                │   Manager    │
│          │   Input Bar               │              │
│          │                           │              │
└──────────┴───────────────────────────┴──────────────┘
```

### Composants à Créer

#### 1. CollapsibleCoT.tsx
```typescript
// Chain of Thought collapsable façon DeepSeek
interface CoTStep {
  id: string;
  title: string;
  content: string;
  status: 'pending' | 'active' | 'completed';
  timestamp: string;
}

// Features:
// - Animation progressive des étapes
// - Collapsable avec bouton "Show thinking"
// - Progress bar
// - Timestamps
```

#### 2. SourceCitation.tsx
```typescript
// Citations façon universitaire [1] [2]
interface Citation {
  id: number;
  type: 'sql' | 'rag' | 'web';
  title: string;
  content: string;
  url?: string;
}

// Features:
// - Numéros cliquables dans le texte
// - Footer avec liste des sources
// - Hover preview
```

#### 3. DataTable.tsx
```typescript
// Tableaux HTML simples avec export
interface TableData {
  headers: string[];
  rows: string[][];
  title?: string;
}

// Features:
// - Rendu HTML simple et sobre
// - Bouton "Export CSV"
// - Bouton "Export Excel"
// - Tri colonnes
// - Pagination si > 50 lignes
```

#### 4. SmartCard.tsx
```typescript
// Cards suggestions initiales
interface SmartCard {
  icon: string;
  title: string;
  description: string;
  action: () => void;
}

// Features:
// - Hover effect doux
// - Icône colorée (pastel)
// - Click pour remplir l'input
```

---

## 📋 Plan d'Exécution (4 Phases)

### Phase 1: Couleurs & CSS (30 min)
**Fichiers à modifier** :
- `frontend/src/index.css` - Mettre à jour les variables CSS
- `frontend/tailwind.config.cjs` - Ajouter couleurs pastel custom

**Actions** :
1. Copier les nouvelles variables CSS dans `:root`
2. Ajuster le dark mode (optionnel pour l'instant)
3. Tester en local (npm run dev)

### Phase 2: Structure Layout (1h)
**Fichiers à créer** :
- `frontend/src/components/v2/Layout/Header.tsx`
- `frontend/src/components/v2/Layout/LeftPanel.tsx`
- `frontend/src/components/v2/Layout/RightPanel.tsx`
- `frontend/src/components/v2/Layout/MainLayout.tsx`

**Actions** :
1. Créer le dossier `/components/v2/`
2. Implémenter les 3 panels avec les bonnes dimensions
3. Header minimal avec logo + toggle button
4. Tester responsive

### Phase 3: Composants Core (2h)
**Fichiers à créer** :
- `frontend/src/components/v2/CollapsibleCoT.tsx`
- `frontend/src/components/v2/SourceCitation.tsx`
- `frontend/src/components/v2/DataTable.tsx`
- `frontend/src/components/v2/SmartCard.tsx`

**Actions** :
1. Implémenter chaque composant individuellement
2. Stories Storybook si possible (optionnel)
3. Tester avec mock data

### Phase 4: Intégration (1h)
**Fichiers à modifier** :
- `frontend/src/pages/MainChatPageV3.tsx` (nouveau fichier)

**Actions** :
1. Créer MainChatPageV3 avec les nouveaux composants
2. Connecter au backend existant (AUCUN changement backend)
3. Migrer la logique de MainChatPage vers V3
4. Tester end-to-end

---

## 🚨 Points d'Attention

### Ce qu'on NE touche PAS
- ❌ Backend (déjà optimisé et testé)
- ❌ API endpoints (aucun changement)
- ❌ Fichiers dans `/pages/` sauf MainChatPage
- ❌ Logique métier existante

### Ce qu'on peut installer
- ✅ Nouvelles libs CSS si nécessaire (ex: `cmdk` déjà installé)
- ✅ Icônes Lucide (déjà installé)
- ✅ Export libs (jsPDF, xlsx déjà installés)

### Tests à faire
1. ✅ Backend health check avant de commencer
2. ✅ Vérifier que npm run dev fonctionne
3. ✅ Tester chaque composant isolément
4. ✅ Test end-to-end avec vraies données

---

## 📦 Assets Requis

### Icônes (Lucide React - déjà installé)
- MessageSquare (chat)
- FileText (documents)
- Clock (historique)
- User (profil)
- Send (envoyer)
- Download (export)
- ChevronDown (collapse)

### Pas besoin d'images
- Logo text-based: "DisruptIQ" en Inter 600

---

## 🎯 Success Criteria

### Must-Have
- ✅ Design minimaliste et sobre
- ✅ Couleurs pastel cohérentes
- ✅ 3 panels fonctionnels (left/center/right)
- ✅ CoT collapsable
- ✅ Messages avec citations
- ✅ Backend connecté et fonctionnel

### Nice-to-Have
- ⭐ Tableaux exportables
- ⭐ Smart cards initiales
- ⭐ Animations Framer Motion
- ⭐ Dark mode

---

## 🚀 Next Steps

**Session suivante** :
1. Vérifier que le backend tourne (`curl http://localhost:8000/health`)
2. Vérifier que le frontend dev tourne (`npm run dev`)
3. Créer le dossier `/components/v2/`
4. **Commencer par Phase 1** : Mettre à jour les couleurs CSS

---

**Estimation temps total** : 4-5 heures
**Approche** : Itérative et sécurisée (v2 folder, pas de casse)
**ROI** : UX moderne, professionnelle, meilleure rétention utilisateurs

**Status** : 🟢 READY TO START
