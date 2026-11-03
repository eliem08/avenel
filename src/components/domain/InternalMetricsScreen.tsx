import React from 'react';
import { Clock, CheckSquare, Edit3, DollarSign, ShieldAlert } from 'lucide-react';

export interface UserReviewMetric {
  user_id: string;
  user_name: string;
  user_email: string;
  active_review_seconds: number;
  fields_corrected: number;
  entries_edited: number;
  issues_resolved: number;
}

export interface FileMetricsSummary {
  work_request_id: string;
  status: string;
  client_name: string;
  period_name: string;
  file_review_seconds: number;
  file_fields_corrected: number;
  file_entries_edited: number;
  file_issues_resolved: number;
  provider_cost_mad: number;
  cost_per_accepted_file_mad: number;
  billable_units: number;
  users: UserReviewMetric[];
}

export interface InternalMetricsData {
  summary: {
    total_active_review_seconds: number;
    total_active_review_minutes: number;
    total_fields_corrected: number;
    total_entries_edited: number;
    total_issues_resolved: number;
    total_provider_calls: number;
    total_provider_cost_mad: number;
    accepted_files_count: number;
    average_cost_per_file_mad: number;
    provider_cost_label_fr?: string;
    provider_cost_label_en?: string;
  };
  files: FileMetricsSummary[];
}

interface InternalMetricsScreenProps {
  currentUserRole: 'owner' | 'operator' | 'accountant' | 'staff' | 'client_user';
  metrics: InternalMetricsData;
}

function formatSeconds(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins} min ${secs.toString().padStart(2, '0')} s`;
}

export function InternalMetricsScreen({
  currentUserRole,
  metrics,
}: InternalMetricsScreenProps) {
  // Enforce Part A / Prompt 01 RBAC: owner and operator only
  if (currentUserRole !== 'owner' && currentUserRole !== 'operator') {
    return (
      <div className="max-w-4xl mx-auto py-12 px-6">
        <div className="bg-surface border border-line rounded-panel p-6 flex items-start gap-4">
          <ShieldAlert className="w-6 h-6 text-fail flex-shrink-0 mt-0.5" />
          <div>
            <h2 className="text-lg font-semibold text-fail">Accès restreint</h2>
            <p className="text-sm text-fail mt-1">
              Cette page d'indicateurs internes est réservée exclusivement aux associés du cabinet
              (propriétaires) et aux opérateurs de la plateforme.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { summary, files } = metrics;

  return (
    <div className="max-w-6xl mx-auto py-8 px-6 font-sans">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">
              Indicateurs internes — Effort de révision & coûts
            </h1>
            <p className="text-sm text-ink-2 mt-1">
              Mesure de l'effort humain actif et coût réel de traitement par dossier mensuel validé.
            </p>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-surface text-ink border border-line">
            Rôle : {currentUserRole === 'owner' ? 'Associé (Owner)' : 'Opérateur (Operator)'}
          </span>
        </div>
      </div>

      {/* Aggregate KPI tiles */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-paper border border-line rounded-panel p-5 ">
          <div className="flex items-center gap-3 text-ink-2 mb-2">
            <Clock className="w-5 h-5 text-ink" />
            <span className="text-xs uppercase tracking-wider font-semibold">Temps actif moyen / dossier</span>
          </div>
          <div className="text-2xl font-bold text-ink" data-testid="metric-review-time">
            {formatSeconds(summary.total_active_review_seconds)}
          </div>
          <div className="text-xs text-ink-2 mt-1">
            Total : {summary.total_active_review_minutes} min sur {files.length} dossier(s)
          </div>
        </div>

        <div className="bg-paper border border-line rounded-panel p-5 ">
          <div className="flex items-center gap-3 text-ink-2 mb-2">
            <Edit3 className="w-5 h-5 text-pink-ink" />
            <span className="text-xs uppercase tracking-wider font-semibold">Corrections humaines</span>
          </div>
          <div className="text-2xl font-bold text-ink" data-testid="metric-corrections">
            {summary.total_fields_corrected} champ(s)
          </div>
          <div className="text-xs text-ink-2 mt-1">
            {summary.total_entries_edited} écriture(s) modifiée(s)
          </div>
        </div>

        <div className="bg-paper border border-line rounded-panel p-5 ">
          <div className="flex items-center gap-3 text-ink-2 mb-2">
            <CheckSquare className="w-5 h-5 text-ok" />
            <span className="text-xs uppercase tracking-wider font-semibold">Anomalies résolues</span>
          </div>
          <div className="text-2xl font-bold text-ink" data-testid="metric-issues-resolved">
            {summary.total_issues_resolved}
          </div>
          <div className="text-xs text-ink-2 mt-1">
            Revue document et rapprochement
          </div>
        </div>

        <div className="bg-paper border border-line rounded-panel p-5 ">
          <div className="flex items-center gap-3 text-ink-2 mb-2">
            <DollarSign className="w-5 h-5 text-ok" />
            <span className="text-xs uppercase tracking-wider font-semibold">Coût fournisseurs par dossier validé</span>
          </div>
          <div className="text-2xl font-bold text-ink" data-testid="metric-cost-per-file">
            {summary.average_cost_per_file_mad.toFixed(4)} MAD
          </div>
          <div className="text-xs text-ink-2 mt-1">
            Provider cost per accepted file ({summary.total_provider_calls} appel(s))
          </div>
        </div>
      </div>

      {/* Placeholders for compute and reviewer cost models (pilot telemetry) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="bg-surface border border-dashed border-line rounded-panel p-4 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase tracking-wider font-semibold text-ink-2">Coût calcul serveur (estimé) / Compute cost</span>
            <div className="text-sm font-medium text-ink mt-0.5">Inférence locale & runtime conteneurs</div>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-panel text-xs font-medium bg-line text-ink border border-line">
            Non calculé (pilote)
          </span>
        </div>

        <div className="bg-surface border border-dashed border-line rounded-panel p-4 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase tracking-wider font-semibold text-ink-2">Coût réviseur humain / Reviewer cost</span>
            <div className="text-sm font-medium text-ink mt-0.5">Taux horaire collaborateur par dossier</div>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-panel text-xs font-medium bg-line text-ink border border-line">
            Non calculé (pilote)
          </span>
        </div>
      </div>

      {/* Files breakdown table */}
      <div className="bg-paper border border-line rounded-panel  overflow-hidden">
        <div className="px-6 py-4 border-b border-line bg-surface flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-ink">
            Détail par dossier mensuel
          </h2>
          <span className="text-xs text-ink-2">
            {files.length} dossier(s) audité(s)
          </span>
        </div>

        <table className="min-w-full divide-y divide-line text-left text-sm">
          <thead className="bg-surface text-xs font-semibold text-ink-2 uppercase">
            <tr>
              <th className="px-6 py-3">Entreprise cliente</th>
              <th className="px-4 py-3">Période</th>
              <th className="px-4 py-3">Collaborateur</th>
              <th className="px-4 py-3 text-right">Temps actif</th>
              <th className="px-4 py-3 text-right">Champs corrigés</th>
              <th className="px-4 py-3 text-right">Écritures</th>
              <th className="px-4 py-3 text-right">Anomalies</th>
              <th className="px-6 py-3 text-right">Coût fournisseurs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-paper">
            {files.map((file) => (
              <React.Fragment key={file.work_request_id}>
                {file.users.map((user) => (
                  <tr key={`${file.work_request_id}-${user.user_id}`} className="hover:bg-surface">
                    <td className="px-6 py-4 font-medium text-ink">
                      <div>{file.client_name}</div>
                    </td>
                    <td className="px-4 py-4 font-mono text-ink">{file.period_name}</td>
                    <td className="px-4 py-4 text-ink">
                      <div>{user.user_name}</div>
                      <div className="text-xs text-ink-2">{user.user_email}</div>
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-ink">
                      {formatSeconds(user.active_review_seconds)}
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-pink-ink font-semibold">
                      {user.fields_corrected}
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-ink">
                      {user.entries_edited}
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-ok font-semibold">
                      {user.issues_resolved}
                    </td>
                    <td className="px-6 py-4 text-right font-mono font-medium text-ink">
                      {file.provider_cost_mad.toFixed(4)} MAD
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
