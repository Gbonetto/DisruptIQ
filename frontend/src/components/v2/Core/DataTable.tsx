import React, { useState } from 'react';
import { Download, FileDown, ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export interface DataTableProps {
  title?: string;
  headers: string[];
  rows: (string | number)[][];
  sortable?: boolean;
  paginate?: boolean;
  pageSize?: number;
}

export const DataTable: React.FC<DataTableProps> = ({
  title,
  headers,
  rows,
  sortable = true,
  paginate = true,
  pageSize = 50,
}) => {
  const [sortConfig, setSortConfig] = useState<{
    key: number;
    direction: 'asc' | 'desc';
  } | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Sort logic
  const sortedRows = React.useMemo(() => {
    if (!sortConfig) return rows;

    return [...rows].sort((a, b) => {
      const aValue = a[sortConfig.key];
      const bValue = b[sortConfig.key];

      if (aValue < bValue) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  }, [rows, sortConfig]);

  // Pagination logic
  const paginatedRows = React.useMemo(() => {
    if (!paginate || sortedRows.length <= pageSize) return sortedRows;

    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    return sortedRows.slice(startIndex, endIndex);
  }, [sortedRows, currentPage, paginate, pageSize]);

  const totalPages = Math.ceil(sortedRows.length / pageSize);

  const handleSort = (columnIndex: number) => {
    if (!sortable) return;

    setSortConfig((current) => {
      if (!current || current.key !== columnIndex) {
        return { key: columnIndex, direction: 'asc' };
      }
      if (current.direction === 'asc') {
        return { key: columnIndex, direction: 'desc' };
      }
      return null;
    });
  };

  // Export functions
  const exportToCSV = () => {
    const csvContent = [
      headers.join(','),
      ...rows.map((row) =>
        row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')
      ),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${title || 'data'}.csv`;
    link.click();
  };

  const exportToExcel = async () => {
    // Using xlsx library (already installed according to the plan)
    try {
      const XLSX = await import('xlsx');
      const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Data');
      XLSX.writeFile(wb, `${title || 'data'}.xlsx`);
    } catch (error) {
      console.error('Failed to export to Excel:', error);
      // Fallback to CSV if xlsx fails
      exportToCSV();
    }
  };

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card">
      {/* Header */}
      {(title || true) && (
        <div className="p-4 border-b border-border flex items-center justify-between bg-secondary/30">
          <h3 className="text-sm font-semibold text-foreground">
            {title || 'Tableau de données'}
          </h3>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                <Download className="w-4 h-4" />
                Exporter
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={exportToCSV}>
                <FileDown className="w-4 h-4 mr-2" />
                Exporter en CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={exportToExcel}>
                <FileDown className="w-4 h-4 mr-2" />
                Exporter en Excel
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto scroll-smooth hover:scrollbar-thumb-primary">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/50">
              {headers.map((header, index) => (
                <th
                  key={index}
                  onClick={() => handleSort(index)}
                  className={`
                    px-4 py-3 text-left font-semibold text-foreground
                    ${sortable ? 'cursor-pointer hover:bg-secondary/70 select-none' : ''}
                  `}
                >
                  <div className="flex items-center gap-2">
                    {header}
                    {sortable && sortConfig?.key === index && (
                      <span className="text-muted-foreground">
                        {sortConfig.direction === 'asc' ? (
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
          <tbody>
            {paginatedRows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-border hover:bg-secondary/30 transition-colors"
              >
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="px-4 py-3 text-muted-foreground"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {paginate && totalPages > 1 && (
        <div className="p-4 border-t border-border flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {currentPage} sur {totalPages} ({sortedRows.length} lignes)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              Précédent
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Suivant
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
