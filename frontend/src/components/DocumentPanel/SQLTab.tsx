import { useState, useEffect } from 'react';
import { Database, Eye, Download, Upload, AlertCircle, RefreshCw, CheckCircle2, Trash2, XCircle } from 'lucide-react';
import { toast } from 'sonner';

interface SQLTable {
  name: string;
  row_count: number;
  columns: string[];
}

interface SQLTableDetail {
  name: string;
  columns: Array<{
    name: string;
    type: string;
    nullable: boolean;
    default: any;
  }>;
  row_count: number;
  sample_rows: Array<Record<string, any>>;
}

interface ColumnMapping {
  csvColumn: string;
  dbColumn: string;
}

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
  warnings?: string[];
}

const ALLOWED_TABLES = [
  { value: 'professionnels', label: 'Professionnels', icon: '👷' },
  { value: 'coproprietaires', label: 'Copropriétaires', icon: '👥' },
  { value: 'coproprietes', label: 'Copropriétés', icon: '🏢' }
];

export function SQLTab() {
  const [tables, setTables] = useState<SQLTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableDetail, setTableDetail] = useState<SQLTableDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Import modal state
  const [showImportModal, setShowImportModal] = useState(false);
  const [selectedTargetTable, setSelectedTargetTable] = useState<string>('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [csvColumns, setCsvColumns] = useState<string[]>([]);
  const [columnMappings, setColumnMappings] = useState<ColumnMapping[]>([]);
  const [dbColumns, setDbColumns] = useState<string[]>([]);
  const [isMapping, setIsMapping] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<Array<Record<string, any>>>([]);
  const [csvDelimiter, setCsvDelimiter] = useState<string>(',');

  // Purge confirmation state
  const [showPurgeModal, setShowPurgeModal] = useState(false);
  const [tableToPurge, setTableToPurge] = useState<string | null>(null);

  // Import errors state
  const [importErrors, setImportErrors] = useState<ImportError[]>([]);
  const [showErrorModal, setShowErrorModal] = useState(false);

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8000/api/sql/tables');
      const data = await response.json();

      // Filter only allowed tables
      const allowedTables = data.tables?.filter((t: SQLTable) =>
        ALLOWED_TABLES.some(at => at.value === t.name)
      ) || [];

      setTables(allowedTables);
    } catch (error) {
      console.error('Failed to load tables:', error);
      toast.error('Échec du chargement des tables');
    } finally {
      setIsLoading(false);
    }
  };

  const loadTableDetail = async (tableName: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/sql/tables/${tableName}`);
      const data = await response.json();
      setTableDetail(data);
      setSelectedTable(tableName);
    } catch (error) {
      console.error('Failed to load table detail:', error);
      toast.error('Échec du chargement des détails');
    }
  };

  const handleDownloadTemplate = async (tableName: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/sql/download-template/${tableName}`);
      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tableName}_template.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast.success(`Template ${tableName} téléchargé`);
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Échec du téléchargement');
    }
  };

  const detectDelimiter = (line: string): string => {
    // Count occurrences of comma and semicolon
    const commaCount = (line.match(/,/g) || []).length;
    const semicolonCount = (line.match(/;/g) || []).length;

    // Return delimiter with most occurrences
    return semicolonCount > commaCount ? ';' : ',';
  };

  const parseCSVLine = (line: string, delimiter: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];

      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === delimiter && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    result.push(current.trim());

    return result;
  };

  const handleFileSelect = async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      toast.error('Format invalide. Fichier CSV requis.');
      return;
    }

    setUploadFile(file);

    // Parse CSV to get column names
    try {
      const text = await file.text();
      const lines = text.split('\n').filter(line => line.trim());

      if (lines.length > 0) {
        // Auto-detect delimiter
        const delimiter = detectDelimiter(lines[0]);
        setCsvDelimiter(delimiter);

        const headers = parseCSVLine(lines[0], delimiter);
        setCsvColumns(headers);

        // Show detected delimiter to user
        toast.success(`CSV détecté: ${headers.length} colonnes (délimiteur: ${delimiter === ',' ? 'virgule' : 'point-virgule'})`);
      }
    } catch (error) {
      console.error('Failed to parse CSV:', error);
      toast.error('Échec de la lecture du CSV');
    }
  };

  const calculateSimilarity = (str1: string, str2: string): number => {
    // Normalize strings: lowercase, remove accents, remove special chars
    const normalize = (s: string) => s
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]/g, '');

    const s1 = normalize(str1);
    const s2 = normalize(str2);

    // Exact match
    if (s1 === s2) return 1.0;

    // Contains match
    if (s1.includes(s2) || s2.includes(s1)) return 0.8;

    // Levenshtein distance-based similarity
    const maxLen = Math.max(s1.length, s2.length);
    if (maxLen === 0) return 0;

    let distance = 0;
    const minLen = Math.min(s1.length, s2.length);

    for (let i = 0; i < minLen; i++) {
      if (s1[i] !== s2[i]) distance++;
    }
    distance += Math.abs(s1.length - s2.length);

    return 1 - (distance / maxLen);
  };

  const autoMapColumns = (csvCols: string[], dbCols: string[]): ColumnMapping[] => {
    return csvCols.map(csvCol => {
      let bestMatch = '';
      let bestScore = 0.6; // Minimum similarity threshold

      dbCols.forEach(dbCol => {
        const score = calculateSimilarity(csvCol, dbCol);
        if (score > bestScore) {
          bestScore = score;
          bestMatch = dbCol;
        }
      });

      return {
        csvColumn: csvCol,
        dbColumn: bestMatch
      };
    });
  };

  const getRequiredColumns = (tableName: string): string[] => {
    // Define required columns for each table (must match actual DB column names)
    const requiredByTable: Record<string, string[]> = {
      'professionnels': ['name', 'email'], // Name and email required
      'coproprietaires': ['nom', 'prenom', 'copropriete_id', 'numero_lot'], // Nom, prenom, copro ID and lot number required
      'coproprietes': ['nom', 'adresse', 'ville', 'code_postal'] // Name, address, city and postal code required
    };

    return requiredByTable[tableName] || [];
  };

  const validateMappings = (): { isValid: boolean; missingRequired: string[] } => {
    const requiredCols = getRequiredColumns(selectedTargetTable);
    const mappedDbCols = columnMappings
      .filter(m => m.dbColumn)
      .map(m => m.dbColumn);

    const missingRequired = requiredCols.filter(req => !mappedDbCols.includes(req));

    return {
      isValid: missingRequired.length === 0,
      missingRequired
    };
  };

  const loadDbColumns = async (tableName: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/sql/tables/${tableName}`);
      const data = await response.json();

      // Filter out internal columns and mark required ones
      const cols = data.columns
        .filter((c: any) =>
          c.name !== 'id' &&
          !['created_at', 'updated_at', 'is_indexed', 'last_indexed_at'].includes(c.name)
        )
        .map((c: any) => c.name);

      setDbColumns(cols);

      // Auto-map with intelligent matching
      const mappedColumns = autoMapColumns(csvColumns, cols);
      setColumnMappings(mappedColumns);

      // Show toast with auto-mapping results
      const autoMappedCount = mappedColumns.filter(m => m.dbColumn).length;
      if (autoMappedCount > 0) {
        toast.success(`✓ ${autoMappedCount} colonne(s) mappée(s) automatiquement`);
      }

    } catch (error) {
      console.error('Failed to load DB columns:', error);
      toast.error('Échec du chargement des colonnes');
    }
  };

  const handleStartMapping = () => {
    if (!selectedTargetTable) {
      toast.error('Sélectionnez une table cible');
      return;
    }
    if (!uploadFile) {
      toast.error('Sélectionnez un fichier CSV');
      return;
    }
    setIsMapping(true);
    loadDbColumns(selectedTargetTable);
  };

  const generatePreview = async () => {
    if (!uploadFile) return;

    try {
      const text = await uploadFile.text();
      const lines = text.split('\n').filter(line => line.trim());

      // Skip header, take first 5 data rows
      const dataRows = lines.slice(1, 6);

      const preview: Array<Record<string, any>> = dataRows.map(line => {
        const values = parseCSVLine(line, csvDelimiter);
        const row: Record<string, any> = {};

        columnMappings.forEach((mapping, idx) => {
          if (mapping.dbColumn && values[idx] !== undefined) {
            row[mapping.dbColumn] = values[idx];
          }
        });

        return row;
      });

      setPreviewData(preview);
      setShowPreview(true);
    } catch (error) {
      console.error('Preview generation failed:', error);
      toast.error('Échec de la génération de l\'aperçu');
    }
  };

  const handleImportData = async () => {
    if (!uploadFile || !selectedTargetTable) return;

    // Build mapping object
    const mapping: Record<string, string> = {};
    columnMappings.forEach(m => {
      if (m.dbColumn) {
        mapping[m.csvColumn] = m.dbColumn;
      }
    });

    if (Object.keys(mapping).length === 0) {
      toast.error('Aucune colonne mappée');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('table_name', selectedTargetTable);
      formData.append('column_mapping', JSON.stringify(mapping));

      const toastId = toast.loading('Import en cours...');

      const response = await fetch('http://localhost:8000/api/sql/append-csv', {
        method: 'POST',
        body: formData,
      });

      const data: ImportResult = await response.json();

      if (response.ok) {
        // Check if there are errors to display
        if (data.errors && data.errors.length > 0) {
          // Show error modal with detailed information
          setImportErrors(data.errors);
          setShowErrorModal(true);

          // Show appropriate toast based on results
          if (data.rows_imported > 0) {
            toast.warning(
              `⚠️ ${data.rows_imported} ligne${data.rows_imported > 1 ? 's' : ''} importée${data.rows_imported > 1 ? 's' : ''}, ${data.rows_skipped} ignorée${data.rows_skipped > 1 ? 's' : ''}`,
              { id: toastId }
            );
          } else {
            toast.error(
              `❌ Aucune ligne importée. ${data.rows_skipped} ligne${data.rows_skipped > 1 ? 's' : ''} ignorée${data.rows_skipped > 1 ? 's' : ''}. Voir les erreurs.`,
              { id: toastId }
            );
          }
        } else if (data.rows_imported > 0) {
          // All good, show success
          toast.success(
            `✅ ${data.rows_imported} ligne${data.rows_imported > 1 ? 's' : ''} importée${data.rows_imported > 1 ? 's' : ''} avec succès`,
            { id: toastId }
          );
        } else {
          // No rows imported and no errors (shouldn't happen)
          toast.error('❌ Aucune ligne importée', { id: toastId });
        }

        // Reset form only if all rows were imported successfully
        if (data.errors.length === 0) {
          setShowImportModal(false);
          setUploadFile(null);
          setSelectedTargetTable('');
          setCsvColumns([]);
          setColumnMappings([]);
          setIsMapping(false);
          setShowPreview(false);
          setPreviewData([]);
        }

        // Reload tables
        await loadTables();
      } else {
        throw new Error(data.message || 'Import failed');
      }
    } catch (error: any) {
      console.error('Import failed:', error);
      toast.error(`Échec de l'import: ${error.message}`);
    }
  };

  const handlePurgeTable = async () => {
    if (!tableToPurge) return;

    try {
      const toastId = toast.loading('Purge en cours...');

      const response = await fetch(`http://localhost:8000/api/sql/purge/${tableToPurge}`, {
        method: 'DELETE'
      });

      const data = await response.json();

      if (response.ok) {
        toast.success(`Table "${tableToPurge}" purgée avec succès`, { id: toastId });
        setShowPurgeModal(false);
        setTableToPurge(null);

        // Clear detail view if we're viewing the purged table
        if (selectedTable === tableToPurge) {
          setSelectedTable(null);
          setTableDetail(null);
        }

        // Reload tables
        await loadTables();
      } else {
        throw new Error(data.detail || 'Purge failed');
      }
    } catch (error: any) {
      console.error('Purge failed:', error);
      toast.error(`Échec de la purge: ${error.message}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Database className="w-4 h-4 text-indigo-600" />
          Gestion des Données SQL
        </h3>
        <div className="flex gap-2">
          <button
            onClick={loadTables}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Actualiser
          </button>
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Upload className="w-3 h-3" />
            Importer Données
          </button>
        </div>
      </div>

      {/* Tables List */}
      <div className="space-y-3">
        {tables.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
            <Database className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-600 font-medium mb-2">Aucune table disponible</p>
            <p className="text-sm text-gray-500">Les tables SQL sont en cours de configuration</p>
          </div>
        ) : (
          tables.map((table) => {
            const tableConfig = ALLOWED_TABLES.find(t => t.value === table.name);

            return (
              <div
                key={table.name}
                className={`group p-4 rounded-xl border transition-all duration-200 cursor-pointer ${
                  selectedTable === table.name
                    ? 'border-indigo-300 bg-gradient-to-br from-indigo-50 to-indigo-100 ring-2 ring-indigo-200'
                    : 'border-gray-200 bg-white hover:border-indigo-200 hover:shadow-md'
                }`}
                onClick={() => loadTableDetail(table.name)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1">
                    <div className={`p-2 rounded-lg text-2xl ${
                      selectedTable === table.name ? 'bg-indigo-200' : 'bg-indigo-100'
                    }`}>
                      {tableConfig?.icon || '📊'}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-gray-900 mb-1">
                        {tableConfig?.label || table.name}
                      </h4>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                          <span className="text-gray-600 font-medium">{table.row_count.toLocaleString()}</span>
                          <span className="text-gray-400">lignes</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-purple-500"></div>
                          <span className="text-gray-600 font-medium">{table.columns?.length || 0}</span>
                          <span className="text-gray-400">colonnes</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-1.5">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadTemplate(table.name);
                      }}
                      className="p-2 text-blue-600 hover:bg-blue-100 rounded-lg transition-all"
                      title="Télécharger template"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        loadTableDetail(table.name);
                      }}
                      className="p-2 text-indigo-600 hover:bg-indigo-100 rounded-lg transition-all"
                      title="Voir détails"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setTableToPurge(table.name);
                        setShowPurgeModal(true);
                      }}
                      className="p-2 text-red-600 hover:bg-red-100 rounded-lg transition-all"
                      title="Purger la table"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Separator between cards and details */}
      {tableDetail && (
        <div className="my-4 border-t border-gray-300"></div>
      )}

      {/* Table Detail Panel */}
      {tableDetail && (
        <div className="mt-2 p-5 bg-gradient-to-br from-white to-gray-50 rounded-xl border border-gray-200 shadow-md">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Database className="w-5 h-5 text-indigo-700" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-gray-900">
                  {ALLOWED_TABLES.find(t => t.value === tableDetail.name)?.label || tableDetail.name}
                </h4>
                <p className="text-xs text-gray-500">
                  {tableDetail.row_count} lignes • {tableDetail.columns.length} colonnes
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                setSelectedTable(null);
                setTableDetail(null);
              }}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Fermer ✕
            </button>
          </div>

          {/* Sample Data Table */}
          {tableDetail.sample_rows && tableDetail.sample_rows.length > 0 && (
            <div>
              <h5 className="text-xs font-bold text-gray-700 mb-3 flex items-center gap-2">
                <span className="w-1 h-4 bg-emerald-500 rounded"></span>
                Aperçu des données ({Math.min(tableDetail.sample_rows.length, 5)} lignes)
              </h5>
              <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
                <table className="min-w-full text-xs">
                  <thead className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                    <tr>
                      {tableDetail.columns.slice(0, 5).map((col) => (
                        <th key={col.name} className="px-3 py-2.5 text-left font-semibold text-gray-700 whitespace-nowrap">
                          {col.name}
                        </th>
                      ))}
                      {tableDetail.columns.length > 5 && (
                        <th className="px-3 py-2.5 text-left text-gray-400">...</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {tableDetail.sample_rows.slice(0, 5).map((row, idx) => (
                      <tr key={idx} className="hover:bg-indigo-50/30 transition-colors">
                        {tableDetail.columns.slice(0, 5).map((col) => (
                          <td key={col.name} className="px-3 py-2.5 text-gray-900 max-w-xs truncate">
                            {String(row[col.name] ?? '-')}
                          </td>
                        ))}
                        {tableDetail.columns.length > 5 && (
                          <td className="px-3 py-2.5 text-gray-400">...</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-gray-500 mt-2 italic">
                Affichage limité aux 5 premières colonnes et 5 premières lignes
              </p>
            </div>
          )}
        </div>
      )}

      {/* Purge Confirmation Modal */}
      {showPurgeModal && tableToPurge && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-6">
              <div className="flex items-start gap-3 mb-4">
                <div className="p-3 bg-red-100 rounded-full">
                  <AlertCircle className="w-6 h-6 text-red-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-gray-900 mb-2">Purger la table ?</h3>
                  <p className="text-sm text-gray-600 mb-3">
                    Vous êtes sur le point de <strong className="text-red-600">supprimer toutes les données</strong> de la table{' '}
                    <strong>{ALLOWED_TABLES.find(t => t.value === tableToPurge)?.label}</strong>.
                  </p>
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-3">
                    <p className="text-xs text-red-800 font-semibold mb-1">⚠️ Action irréversible</p>
                    <ul className="text-xs text-red-700 space-y-1 list-disc list-inside">
                      <li>Toutes les lignes seront supprimées</li>
                      <li>La structure de la table sera conservée</li>
                      <li>Les compteurs (ID) seront réinitialisés</li>
                      <li>Cette action ne peut pas être annulée</li>
                    </ul>
                  </div>
                  <p className="text-xs text-gray-500 italic">
                    Assurez-vous d'avoir une sauvegarde avant de continuer.
                  </p>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setShowPurgeModal(false);
                    setTableToPurge(null);
                  }}
                  className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Annuler
                </button>
                <button
                  onClick={handlePurgeTable}
                  className="flex-1 px-4 py-2 bg-red-600 text-white text-sm font-bold rounded-lg hover:bg-red-700 transition-colors"
                >
                  Purger définitivement
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Importer des Données CSV</h3>

              {!isMapping ? (
                // Step 1: Select table and file
                <div className="space-y-4">
                  {/* Table Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Table cible
                    </label>
                    <select
                      value={selectedTargetTable}
                      onChange={(e) => setSelectedTargetTable(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value="">Sélectionnez une table...</option>
                      {ALLOWED_TABLES.map(t => (
                        <option key={t.value} value={t.value}>
                          {t.icon} {t.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* File Upload */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Fichier CSV
                    </label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                      className="w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                    />
                    {uploadFile && (
                      <p className="mt-2 text-xs text-green-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        {uploadFile.name} ({csvColumns.length} colonnes détectées)
                      </p>
                    )}
                  </div>

                  {/* Download Template */}
                  {selectedTargetTable && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-xs text-blue-800 font-medium mb-2">
                            Besoin d'un template ?
                          </p>
                          <button
                            onClick={() => handleDownloadTemplate(selectedTargetTable)}
                            className="text-xs text-blue-700 hover:text-blue-900 underline flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Télécharger le template {ALLOWED_TABLES.find(t => t.value === selectedTargetTable)?.label}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-4">
                    <button
                      onClick={handleStartMapping}
                      disabled={!selectedTargetTable || !uploadFile}
                      className="flex-1 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      Continuer vers le mapping
                    </button>
                    <button
                      onClick={() => {
                        setShowImportModal(false);
                        setUploadFile(null);
                        setSelectedTargetTable('');
                        setCsvColumns([]);
                        setIsMapping(false);
                        setShowPreview(false);
                        setPreviewData([]);
                      }}
                      className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      Annuler
                    </button>
                  </div>
                </div>
              ) : (
                // Step 2: Column Mapping
                <div className="space-y-4">
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
                    <p className="text-xs text-yellow-800">
                      <strong>Instructions:</strong> Faites correspondre les colonnes de votre CSV avec les colonnes de la base de données.
                      Les colonnes non mappées seront ignorées.
                    </p>
                  </div>

                  {/* Real-time Validation Banner */}
                  {(() => {
                    const validation = validateMappings();
                    if (!validation.isValid) {
                      return (
                        <div className="bg-red-50 border border-red-300 rounded-lg p-3 mb-4">
                          <div className="flex items-start gap-2">
                            <AlertCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              <p className="text-xs font-semibold text-red-800 mb-1">
                                ⚠️ Colonnes requises manquantes
                              </p>
                              <p className="text-xs text-red-700">
                                Les colonnes suivantes sont obligatoires :{' '}
                                <strong>{validation.missingRequired.join(', ')}</strong>
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  })()}

                  {/* Mapping Table */}
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Colonne CSV</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">➜ Colonne BDD</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {columnMappings.map((mapping, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-mono text-xs text-gray-900">
                              {mapping.csvColumn}
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <select
                                  value={mapping.dbColumn}
                                  onChange={(e) => {
                                    const newMappings = [...columnMappings];
                                    newMappings[idx].dbColumn = e.target.value;
                                    setColumnMappings(newMappings);
                                  }}
                                  className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                                >
                                  <option value="">-- Ignorer --</option>
                                  {dbColumns.map(col => {
                                    const isRequired = getRequiredColumns(selectedTargetTable).includes(col);
                                    return (
                                      <option key={col} value={col}>
                                        {isRequired ? '* ' : ''}{col}
                                      </option>
                                    );
                                  })}
                                </select>
                                {mapping.dbColumn && calculateSimilarity(mapping.csvColumn, mapping.dbColumn) > 0.6 && (
                                  <div className="flex items-center gap-1 text-green-600 text-xs whitespace-nowrap" title="Mappé automatiquement">
                                    <CheckCircle2 className="w-3 h-3" />
                                    <span className="font-medium">Auto</span>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Preview Section */}
                  {showPreview && previewData.length > 0 && (
                    <div className="mt-4 bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-indigo-900 mb-3 flex items-center gap-2">
                        <Eye className="w-4 h-4" />
                        Aperçu des 5 premières lignes mappées
                      </h4>
                      <div className="overflow-x-auto bg-white border border-indigo-200 rounded-lg">
                        <table className="min-w-full text-xs">
                          <thead className="bg-indigo-100 border-b border-indigo-200">
                            <tr>
                              {Object.keys(previewData[0] || {}).map(col => (
                                <th key={col} className="px-3 py-2 text-left font-semibold text-indigo-900">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-indigo-100">
                            {previewData.map((row, idx) => (
                              <tr key={idx} className="hover:bg-indigo-50">
                                {Object.values(row).map((val, vidx) => (
                                  <td key={vidx} className="px-3 py-2 text-gray-900">
                                    {String(val || '-')}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-4">
                    <button
                      onClick={() => {
                        setIsMapping(false);
                        setShowPreview(false);
                        setPreviewData([]);
                      }}
                      className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      ← Retour
                    </button>
                    {!showPreview ? (
                      <button
                        onClick={generatePreview}
                        disabled={!validateMappings().isValid || columnMappings.filter(m => m.dbColumn).length === 0}
                        className="flex-1 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                      >
                        <Eye className="w-4 h-4" />
                        Aperçu avant import
                      </button>
                    ) : (
                      <button
                        onClick={handleImportData}
                        className="flex-1 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
                      >
                        Confirmer et importer
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Import Errors Modal */}
      {showErrorModal && importErrors.length > 0 && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-red-50">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 bg-red-100 rounded-full">
                  <AlertCircle className="w-6 h-6 text-red-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Erreurs d'Import
                  </h3>
                  <p className="text-sm text-gray-600">
                    {importErrors.length} ligne{importErrors.length > 1 ? 's' : ''} ignorée{importErrors.length > 1 ? 's' : ''}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowErrorModal(false)}
                className="p-2 hover:bg-red-100 rounded-lg transition-colors"
                title="Fermer"
              >
                <XCircle className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Modal Body - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-4">
                {importErrors.map((error, idx) => {
                  const errorTypeColors = {
                    missing_required_field: 'bg-red-100 text-red-800 border-red-200',
                    duplicate_key: 'bg-yellow-100 text-yellow-800 border-yellow-200',
                    sql_error: 'bg-orange-100 text-orange-800 border-orange-200',
                    empty_row: 'bg-gray-100 text-gray-800 border-gray-200',
                    constraint_violation: 'bg-purple-100 text-purple-800 border-purple-200'
                  };

                  const errorTypeLabels = {
                    missing_required_field: 'Champs manquants',
                    duplicate_key: 'Doublon',
                    sql_error: 'Erreur SQL',
                    empty_row: 'Ligne vide',
                    constraint_violation: 'Contrainte violée'
                  };

                  const colorClass = errorTypeColors[error.error_type as keyof typeof errorTypeColors] || 'bg-gray-100 text-gray-800 border-gray-200';
                  const label = errorTypeLabels[error.error_type as keyof typeof errorTypeLabels] || error.error_type;

                  return (
                    <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-gray-50">
                      {/* Error Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-mono font-semibold text-gray-700 bg-white px-3 py-1 rounded border border-gray-300">
                            Ligne {error.row_number}
                          </span>
                          <span className={`text-xs font-medium px-3 py-1 rounded border ${colorClass}`}>
                            {label}
                          </span>
                        </div>
                      </div>

                      {/* Error Message */}
                      <div className="mb-3">
                        <p className="text-sm text-gray-900 font-medium">
                          {error.error_message}
                        </p>
                      </div>

                      {/* Row Data - Collapsible */}
                      <details className="group">
                        <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800 font-medium flex items-center gap-1 select-none">
                          <span>▸</span>
                          <span>Voir les données de la ligne</span>
                        </summary>
                        <div className="mt-3 bg-white border border-gray-200 rounded p-3 overflow-x-auto">
                          <table className="min-w-full text-xs">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b">Colonne</th>
                                <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b">Valeur</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(error.row_data).map(([key, value], vidx) => (
                                <tr key={vidx} className="border-b last:border-b-0">
                                  <td className="px-3 py-2 font-mono font-semibold text-gray-600">{key}</td>
                                  <td className="px-3 py-2 text-gray-900 font-mono">
                                    {value !== null && value !== undefined && value !== ''
                                      ? String(value)
                                      : <span className="text-gray-400 italic">vide</span>
                                    }
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
              <p className="text-sm text-gray-600">
                💡 Corrigez les erreurs dans votre CSV et réessayez l'import
              </p>
              <button
                onClick={() => setShowErrorModal(false)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
