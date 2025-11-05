/**
 * AppLayout - Main application layout with sidebar navigation
 * Premium layout with Command Palette and responsive design
 */

import React, { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Building,
  UserCog,
  Upload,
  FileText,
  Settings,
  Search,
  Bell,
  Menu,
  X,
  Newspaper,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CommandPalette } from '@/components/command-palette';
import { Badge } from '@/components/ui/badge';

interface SidebarItem {
  id: string;
  label: string;
  icon: React.ElementType;
  href: string;
  badge?: string;
  group?: string;
}

const sidebarItems: SidebarItem[] = [
  {
    id: 'dashboard',
    label: 'Vue Globale',
    icon: LayoutDashboard,
    href: '/admin',
    group: 'main',
  },
  {
    id: 'digest',
    label: 'Digest Quotidien',
    icon: Newspaper,
    href: '/admin/digest',
    group: 'main',
  },
  {
    id: 'professionnels',
    label: 'Professionnels',
    icon: Users,
    href: '/admin/professionnels',
    badge: '47',
    group: 'data',
  },
  {
    id: 'coproprietes',
    label: 'Copropriétés',
    icon: Building,
    href: '/admin/coproprietes',
    badge: '12',
    group: 'data',
  },
  {
    id: 'coproprietaires',
    label: 'Copropriétaires',
    icon: UserCog,
    href: '/admin/coproprietaires',
    badge: '156',
    group: 'data',
  },
  {
    id: 'import',
    label: 'Import Données',
    icon: Upload,
    href: '/admin/import',
    group: 'tools',
  },
  {
    id: 'documents',
    label: 'Documents',
    icon: FileText,
    href: '/admin/documents',
    group: 'tools',
  },
  {
    id: 'settings',
    label: 'Configuration',
    icon: Settings,
    href: '/admin/settings',
    group: 'settings',
  },
];

const groupLabels = {
  main: '',
  data: 'Données',
  tools: 'Outils',
  settings: 'Paramètres',
};

export const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Group items by group
  const groupedItems = sidebarItems.reduce((acc, item) => {
    const group = item.group || 'main';
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {} as Record<string, SidebarItem[]>);

  // Handle keyboard shortcut for Command Palette
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const isActive = (href: string) => {
    if (href === '/admin') {
      return location.pathname === '/admin';
    }
    return location.pathname.startsWith(href);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar - Desktop */}
      <aside
        className={cn(
          'hidden md:flex flex-col bg-white border-r border-gray-200 transition-all duration-300',
          sidebarOpen ? 'w-64' : 'w-20'
        )}
      >
        {/* Logo & Toggle */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
          {sidebarOpen && (
            <h1 className="text-xl font-bold text-gray-900">
              📊 DisruptIQ
            </h1>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="ml-auto"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-2">
          {Object.entries(groupedItems).map(([group, items]) => (
            <div key={group} className="mb-6">
              {sidebarOpen && groupLabels[group as keyof typeof groupLabels] && (
                <h3 className="px-3 mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {groupLabels[group as keyof typeof groupLabels]}
                </h3>
              )}
              <div className="space-y-1">
                {items.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);

                  return (
                    <button
                      key={item.id}
                      onClick={() => navigate(item.href)}
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                        active
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-gray-700 hover:bg-gray-100'
                      )}
                    >
                      <Icon className={cn('h-5 w-5 flex-shrink-0', active && 'text-blue-600')} />
                      {sidebarOpen && (
                        <>
                          <span className="flex-1 text-left">{item.label}</span>
                          {item.badge && (
                            <Badge variant={active ? 'default' : 'secondary'} className="text-xs">
                              {item.badge}
                            </Badge>
                          )}
                        </>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User Profile */}
        {sidebarOpen && (
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-semibold">
                A
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  Admin User
                </p>
                <p className="text-xs text-gray-500 truncate">
                  admin@disruptiq.com
                </p>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* Mobile Sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white shadow-xl">
            <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
              <h1 className="text-xl font-bold text-gray-900">📊 DisruptIQ</h1>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileMenuOpen(false)}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            <nav className="flex-1 overflow-y-auto py-4 px-2">
              {Object.entries(groupedItems).map(([group, items]) => (
                <div key={group} className="mb-6">
                  {groupLabels[group as keyof typeof groupLabels] && (
                    <h3 className="px-3 mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      {groupLabels[group as keyof typeof groupLabels]}
                    </h3>
                  )}
                  <div className="space-y-1">
                    {items.map((item) => {
                      const Icon = item.icon;
                      const active = isActive(item.href);

                      return (
                        <button
                          key={item.id}
                          onClick={() => {
                            navigate(item.href);
                            setMobileMenuOpen(false);
                          }}
                          className={cn(
                            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                            active
                              ? 'bg-blue-50 text-blue-700'
                              : 'text-gray-700 hover:bg-gray-100'
                          )}
                        >
                          <Icon className={cn('h-5 w-5', active && 'text-blue-600')} />
                          <span className="flex-1 text-left">{item.label}</span>
                          {item.badge && (
                            <Badge variant={active ? 'default' : 'secondary'}>
                              {item.badge}
                            </Badge>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            {/* Mobile Menu Toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Search Button - Opens Command Palette */}
            <Button
              variant="outline"
              className="w-full max-w-xs justify-start text-sm text-gray-500"
              onClick={() => setCommandPaletteOpen(true)}
            >
              <Search className="h-4 w-4 mr-2" />
              Rechercher...
              <kbd className="ml-auto pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
                <span className="text-xs">⌘</span>K
              </kbd>
            </Button>
          </div>

          <div className="flex items-center gap-2">
            {/* Notifications */}
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
            </Button>

            {/* User Menu */}
            <Button variant="ghost" className="hidden md:flex">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-semibold text-sm">
                A
              </div>
            </Button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      {/* Command Palette */}
      <CommandPalette
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
      />
    </div>
  );
};
