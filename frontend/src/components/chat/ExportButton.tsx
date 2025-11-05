/**
 * ExportButton - Export élégant de données en CSV/Excel/JSON
 * Design: Dropdown minimaliste avec icônes
 */

import { useState } from 'react';
import { Download, FileText, File, FileJson, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as Papa from 'papaparse';
import * as XLSX from 'xlsx';

interface ExportButtonProps {
  data: any[];
  filename?: string;
  className?: string;
}

type ExportFormat = 'csv' | 'excel' | 'json';

export function ExportButton({ data, filename = 'data', className = '' }: ExportButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleExport = (format: ExportFormat) => {
    setIsOpen(false);

    switch (format) {
      case 'csv':
        exportToCSV(data, filename);
        break;
      case 'excel':
        exportToExcel(data, filename);
        break;
      case 'json':
        exportToJSON(data, filename);
        break;
    }
  };

  if (!data || data.length === 0) return null;

  return (
    <div className={`relative inline-block ${className}`}>
      {/* Button principal */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg transition-colors shadow-sm"
      >
        <Download className="w-4 h-4" />
        <span>Exporter</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown menu */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop transparent pour fermer */}
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />

            {/* Menu */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -10 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20"
            >
              {/* Option CSV */}
              <button
                onClick={() => handleExport('csv')}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <FileText className="w-4 h-4 text-gray-500" />
                <div className="text-left">
                  <div className="font-medium">CSV</div>
                  <div className="text-xs text-gray-500">Format tableur</div>
                </div>
              </button>

              {/* Option Excel */}
              <button
                onClick={() => handleExport('excel')}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <File className="w-4 h-4 text-green-600" />
                <div className="text-left">
                  <div className="font-medium">Excel</div>
                  <div className="text-xs text-gray-500">Fichier .xlsx</div>
                </div>
              </button>

              {/* Option JSON */}
              <button
                onClick={() => handleExport('json')}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <FileJson className="w-4 h-4 text-blue-600" />
                <div className="text-left">
                  <div className="font-medium">JSON</div>
                  <div className="text-xs text-gray-500">Format développeur</div>
                </div>
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

// === Export Functions ===

function exportToCSV(data: any[], filename: string) {
  const csv = Papa.unparse(data);
  downloadFile(csv, `${filename}.csv`, 'text/csv;charset=utf-8;');
}

function exportToExcel(data: any[], filename: string) {
  const worksheet = XLSX.utils.json_to_sheet(data);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');

  // Write file
  XLSX.writeFile(workbook, `${filename}.xlsx`);
}

function exportToJSON(data: any[], filename: string) {
  const json = JSON.stringify(data, null, 2);
  downloadFile(json, `${filename}.json`, 'application/json;charset=utf-8;');
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
