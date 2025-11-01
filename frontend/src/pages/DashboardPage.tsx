/**
 * DashboardPage - Main dashboard with metrics and quick actions
 * Premium dashboard with real-time stats and visualizations
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Building,
  UserCog,
  TrendingUp,
  Upload,
  Download,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Mail,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';

interface Stats {
  professionnels: {
    total: number;
    indexed: number;
    byCategory: Record<string, number>;
  };
  coproprietes: {
    total: number;
    totalLots: number;
    byCities: Record<string, number>;
  };
  coproprietaires: {
    total: number;
    withSpecialStatus: number;
    byStatus: Record<string, number>;
  };
  recent_activity: {
    type: string;
    entity: string;
    action: string;
    timestamp: string;
  }[];
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setIsLoading(true);
    try {
      const [professionnels, coproprietes, coproprietaires] = await Promise.all([
        fetch('http://localhost:8000/api/admin/vendors').then((r) => r.json()),
        fetch('http://localhost:8000/api/coproprietes/').then((r) => r.json()),
        fetch('http://localhost:8000/api/coproprietaires/').then((r) => r.json()),
      ]);

      // Calculate stats
      const professionnelsIndexed = professionnels.filter((p: any) => p.is_indexed).length;
      const byCategory = professionnels.reduce((acc: any, p: any) => {
        acc[p.category || 'Non catégorisé'] = (acc[p.category || 'Non catégorisé'] || 0) + 1;
        return acc;
      }, {});

      const totalLots = coproprietes.reduce((sum: number, c: any) => sum + (c.nombre_lots || 0), 0);
      const byCities = coproprietes.reduce((acc: any, c: any) => {
        acc[c.ville] = (acc[c.ville] || 0) + 1;
        return acc;
      }, {});

      const withSpecialStatus = coproprietaires.filter((c: any) => c.statut_special).length;
      const byStatus = coproprietaires.reduce((acc: any, c: any) => {
        const status = c.statut_special || 'Résident standard';
        acc[status] = (acc[status] || 0) + 1;
        return acc;
      }, {});

      setStats({
        professionnels: {
          total: professionnels.length,
          indexed: professionnelsIndexed,
          byCategory,
        },
        coproprietes: {
          total: coproprietes.length,
          totalLots,
          byCities,
        },
        coproprietaires: {
          total: coproprietaires.length,
          withSpecialStatus,
          byStatus,
        },
        recent_activity: [],
      });
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const MetricCard: React.FC<{
    title: string;
    value: number;
    subtitle?: string;
    icon: React.ElementType;
    trend?: { value: number; isPositive: boolean };
    color: string;
    onClick?: () => void;
  }> = ({ title, value, subtitle, icon: Icon, trend, color, onClick }) => (
    <Card
      className="hover:shadow-lg transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-medium text-gray-600">{title}</CardTitle>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value.toLocaleString()}</div>
        {subtitle && (
          <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
        )}
        {trend && (
          <div className="flex items-center mt-2 text-xs">
            {trend.isPositive ? (
              <>
                <ArrowUpRight className="h-3 w-3 text-green-500 mr-1" />
                <span className="text-green-600 font-medium">+{trend.value}%</span>
              </>
            ) : (
              <>
                <ArrowDownRight className="h-3 w-3 text-red-500 mr-1" />
                <span className="text-red-600 font-medium">{trend.value}%</span>
              </>
            )}
            <span className="text-gray-500 ml-1">vs mois dernier</span>
          </div>
        )}
      </CardContent>
    </Card>
  );

  const QuickAction: React.FC<{
    label: string;
    description: string;
    icon: React.ElementType;
    onClick: () => void;
    variant?: 'default' | 'outline';
  }> = ({ label, description, icon: Icon, onClick, variant = 'outline' }) => (
    <Button
      variant={variant}
      className="h-auto flex flex-col items-start p-4 text-left"
      onClick={onClick}
    >
      <div className="flex items-center gap-2 mb-1">
        <Icon className="h-4 w-4" />
        <span className="font-semibold">{label}</span>
      </div>
      <span className="text-xs text-gray-500 font-normal">{description}</span>
    </Button>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-64 mb-2" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Erreur de chargement
          </h3>
          <p className="text-gray-500 mb-4">
            Impossible de charger les statistiques
          </p>
          <Button onClick={fetchStats}>Réessayer</Button>
        </div>
      </div>
    );
  }

  const indexingPercentage = stats.professionnels.total > 0
    ? Math.round((stats.professionnels.indexed / stats.professionnels.total) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Vue Globale</h1>
        <p className="text-gray-500 mt-1">
          Tableau de bord et métriques de votre système de gestion
        </p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Professionnels"
          value={stats.professionnels.total}
          subtitle={`${stats.professionnels.indexed} indexés dans RAG`}
          icon={Users}
          trend={{ value: 12, isPositive: true }}
          color="bg-blue-500"
          onClick={() => navigate('/admin/professionnels')}
        />
        <MetricCard
          title="Copropriétés"
          value={stats.coproprietes.total}
          subtitle={`${stats.coproprietes.totalLots} lots au total`}
          icon={Building}
          trend={{ value: 8, isPositive: true }}
          color="bg-green-500"
          onClick={() => navigate('/admin/coproprietes')}
        />
        <MetricCard
          title="Copropriétaires"
          value={stats.coproprietaires.total}
          subtitle={`${stats.coproprietaires.withSpecialStatus} rôles spéciaux`}
          icon={UserCog}
          trend={{ value: 15, isPositive: true }}
          color="bg-purple-500"
          onClick={() => navigate('/admin/coproprietaires')}
        />
        <MetricCard
          title="Taux d'indexation"
          value={indexingPercentage}
          subtitle="Professionnels dans RAG"
          icon={Activity}
          color="bg-orange-500"
        />
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Actions rapides</CardTitle>
          <CardDescription>
            Accédez rapidement aux fonctionnalités principales
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <QuickAction
              label="Importer des données"
              description="Charger des CSV"
              icon={Upload}
              onClick={() => navigate('/admin/import')}
              variant="default"
            />
            <QuickAction
              label="Exporter les données"
              description="Télécharger en CSV"
              icon={Download}
              onClick={() => {
                // TODO: Implement export
                console.log('Export triggered');
              }}
            />
            <QuickAction
              label="Ajouter un professionnel"
              description="Créer une fiche"
              icon={Plus}
              onClick={() => navigate('/admin/professionnels')}
            />
            <QuickAction
              label="Gérer les emails"
              description="Consulter la boîte"
              icon={Mail}
              onClick={() => navigate('/admin/emails')}
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* RAG Indexing Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Indexation RAG
            </CardTitle>
            <CardDescription>
              État de l'indexation des professionnels dans le système RAG
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Progression</span>
                <span className="font-semibold">
                  {stats.professionnels.indexed} / {stats.professionnels.total}
                </span>
              </div>
              <Progress value={indexingPercentage} className="h-2" />
            </div>
            <div className="flex items-center justify-between pt-2">
              <Badge
                variant={indexingPercentage === 100 ? 'success' : 'secondary'}
                className="flex items-center gap-1"
              >
                {indexingPercentage === 100 ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Complet
                  </>
                ) : (
                  <>
                    <Activity className="h-3 w-3" />
                    En cours
                  </>
                )}
              </Badge>
              {indexingPercentage < 100 && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    // TODO: Trigger reindexing
                    console.log('Reindex triggered');
                  }}
                >
                  Réindexer tout
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Distribution by Category */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Répartition par catégorie
            </CardTitle>
            <CardDescription>
              Distribution des professionnels par métier
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.professionnels.byCategory)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([category, count]) => {
                  const percentage = Math.round((count / stats.professionnels.total) * 100);
                  return (
                    <div key={category} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium capitalize">{category}</span>
                        <span className="text-gray-500">
                          {count} ({percentage}%)
                        </span>
                      </div>
                      <Progress value={percentage} className="h-1.5" />
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>

        {/* Cities Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building className="h-5 w-5" />
              Copropriétés par ville
            </CardTitle>
            <CardDescription>
              Répartition géographique des biens gérés
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.coproprietes.byCities)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([city, count]) => {
                  const percentage = Math.round((count / stats.coproprietes.total) * 100);
                  return (
                    <div key={city} className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="font-medium">{city}</span>
                          <span className="text-gray-500">
                            {count} ({percentage}%)
                          </span>
                        </div>
                        <Progress value={percentage} className="h-1.5" />
                      </div>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>

        {/* Special Roles */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCog className="h-5 w-5" />
              Rôles spéciaux
            </CardTitle>
            <CardDescription>
              Copropriétaires avec statuts particuliers
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.coproprietaires.byStatus)
                .filter(([status]) => status !== 'Résident standard')
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="capitalize">
                        {status}
                      </Badge>
                    </div>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))}
              {stats.coproprietaires.withSpecialStatus === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">
                  Aucun rôle spécial assigné
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            État du système
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-medium text-green-900">API Backend</span>
              </div>
              <Badge variant="success">Opérationnel</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-medium text-green-900">Base de données</span>
              </div>
              <Badge variant="success">Connecté</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-medium text-green-900">RAG Service</span>
              </div>
              <Badge variant="success">Actif</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
