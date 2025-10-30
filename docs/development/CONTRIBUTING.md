# 🤝 Guide de Contribution - DisruptIQ

Merci de votre intérêt pour contribuer à DisruptIQ ! Ce guide vous aidera à comprendre notre processus de développement et nos standards de code.

---

## 📋 Table des Matières

1. [Prérequis](#prérequis)
2. [Configuration de l'Environnement de Développement](#configuration-de-lenvironnement-de-développement)
3. [Workflow de Développement](#workflow-de-développement)
4. [Standards de Code](#standards-de-code)
5. [Conventions de Commits](#conventions-de-commits)
6. [Tests](#tests)
7. [Pull Requests](#pull-requests)
8. [Code Review](#code-review)

---

## 🔧 Prérequis

Avant de commencer, assurez-vous d'avoir installé :

- **Python 3.11+**
- **Node.js 18+** et **npm**
- **Docker** et **Docker Compose**
- **Git**
- Un éditeur de code (VS Code recommandé)

---

## 🚀 Configuration de l'Environnement de Développement

### 1. Fork et Clone

```bash
# Fork le repository sur GitHub
# Puis clone votre fork
git clone https://github.com/votre-username/DisruptIQ.git
cd DisruptIQ

# Ajouter le repository principal comme upstream
git remote add upstream https://github.com/original-org/DisruptIQ.git
```

### 2. Configuration Backend

```bash
cd backend

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Copier le fichier .env.example
cp .env.example .env
# Éditer .env avec vos valeurs
```

### 3. Configuration Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Copier le fichier .env.example
cp .env.example .env
# Éditer .env avec vos valeurs
```

### 4. Lancer les Services

```bash
# À la racine du projet
docker-compose up -d postgres qdrant redis

# Backend (terminal 1)
cd backend
uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend
npm run dev
```

---

## 🔄 Workflow de Développement

### 1. Créer une Branche

Créez toujours une nouvelle branche pour vos modifications :

```bash
git checkout main
git pull upstream main
git checkout -b feature/nom-de-votre-feature
```

**Convention de nommage des branches :**
- `feature/description` - Nouvelle fonctionnalité
- `fix/description` - Correction de bug
- `docs/description` - Documentation
- `refactor/description` - Refactoring
- `test/description` - Ajout de tests

### 2. Développer

- Faites des commits fréquents et atomiques
- Testez vos modifications localement
- Assurez-vous que le code respecte les standards

### 3. Synchroniser avec Upstream

```bash
git fetch upstream
git rebase upstream/main
```

### 4. Push et Pull Request

```bash
git push origin feature/nom-de-votre-feature
```

Puis créez une Pull Request sur GitHub.

---

## 📝 Standards de Code

### Backend (Python)

#### Style de Code

Nous suivons **PEP 8** avec quelques particularités :

- **Line length**: 100 caractères max
- **Imports**: Groupés par standard lib, third-party, local
- **Type hints**: Obligatoires pour toutes les fonctions publiques
- **Docstrings**: Format Google pour les fonctions complexes

#### Exemple de Code Backend

```python
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

async def get_vendors_by_category(
    category: str,
    db: AsyncSession,
    limit: int = 10,
    offset: int = 0
) -> List[Vendor]:
    """
    Récupère les vendors par catégorie.

    Args:
        category: Catégorie à filtrer
        db: Session de base de données
        limit: Nombre max de résultats
        offset: Décalage pour la pagination

    Returns:
        Liste des vendors correspondants

    Raises:
        HTTPException: Si la catégorie n'existe pas
    """
    if not category:
        raise HTTPException(400, "Category required")

    result = await db.execute(
        select(Vendor)
        .where(Vendor.category == category)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
```

#### Outils de Linting/Formatting

```bash
# Installer les outils
pip install black isort flake8 mypy

# Formatter le code
black .
isort .

# Vérifier le style
flake8 .
mypy .
```

### Frontend (TypeScript/React)

#### Style de Code

- **TypeScript strict mode**: Activé
- **ESLint**: Suivre la config du projet
- **Prettier**: Formatter automatiquement
- **Naming conventions**:
  - Components: PascalCase (`VendorCard.tsx`)
  - Hooks: camelCase avec prefix `use` (`useVendors.ts`)
  - Utils: camelCase (`formatDate.ts`)

#### Exemple de Code Frontend

```typescript
import { useState, useEffect } from 'react'
import { adminApi } from '@/lib/api'
import { Vendor } from '@/types'

interface VendorListProps {
  category?: string
  onSelect?: (vendor: Vendor) => void
}

export function VendorList({ category, onSelect }: VendorListProps) {
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadVendors = async () => {
      try {
        setLoading(true)
        const response = await adminApi.listVendors({ category })
        setVendors(response.data)
      } catch (err) {
        setError('Failed to load vendors')
      } finally {
        setLoading(false)
      }
    }

    loadVendors()
  }, [category])

  if (loading) return <div>Chargement...</div>
  if (error) return <div>Erreur: {error}</div>

  return (
    <div className="vendor-list">
      {vendors.map((vendor) => (
        <VendorCard
          key={vendor.id}
          vendor={vendor}
          onClick={() => onSelect?.(vendor)}
        />
      ))}
    </div>
  )
}
```

#### Outils de Linting/Formatting

```bash
# Vérifier le code
npm run lint

# Formatter le code
npm run format

# Vérifier les types
npm run type-check
```

### Gestion d'Erreurs

#### Backend

```python
# Toujours utiliser des exceptions spécifiques
from fastapi import HTTPException

# ✅ Bon
raise HTTPException(404, detail="Vendor not found")

# ❌ Mauvais
raise Exception("Not found")
```

#### Frontend

```typescript
// Toujours gérer les erreurs des appels API
try {
  const response = await api.get('/vendors')
  setData(response.data)
} catch (error) {
  const message = error.response?.data?.detail || 'Une erreur est survenue'
  setError(message)
}
```

---

## 📝 Conventions de Commits

Nous utilisons les **Conventional Commits** :

```
<type>(<scope>): <description>

[corps optionnel]

[footer optionnel]
```

### Types

- `feat`: Nouvelle fonctionnalité
- `fix`: Correction de bug
- `docs`: Documentation uniquement
- `style`: Changements de formatting (sans impact sur le code)
- `refactor`: Refactoring (ni feature ni fix)
- `perf`: Amélioration de performance
- `test`: Ajout ou modification de tests
- `chore`: Maintenance (dependencies, config, etc.)

### Exemples

```bash
feat(admin): add vendor bulk delete endpoint

fix(chat): resolve RAG context retrieval error

docs(setup): update Gmail OAuth configuration guide

refactor(services): extract vendor indexing logic to separate service

test(api): add integration tests for digest endpoints

chore(deps): upgrade fastapi to v0.104.1
```

### Règles

- Utiliser l'impératif présent : "add" pas "added"
- Première ligne max 72 caractères
- Corps du commit pour expliquer le **pourquoi** (pas le quoi)
- Référencer les issues : `Closes #123`

---

## 🧪 Tests

### Backend Tests

```bash
cd backend

# Lancer tous les tests
pytest

# Lancer avec coverage
pytest --cov=app --cov-report=html

# Lancer un fichier spécifique
pytest tests/test_admin.py

# Lancer avec logs
pytest -v -s
```

#### Structure des Tests

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_vendors():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/admin/vendors")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
```

### Frontend Tests

```bash
cd frontend

# Lancer les tests
npm test

# Lancer avec coverage
npm test -- --coverage

# Lancer en mode watch
npm test -- --watch
```

### Tests à Ajouter

Avant de soumettre une PR, assurez-vous d'ajouter des tests pour :

- ✅ Nouvelles fonctionnalités
- ✅ Corrections de bugs
- ✅ Endpoints API
- ✅ Composants React complexes
- ✅ Logique métier critique

---

## 🔀 Pull Requests

### Checklist avant Soumission

- [ ] Le code respecte les standards de style
- [ ] Tous les tests passent
- [ ] De nouveaux tests ont été ajoutés si nécessaire
- [ ] La documentation a été mise à jour
- [ ] Les commits suivent les conventions
- [ ] Aucun conflit avec la branche `main`
- [ ] Le code a été testé localement

### Template de PR

```markdown
## Description

Brève description des changements

## Type de Changement

- [ ] Bug fix
- [ ] Nouvelle fonctionnalité
- [ ] Breaking change
- [ ] Documentation

## Tests Effectués

- [ ] Tests unitaires
- [ ] Tests d'intégration
- [ ] Tests manuels

## Screenshots (si applicable)

## Notes pour les Reviewers

Points d'attention particuliers
```

### Taille des PRs

- Préférer des PRs **petites et focalisées**
- Une PR = une fonctionnalité ou un fix
- Si > 500 lignes, envisager de découper

---

## 👀 Code Review

### En tant qu'Auteur

- Répondre aux commentaires rapidement
- Être ouvert aux suggestions
- Expliquer vos choix techniques si nécessaire
- Mettre à jour la PR selon les feedbacks

### En tant que Reviewer

- Être constructif et bienveillant
- Pointer les problèmes spécifiques
- Suggérer des solutions
- Approuver si tout est OK

### Points de Review

- ✅ Logique correcte
- ✅ Pas de régression
- ✅ Performance acceptable
- ✅ Sécurité (pas de failles)
- ✅ Tests suffisants
- ✅ Code lisible et maintenable
- ✅ Pas de duplication de code

---

## 🐛 Signaler un Bug

Utilisez les GitHub Issues avec le template Bug Report :

- Description claire du problème
- Steps to reproduce
- Comportement attendu vs réel
- Screenshots si applicable
- Environnement (OS, versions, etc.)
- Logs d'erreur

---

## 💡 Proposer une Fonctionnalité

Utilisez les GitHub Issues avec le template Feature Request :

- Cas d'usage
- Bénéfices attendus
- Proposition de design/implementation
- Alternatives considérées

---

## 🆘 Besoin d'Aide ?

- Consultez d'abord la [documentation](../README.md)
- Vérifiez les [issues existantes](https://github.com/org/DisruptIQ/issues)
- Consultez le [TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)
- Demandez sur Discord/Slack (si disponible)

---

## 📜 Licence

En contribuant, vous acceptez que vos contributions soient sous la même licence que le projet.

---

**Merci de contribuer à DisruptIQ ! 🚀**

**Dernière mise à jour** : 30 octobre 2025
