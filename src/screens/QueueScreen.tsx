import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '@/api/useApi';
import type { ClientEntity, WorkRequest } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

// Labels for work_requests.status (Part D.1). Display copy only.
const STATUS_FR: Record<string, string> = {
  draft: 'Brouillon',
  intake: 'Réception',
  extracting: 'Lecture',
  preparing: 'Préparation',
  reconciling: 'Rapprochement',
  quality_check: 'Contrôle',
  needs_attention: 'À traiter',
  awaiting_approval: 'À valider',
  exporting: 'Export',
  completed: 'Terminé',
  completed_with_open_items: 'Terminé avec anomalies',
  cancelled: 'Annulé',
  failed: 'En échec',
};
/** States waiting on a person get the pink rule (Part E.2). */
const NEEDS_PERSON = new Set(['needs_attention', 'awaiting_approval']);

type State =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'ready'; rows: WorkRequest[]; clients: Map<string, ClientEntity> };

export function QueueScreen() {
  const api = useApi();
  const [state, setState] = useState<State>({ kind: 'loading' });

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const [wr, ce] = await Promise.all([api.GET('/work-requests'), api.GET('/client-entities')]);
      if (!wr.data || wr.error || !ce.data || ce.error) throw new Error('api');
      setState({ kind: 'ready', rows: wr.data.items, clients: new Map(ce.data.items.map((c) => [c.id, c])) });
    } catch {
      setState({ kind: 'error' });
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <h1 className="text-[1.75rem]">Dossiers mensuels</h1>
      <div className="mt-6">
        {state.kind === 'loading' && <LoadingState label="Chargement des dossiers…" />}
        {state.kind === 'error' && (
          <ErrorState
            title="Les dossiers n'ont pas pu être chargés."
            detail="Le serveur AVENEL ne répond pas. Réessayez dans un instant ; si le problème continue, contactez l'administrateur du cabinet."
            action={
              <Button variant="secondary" onClick={() => void load()}>
                Réessayer
              </Button>
            }
          />
        )}
        {state.kind === 'ready' && state.rows.length === 0 && (
          <EmptyState title="Aucun dossier mensuel. Créez un dossier pour commencer." />
        )}
        {state.kind === 'ready' && state.rows.length > 0 && (
          <table className="w-full border-collapse text-sm" data-testid="queue-table">
            <thead className="bg-surface text-left text-ink-2">
              <tr className="h-9 border-b border-line">
                <th scope="col" className="px-3 font-medium">
                  Société
                </th>
                <th scope="col" className="px-3 font-medium">
                  État
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Révision
                </th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((r) => {
                const c = state.clients.get(r.client_entity_id);
                const needsPerson = NEEDS_PERSON.has(r.status);
                return (
                  <tr
                    key={r.id}
                    data-testid="queue-row"
                    data-work-request-id={r.id}
                    className={`h-9 border-b border-l-[3px] border-b-line ${needsPerson ? 'border-l-pink' : 'border-l-transparent'}`}
                  >
                    <td className="px-3">
                      <Link to={`/files/${r.id}`} className="text-sky-ink hover:underline">{c?.legal_name ?? '—'}</Link>
                    </td>
                    <td className={`px-3 ${needsPerson ? 'text-pink-ink' : 'text-ink'}`}>
                      {STATUS_FR[r.status] ?? r.status}
                    </td>
                    <td className="px-3 text-right tabular-nums">{r.current_revision ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
