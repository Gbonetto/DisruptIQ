/**
 * DataTable - Tableau élégant avec tri, filtrage, pagination et export
 * Design: Minimaliste, moderne, performant
 */

import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, Search } from 'lucide-react';
import { ExportButton } from './ExportButton';

interface DataTableProps {
  data: any[];
  caption?: string;
  maxRows?: number;
  enableExport?: boolean;
  enableSearch?: boolean;
  enableSort?: boolean;
  className?: string;
}

type SortDirection = 'asc' | 'desc' | null;

export function DataTable({
  data,
  caption,
  maxRows = 10,
  enableExport = true,
  enableSearch = true,
  enableSort = true,
  className = '',
}: DataTableProps) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  if (!data || data.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4">
        Aucune donnée à afficher
      </div>
    );
  }

  // Get columns from first object
  const columns = Object.keys(data[0]);

  // Filter data based on search
  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) return data;

    return data.filter((row) =>
      Object.values(row).some((value) =>
        String(value).toLowerCase().includes(searchQuery.toLowerCase())
      )
    );
  }, [data, searchQuery]);

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortColumn || !sortDirection) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      // Handle nulls
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      // Compare
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      }

      const comparison = String(aVal).localeCompare(String(bVal));
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [filteredData, sortColumn, sortDirection]);

  // Pagination
  const totalPages = Math.ceil(sortedData.length / maxRows);
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * maxRows;
    return sortedData.slice(start, start + maxRows);
  }, [sortedData, currentPage, maxRows]);

  // Handle sort
  const handleSort = (column: string) => {
    if (!enableSort) return;

    if (sortColumn === column) {
      // Cycle: asc -> desc -> null
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else if (sortDirection === 'desc') {
        setSortColumn(null);
        setSortDirection(null);
      }
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  return (
    <div className={`my-6 ${className}`}>
      {/* Header: Caption + Actions */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          {caption && (
            <h3 className="text-sm font-semibold text-gray-800">{caption}</h3>
          )}
          <span className="text-xs text-gray-500">
            {sortedData.length} {sortedData.length === 1 ? 'ligne' : 'lignes'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          {enableSearch && data.length > 5 && (
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1); // Reset to first page
                }}
                placeholder="Rechercher..."
                className="pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          )}

          {/* Export button */}
          {enableExport && (
            <ExportButton
              data={sortedData}
              filename={caption || 'data'}
            />
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  onClick={() => handleSort(column)}
                  className={`px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider ${
                    enableSort ? 'cursor-pointer hover:bg-gray-100 transition-colors' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>{column}</span>
                    {enableSort && sortColumn === column && (
                      <span className="text-blue-600">
                        {sortDirection === 'asc' ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {paginatedData.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="hover:bg-gray-50 transition-colors"
              >
                {columns.map((column) => (
                  <td
                    key={column}
                    className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap"
                  >
                    {formatCellValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <div className="text-xs text-gray-600">
            Page {currentPage} sur {totalPages}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Précédent
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Suivant
            </button>
          </div>
        </div>
      )}

      {/* Empty state after search */}
      {filteredData.length === 0 && searchQuery && (
        <div className="text-center py-8 text-sm text-gray-500">
          Aucun résultat pour "{searchQuery}"
        </div>
      )}
    </div>
  );
}

// Format cell value (handle different types)
function formatCellValue(value: any): string {
  if (value == null) return '-';
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
