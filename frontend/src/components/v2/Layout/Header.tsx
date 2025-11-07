import React from 'react';
import { FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HeaderProps {
  onToggleDocuments?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleDocuments }) => {
  return (
    <header className="h-[60px] border-b border-border bg-secondary/50 backdrop-blur-sm">
      <div className="h-full px-6 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-foreground">
            DisruptIQ
          </h1>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleDocuments}
            className="gap-2"
          >
            <FileText className="w-4 h-4" />
            Documents
          </Button>
        </div>
      </div>
    </header>
  );
};
