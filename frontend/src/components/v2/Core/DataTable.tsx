import React, { useState } from 'react';
import { Download, FileDown, ChevronUp, ChevronDown, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
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
  headers: rawHeaders,
  rows: rawRows,
  sortable = true,
  paginate = true,
  pageSize = 10,
}) => {
  // Ensure headers and rows are always valid arrays (before any hooks)
  const headers = Array.isArray(rawHeaders) ? rawHeaders : [];
  const rows = Array.isArray(rawRows) ? rawRows : [];

  const [sortConfig, setSortConfig] = useState<{
    key: number;
    direction: 'asc' | 'desc';
  } | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isExporting, setIsExporting] = useState(false);

  // Sort logic - with safeguard for empty rows
  const sortedRows = React.useMemo(() => {
    if (rows.length === 0) return [];
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

  // Pagination logic with adaptive page size
  const effectivePageSize = React.useMemo(() => {
    // If total rows <= 20, show all rows on first page
    if (!sortedRows || sortedRows.length === 0) return pageSize;
    if (sortedRows.length <= 20) return sortedRows.length;
    return pageSize;
  }, [sortedRows, pageSize]);

  const paginatedRows = React.useMemo(() => {
    if (!sortedRows || sortedRows.length === 0) return [];
    if (!paginate || sortedRows.length <= effectivePageSize) return sortedRows;

    const startIndex = (currentPage - 1) * effectivePageSize;
    const endIndex = startIndex + effectivePageSize;
    return sortedRows.slice(startIndex, endIndex);
  }, [sortedRows, currentPage, paginate, effectivePageSize]);

  const totalPages = sortedRows.length > 0 && effectivePageSize > 0
    ? Math.ceil(sortedRows.length / effectivePageSize)
    : 1;

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
    try {
      setIsExporting(true);

      // Add BOM for UTF-8 encoding (helps Excel open CSV correctly with accents)
      const BOM = '\uFEFF';
      const csvContent = BOM + [
        headers.join(','),
        ...rows.map((row) =>
          row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')
        ),
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${title || 'export'}_${new Date().toISOString().split('T')[0]}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);

      toast.success(`${rows.length} lignes exportées en CSV`);
    } catch (error) {
      console.error('CSV export failed:', error);
      toast.error('Erreur lors de l\'export CSV');
    } finally {
      setIsExporting(false);
    }
  };

  const exportToExcel = async () => {
    // Using exceljs (secure alternative to xlsx)
    try {
      setIsExporting(true);

      const ExcelJS = await import('exceljs');
      const workbook = new ExcelJS.Workbook();
      const worksheet = workbook.addWorksheet('Données');

      // Add metadata
      workbook.creator = 'DisruptIQ';
      workbook.created = new Date();

      // Add headers and rows
      worksheet.addRow(headers);
      rows.forEach(row => worksheet.addRow(row));

      // Style header row
      worksheet.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
      worksheet.getRow(1).fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FF4472C4' }
      };
      worksheet.getRow(1).alignment = { vertical: 'middle', horizontal: 'left' };

      // Auto-size columns based on content
      worksheet.columns.forEach((column, index) => {
        let maxLength = headers[index]?.length || 10;
        rows.forEach(row => {
          const cellValue = String(row[index] || '');
          maxLength = Math.max(maxLength, cellValue.length);
        });
        column.width = Math.min(maxLength + 2, 50);
      });

      // Add borders to all cells
      worksheet.eachRow((row, rowNumber) => {
        row.eachCell((cell) => {
          cell.border = {
            top: { style: 'thin' },
            left: { style: 'thin' },
            bottom: { style: 'thin' },
            right: { style: 'thin' }
          };
        });
      });

      // Download file
      const buffer = await workbook.xlsx.writeBuffer();
      const blob = new Blob([buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${title || 'export'}_${new Date().toISOString().split('T')[0]}.xlsx`;
      link.click();
      URL.revokeObjectURL(link.href);

      toast.success(`${rows.length} lignes exportées en Excel`);
    } catch (error) {
      console.error('Failed to export to Excel:', error);
      toast.error('Erreur lors de l\'export Excel, tentative CSV...');
      // Fallback to CSV if exceljs fails
      exportToCSV();
    } finally {
      setIsExporting(false);
    }
  };

  // Early return if no data to display (after all hooks)
  if (headers.length === 0 && rows.length === 0) {
    return null;
  }

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
              <Button variant="outline" size="sm" className="gap-2" disabled={isExporting}>
                {isExporting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Export...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    Exporter
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={exportToCSV} disabled={isExporting}>
                <FileDown className="w-4 h-4 mr-2" />
                Exporter en CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={exportToExcel} disabled={isExporting}>
                <FileDown className="w-4 h-4 mr-2" />
                Exporter en Excel
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto scroll-smooth hover:scrollbar-thumb-primary">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="border-b border-border bg-secondary/50">
              {headers.map((header, index) => (
                <th
                  key={index}
                  onClick={() => handleSort(index)}
                  className={`
                    px-3 py-2 text-left font-semibold text-foreground text-xs whitespace-nowrap
                    ${sortable ? 'cursor-pointer hover:bg-secondary/70 select-none' : ''}
                  `}
                >
                  <div className="flex items-center gap-1">
                    <span className="truncate">{header}</span>
                    {sortable && sortConfig?.key === index && (
                      <span className="text-muted-foreground flex-shrink-0">
                        {sortConfig.direction === 'asc' ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
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
                    className="px-3 py-2 text-muted-foreground text-xs max-w-[200px] truncate"
                    title={String(cell)}
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
