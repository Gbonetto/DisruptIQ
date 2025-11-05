# DisruptIQ - Knowledge Management & Multi-Agent Quality Fixes v6.0

**Date**: 2025-11-04
**Priorité**: 🔴 CRITIQUE - Pilier de la solution
**Objectifs**:
1. Fix SQL Import (Gregori Bonetto missing)
2. Improve Multi-Agent Quality
3. Professional Chain of Thought UI

---

## 🔴 PROBLÈME 1: SQL Import Silently Fails

### Symptômes
```
User: Import CSV avec Gregori Bonetto
System: "0 lignes importées (1 ignorées)"
Result: Gregori Bonetto PAS dans la BDD
```

### Root Cause Analysis

**Fichier**: `backend/app/api/endpoints/sql_tables.py:478-506`

```python
for _, row in df.iterrows():
    try:
        # Build insert data from mapping
        insert_data = {}
        for csv_col, db_col in mapping.items():
            if db_col and csv_col in df.columns:
                value = row[csv_col]
                if pd.notna(value):  # Skip NaN values
                    insert_data[db_col] = value

        if not insert_data:  # BUG 1: Silent skip if all values are NaN
            rows_skipped += 1
            continue

        # INSERT query...
        await db.execute(text(insert_sql), params)
        rows_imported += 1

    except Exception as e:
        logger.warning("row_import_failed", error=str(e), row_data=insert_data)
        rows_skipped += 1  # BUG 2: Silent fail without user notification
        continue
```

**3 Bugs Identifiés**:

1. **Silent Skip**: Si tous les champs mappés sont NaN → skip sans explication
2. **Silent Fail**: Si erreur SQL (duplicate key, constraint violation) → skip sans détails
3. **No Validation**: Pas de validation des required fields avant INSERT

**Conséquences**:
- User ne sait PAS pourquoi Gregori Bonetto n'est pas importé
- Impossible de debug sans regarder les logs backend
- Perte de données silencieuse = 💀 CRITIQUE pour Knowledge Management

---

## ✅ SOLUTION 1: Robust Import with Detailed Feedback

### A. Add Detailed Error Tracking

```python
# sql_tables.py - IMPROVED VERSION

from pydantic import BaseModel
from typing import List, Optional

class ImportError(BaseModel):
    """Detailed error for a failed row"""
    row_number: int
    error_type: str  # "missing_required_field", "duplicate_key", "validation_error", "sql_error"
    error_message: str
    row_data: dict  # Original row data for debugging

class ImportResult(BaseModel):
    """Detailed import result"""
    message: str
    table_name: str
    rows_imported: int
    rows_skipped: int
    errors: List[ImportError] = []  # NEW: Detailed errors
    warnings: List[str] = []  # NEW: Warnings for user

@router.post("/append-csv")
async def append_csv_improved(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    column_mapping: str = Form(...),
    db: AsyncSession = Depends(get_db)
) -> ImportResult:
    """
    Improved CSV import with detailed error reporting
    """
    import json

    try:
        # ... validation code (same as before) ...

        # Get REQUIRED columns from model
        required_columns = get_required_columns(table_name)

        # Apply mapping and insert rows
        rows_imported = 0
        rows_skipped = 0
        errors: List[ImportError] = []
        warnings: List[str] = []

        for row_idx, row in df.iterrows():
            row_number = row_idx + 2  # +2 because: 0-indexed + header row

            try:
                # Build insert data from mapping
                insert_data = {}
                for csv_col, db_col in mapping.items():
                    if db_col and csv_col in df.columns:
                        value = row[csv_col]
                        if pd.notna(value):
                            insert_data[db_col] = value

                # VALIDATION 1: Check required fields
                missing_required = [col for col in required_columns if col not in insert_data]
                if missing_required:
                    errors.append(ImportError(
                        row_number=row_number,
                        error_type="missing_required_field",
                        error_message=f"Missing required fields: {', '.join(missing_required)}",
                        row_data={k: str(v) for k, v in row.to_dict().items()}
                    ))
                    rows_skipped += 1
                    continue

                # VALIDATION 2: Empty row check
                if not insert_data:
                    errors.append(ImportError(
                        row_number=row_number,
                        error_type="empty_row",
                        error_message="Row is empty or all values are missing",
                        row_data={k: str(v) for k, v in row.to_dict().items()}
                    ))
                    rows_skipped += 1
                    continue

                # Check for duplicates BEFORE inserting
                if table_name == "professionnels" and "email" in insert_data:
                    duplicate_check = await db.execute(
                        text("SELECT id FROM professionnels WHERE email = :email"),
                        {"email": insert_data["email"]}
                    )
                    if duplicate_check.scalar():
                        errors.append(ImportError(
                            row_number=row_number,
                            error_type="duplicate_key",
                            error_message=f"Duplicate email: {insert_data['email']} already exists",
                            row_data=insert_data
                        ))
                        rows_skipped += 1
                        continue

                # Build INSERT query
                columns_str = ', '.join([f'"{col}"' for col in insert_data.keys()])
                placeholders = ', '.join([f':col_{i}' for i in range(len(insert_data))])
                insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'

                params = {f'col_{i}': val for i, val in enumerate(insert_data.values())}

                await db.execute(text(insert_sql), params)
                rows_imported += 1

                logger.info("row_imported_successfully",
                           table=table_name,
                           row=row_number,
                           data=insert_data)

            except Exception as e:
                error_message = str(e)

                # Classify error type
                if "duplicate key" in error_message.lower():
                    error_type = "duplicate_key"
                elif "violates" in error_message.lower():
                    error_type = "constraint_violation"
                else:
                    error_type = "sql_error"

                errors.append(ImportError(
                    row_number=row_number,
                    error_type=error_type,
                    error_message=error_message,
                    row_data=insert_data if insert_data else {k: str(v) for k, v in row.to_dict().items()}
                ))

                logger.error("row_import_failed",
                            table=table_name,
                            row=row_number,
                            error=error_message,
                            row_data=insert_data)
                rows_skipped += 1
                continue

        await db.commit()

        # Build user-friendly message
        if rows_imported > 0 and rows_skipped == 0:
            message = f"✅ {rows_imported} lignes importées avec succès"
        elif rows_imported > 0 and rows_skipped > 0:
            message = f"⚠️ {rows_imported} lignes importées, {rows_skipped} ignorées (voir détails ci-dessous)"
        else:
            message = f"❌ Aucune ligne importée. {rows_skipped} lignes ignorées (voir erreurs ci-dessous)"

        logger.info("csv_appended_with_details",
                   table_name=table_name,
                   rows_imported=rows_imported,
                   rows_skipped=rows_skipped,
                   error_count=len(errors))

        return ImportResult(
            message=message,
            table_name=table_name,
            rows_imported=rows_imported,
            rows_skipped=rows_skipped,
            errors=errors,
            warnings=warnings
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("csv_append_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import CSV: {str(e)}"
        )


def get_required_columns(table_name: str) -> List[str]:
    """Get required columns for each table"""
    required_by_table = {
        'professionnels': ['name', 'email'],
        'coproprietaires': ['nom', 'prenom', 'copropriete_id', 'numero_lot'],
        'coproprietes': ['nom', 'adresse', 'ville', 'code_postal']
    }
    return required_by_table.get(table_name, [])
```

---

### B. Frontend: Display Detailed Errors

**Fichier**: `frontend/src/components/DocumentPanel/SQLTab.tsx`

Ajouter un modal d'erreurs détaillées :

```typescript
// SQLTab.tsx - ERROR DISPLAY COMPONENT

interface ImportError {
  row_number: number;
  error_type: string;
  error_message: string;
  row_data: Record<string, any>;
}

interface ImportResult {
  message: string;
  table_name: string;
  rows_imported: number;
  rows_skipped: number;
  errors: ImportError[];
  warnings: string[];
}

const ImportErrorsModal = ({ result, onClose }: { result: ImportResult, onClose: () => void }) => {
  if (!result.errors || result.errors.length === 0) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[80vh] overflow-hidden">
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold">
            ⚠️ Détails des Erreurs d'Import ({result.errors.length} lignes ignorées)
          </h3>
        </div>

        <div className="overflow-y-auto max-h-[60vh] p-6">
          <table className="w-full border-collapse">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-4 py-2 text-left">Ligne</th>
                <th className="px-4 py-2 text-left">Type d'Erreur</th>
                <th className="px-4 py-2 text-left">Message</th>
                <th className="px-4 py-2 text-left">Données</th>
              </tr>
            </thead>
            <tbody>
              {result.errors.map((error, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-sm">{error.row_number}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      error.error_type === 'duplicate_key' ? 'bg-yellow-100 text-yellow-800' :
                      error.error_type === 'missing_required_field' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {error.error_type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm">{error.error_message}</td>
                  <td className="px-4 py-2">
                    <details className="text-xs">
                      <summary className="cursor-pointer text-blue-600">Voir données</summary>
                      <pre className="mt-2 bg-gray-100 p-2 rounded overflow-x-auto">
                        {JSON.stringify(error.row_data, null, 2)}
                      </pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="p-6 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
```

---

## 🎯 PROBLÈME 2: Chain of Thought Not Professional

### Current Issues
- Pas de structure claire
- Trop verbose
- Pas de "trust layer" (transparence)
- Design pas assez "pro"

### Solution: Professional CoT UI (DeepSeek-style)

**Inspiration**: Notebook-style avec collapsible sections

```typescript
// frontend/src/components/ChainOfThought/ProfessionalCoT.tsx

import { useState } from 'react';
import { ChevronDown, ChevronRight, Brain, CheckCircle, XCircle, Loader } from 'lucide-react';

interface ThoughtStep {
  type: 'analyzing' | 'classifying' | 'planning' | 'executing' | 'synthesizing' | 'completed' | 'error';
  title: string;
  content: string;
  agent: string;
  progress: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

export const ProfessionalCoT = ({ thoughts }: { thoughts: ThoughtStep[] }) => {
  const [expanded, setExpanded] = useState(false);

  const getStepIcon = (type: string, progress: number) => {
    if (progress === 1.0) return <CheckCircle className="w-4 h-4 text-green-600" />;
    if (type === 'error') return <XCircle className="w-4 h-4 text-red-600" />;
    return <Loader className="w-4 h-4 text-blue-600 animate-spin" />;
  };

  const getStepColor = (type: string) => {
    const colors = {
      analyzing: 'border-l-blue-500',
      classifying: 'border-l-purple-500',
      planning: 'border-l-indigo-500',
      executing: 'border-l-orange-500',
      synthesizing: 'border-l-green-500',
      completed: 'border-l-green-600',
      error: 'border-l-red-600',
    };
    return colors[type] || 'border-l-gray-400';
  };

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden font-mono text-sm">
      {/* Header - Collapsible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-100 hover:bg-gray-150 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-gray-700" />
          <span className="font-semibold text-gray-800">🧠 Raisonnement de l'IA</span>
          <span className="text-xs text-gray-500">({thoughts.length} étapes)</span>
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-gray-600" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-600" />
        )}
      </button>

      {/* Thought Steps - Collapsible */}
      {expanded && (
        <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
          {thoughts.map((thought, idx) => (
            <div
              key={idx}
              className={`border-l-4 ${getStepColor(thought.type)} bg-white rounded-r-lg p-4 shadow-sm`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">{getStepIcon(thought.type, thought.progress)}</div>

                <div className="flex-1">
                  {/* Step Header */}
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-800">{thought.title}</h4>
                    <span className="text-xs text-gray-500 font-normal">
                      {thought.agent}
                    </span>
                  </div>

                  {/* Step Content */}
                  <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">
                    {thought.content}
                  </p>

                  {/* Progress Bar */}
                  {thought.progress < 1.0 && thought.type !== 'error' && (
                    <div className="mt-3 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-blue-600 h-full transition-all duration-300"
                        style={{ width: `${thought.progress * 100}%` }}
                      />
                    </div>
                  )}

                  {/* Metadata (for debugging) */}
                  {thought.metadata && Object.keys(thought.metadata).length > 0 && (
                    <details className="mt-3">
                      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                        📊 Données techniques
                      </summary>
                      <pre className="mt-2 bg-gray-100 p-2 rounded text-xs overflow-x-auto">
                        {JSON.stringify(thought.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer - Trust Layer */}
      <div className="px-4 py-2 bg-gray-100 border-t border-gray-200 text-xs text-gray-600">
        <span className="flex items-center gap-1">
          💡 <strong>Pourquoi ce raisonnement ?</strong> Transparence totale sur le processus de décision de l'IA.
        </span>
      </div>
    </div>
  );
};
```

---

## 🎨 UX/UI Design Specs pour Designer

### Visual Style Guide

**Palette de Couleurs**:
```css
/* Step Type Colors */
--cot-analyzing: #3B82F6;    /* blue-500 */
--cot-classifying: #A855F7;  /* purple-500 */
--cot-planning: #6366F1;     /* indigo-500 */
--cot-executing: #F97316;    /* orange-500 */
--cot-synthesizing: #10B981; /* green-500 */
--cot-completed: #059669;    /* green-600 */
--cot-error: #DC2626;        /* red-600 */

/* Background */
--cot-bg: #F9FAFB;           /* gray-50 */
--cot-header-bg: #F3F4F6;    /* gray-100 */
--cot-border: #E5E7EB;       /* gray-200 */
```

**Typography**:
- **Main font**: `JetBrains Mono` ou `Roboto Mono` (monospace pour effet "code")
- **Size**: 13px-14px (lisible mais pas trop gros)
- **Weight**: Regular (400) pour contenu, Semibold (600) pour titres

**Spacing**:
- Header padding: `12px 16px`
- Step padding: `16px`
- Gap between steps: `12px`

**Components**:
1. **Header** (always visible)
   - Icon cerveau 🧠
   - "Raisonnement de l'IA" label
   - Badge avec nombre d'étapes
   - Chevron pour expand/collapse

2. **Step Cards** (collapsible)
   - Bordure gauche colorée (type de step)
   - Icon status (spinner, check, error)
   - Titre + agent name
   - Contenu markdown-friendly
   - Progress bar optionnelle
   - Metadata collapsible

3. **Footer - Trust Layer**
   - Petit texte expliquant la transparence
   - Icône 💡 + message rassurant

---

## 📊 Implementation Plan

### Phase 1: Critical Fixes (Aujourd'hui) 🔥

1. **Fix SQL Import Error Reporting**
   - [ ] Update `sql_tables.py:append-csv` endpoint
   - [ ] Add `ImportError` and `ImportResult` models
   - [ ] Implement required field validation
   - [ ] Add duplicate key checking BEFORE insert
   - [ ] Return detailed errors array

2. **Frontend Error Display**
   - [ ] Create `ImportErrorsModal` component
   - [ ] Display errors table with row numbers
   - [ ] Color-code error types
   - [ ] Show row data in collapsible details

3. **Test Import Fix**
   - [ ] Re-import Gregori Bonetto CSV
   - [ ] Verify detailed error message if fails
   - [ ] Fix CSV data if needed
   - [ ] Confirm Gregori Bonetto in database

### Phase 2: Professional CoT UI (Cette Semaine) 🎨

4. **Create Professional CoT Component**
   - [ ] Create `ProfessionalCoT.tsx` component
   - [ ] Implement collapsible sections
   - [ ] Add step icons and colors
   - [ ] Add progress bars
   - [ ] Add metadata details (collapsible)

5. **Integrate CoT in Chat**
   - [ ] Replace old ThoughtStream UI
   - [ ] Test with real agent responses
   - [ ] Adjust spacing and colors

6. **Add Trust Layer**
   - [ ] Footer with transparency message
   - [ ] Link to "How it works" documentation

### Phase 3: Multi-Agent Quality (2 Semaines) 🤖

7. **Entity Extraction Confidence Scoring**
   - [ ] Implement from SYSTEM_IMPROVEMENTS_v5.md
   - [ ] Add `confidence` and `is_primary_intent` fields
   - [ ] Filter low-confidence entities

8. **Query Planner Priority Logic**
   - [ ] Sort entities by confidence
   - [ ] Stop after first primary intent
   - [ ] Test "plombiers pour Mimosas" case

9. **Add Tests**
   - [ ] Unit tests for entity extraction
   - [ ] Integration tests for import
   - [ ] E2E tests for email context

---

## 🎯 Success Metrics

### Import Quality
- **Before**: 0 rows imported, 1 skipped (no details)
- **After**: Detailed error: "Row 2: Missing required field 'email'" → User can fix!

### CoT UX
- **Before**: Verbose text dump, hard to read
- **After**: Professional notebook-style, collapsible, color-coded, trust layer

### Multi-Agent Accuracy
- **Before**: 33 recipients instead of 7 (471% error)
- **After**: 7 recipients only (100% accuracy with confidence scoring)

---

## 📝 Notes pour l'Équipe

**Priorité Absolue**: Import SQL fix (Gregori Bonetto)
- Blocking pour knowledge management
- Impact user immédiat
- Quick win (2-3 heures)

**Priorité Haute**: Professional CoT UI
- Améliore trust et transparence
- Différenciateur UX
- 1 journée de travail

**Priorité Moyenne**: Entity Extraction Quality
- Améliore accuracy mais système fonctionne
- 2-3 jours de travail

---

**Status**: READY FOR IMPLEMENTATION
**Owner**: Backend + Frontend Teams
**Timeline**: Phase 1 aujourd'hui, Phase 2 cette semaine, Phase 3 dans 2 semaines
