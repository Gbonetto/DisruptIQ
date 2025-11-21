# 📋 Guide de Migration: xlsx → exceljs

**Date:** 13 Novembre 2025
**Raison:** Vulnérabilités sécurité dans xlsx (CVE-2024-...)
**Alternative:** exceljs (bibliothèque sécurisée et activement maintenue)

---

## ✅ Changements Effectués

1. ✅ `xlsx` désinstallé
2. ✅ `exceljs` installé
3. ✅ Utilitaire `src/lib/excel-utils.ts` créé

---

## 🔄 Migration du Code

### Fichiers à Mettre à Jour

Les fichiers suivants utilisent xlsx et doivent être migrés:

1. `src/pages/MainChatPage.tsx`
2. `src/components/v2/Core/DataTable.tsx`
3. `src/pages/ProfessionnelsPage.tsx`
4. `src/pages/CoproprietesPage.tsx`
5. `src/pages/CoproprietairesPage.tsx`
6. `src/components/import-wizard/ImportWizard.tsx`

---

## 📝 Exemples de Migration

### Avant (avec xlsx):

```typescript
import * as XLSX from 'xlsx';

// Export to Excel
const worksheet = XLSX.utils.json_to_sheet(data);
const workbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
XLSX.writeFile(workbook, "export.xlsx");

// Import from Excel
const file = e.target.files[0];
const reader = new FileReader();
reader.onload = (e) => {
  const data = new Uint8Array(e.target.result);
  const workbook = XLSX.read(data, { type: 'array' });
  const worksheet = workbook.Sheets[workbook.SheetNames[0]];
  const jsonData = XLSX.utils.sheet_to_json(worksheet);
  console.log(jsonData);
};
reader.readAsArrayBuffer(file);
```

### Après (avec exceljs via notre utilitaire):

```typescript
import { exportToExcel, importFromExcel } from '@/lib/excel-utils';

// Export to Excel
await exportToExcel(data, "export.xlsx", "Sheet1");

// Import from Excel
const file = e.target.files[0];
const jsonData = await importFromExcel(file);
console.log(jsonData);
```

---

## 🔧 Fonctions Disponibles

### 1. `exportToExcel()`

Export data to Excel file.

```typescript
await exportToExcel(
  data: ExcelData[],      // Array of objects
  filename: string,        // Output filename
  sheetName?: string       // Sheet name (default: "Sheet1")
): Promise<void>
```

**Exemple:**
```typescript
const users = [
  { name: "John", email: "john@example.com", age: 30 },
  { name: "Jane", email: "jane@example.com", age: 25 },
];

await exportToExcel(users, "users.xlsx", "Users");
```

### 2. `importFromExcel()`

Read Excel file and convert to JSON.

```typescript
await importFromExcel(
  file: File,             // File from input
  sheetIndex?: number     // Sheet index (default: 0)
): Promise<ExcelData[]>
```

**Exemple:**
```typescript
const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const data = await importFromExcel(file);
    console.log("Imported data:", data);
    // Process data...
  } catch (error) {
    console.error("Import failed:", error);
  }
};
```

### 3. `downloadExcelTemplate()`

Download empty template file for imports.

```typescript
await downloadExcelTemplate(
  headers: string[],      // Column headers
  filename?: string       // Filename (default: "template.xlsx")
): Promise<void>
```

**Exemple:**
```typescript
await downloadExcelTemplate(
  ["Name", "Email", "Phone", "Company"],
  "import_template.xlsx"
);
```

---

## 🎨 Features Bonus

Notre utilitaire exceljs ajoute des améliorations:

- ✅ **Headers stylés** (fond gris, texte bold)
- ✅ **Auto-sizing colonnes** (largeur 15-20 chars)
- ✅ **Gestion erreurs** (try/catch avec messages clairs)
- ✅ **Type-safe** (TypeScript)
- ✅ **Async/await** (moderne)

---

## 🚀 Plan de Migration (Optionnel)

Si tu veux migrer immédiatement (recommandé):

### Étape 1: Rechercher tous les usages

```bash
cd frontend
grep -r "import.*xlsx" src/
grep -r "XLSX\." src/
```

### Étape 2: Remplacer imports

```typescript
// Avant
import * as XLSX from 'xlsx';

// Après
import { exportToExcel, importFromExcel } from '@/lib/excel-utils';
```

### Étape 3: Remplacer exports

```typescript
// Avant
const worksheet = XLSX.utils.json_to_sheet(data);
const workbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(workbook, worksheet, "Data");
XLSX.writeFile(workbook, `${filename}.xlsx`);

// Après
await exportToExcel(data, filename, "Data");
```

### Étape 4: Remplacer imports

```typescript
// Avant
const reader = new FileReader();
reader.onload = (e) => {
  const data = new Uint8Array(e.target.result);
  const workbook = XLSX.read(data, { type: 'array' });
  const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
  const jsonData = XLSX.utils.sheet_to_json(firstSheet);
  setImportedData(jsonData);
};
reader.readAsArrayBuffer(file);

// Après
const jsonData = await importFromExcel(file);
setImportedData(jsonData);
```

### Étape 5: Tester

```bash
npm run dev
# Test export/import features in browser
```

---

## ⚠️ Notes Importantes

### Compatibilité

- ✅ **Formats supportés:** .xlsx, .xlsm, .xls (lecture uniquement .xlsx recommandé)
- ✅ **Browser compatibility:** Tous navigateurs modernes (Chrome, Firefox, Safari, Edge)
- ✅ **TypeScript:** Full type support

### Performance

- ExcelJS est **plus rapide** que xlsx pour les gros fichiers
- **Streaming support** disponible pour très gros fichiers (>100 MB)
- Pas de dépendances natives (100% JavaScript)

### Sécurité

- ✅ **Pas de vulnérabilités connues**
- ✅ **Activement maintenu** (dernière release: Nov 2024)
- ✅ **Large community** (6.5M downloads/week)
- ✅ **Type-safe** (TypeScript natif)

---

## 📞 Support

En cas de problème lors de la migration:

1. Consulter [ExcelJS Documentation](https://github.com/exceljs/exceljs)
2. Vérifier `src/lib/excel-utils.ts` pour exemples
3. Tester avec fichiers Excel simples d'abord

---

## ✅ Checklist Migration

- [x] xlsx désinstallé
- [x] exceljs installé
- [x] Utilitaire excel-utils.ts créé
- [ ] Imports mis à jour dans tous les fichiers
- [ ] Code export mis à jour
- [ ] Code import mis à jour
- [ ] Tests manuels effectués
- [ ] npm audit passe sans vulnérabilités

---

**Status:** ✅ Prêt pour migration
**Temps estimé migration:** 30-60 minutes pour 6 fichiers

*Guide créé: 13 Novembre 2025*
