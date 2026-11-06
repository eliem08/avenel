import { useCallback, useEffect, useState } from 'react';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import { PortalRequests, type PortalRequestItem } from '@/components/domain/PortalRequests';
import { Message } from '@/components/ui/Form';
import { ErrorState, LoadingState } from '@/components/ui/States';

/** Part E.5 client portal: what the firm is waiting for, and the answers. One page, no dashboard. */
export function PortalPage() {
  const raw = useRawFetch();
  const [items, setItems] = useState<PortalRequestItem[] | null | 'error'>(null);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await raw('/portal/requests');
      setItems(r.ok ? ((await r.json()) as PortalRequestItem[]) : 'error');
    } catch {
      setItems('error');
    }
  }, [raw]);

  useEffect(() => {
    void load();
  }, [load]);

  async function answer(requestId: string, response: string) {
    const r = await raw(`/portal/requests/${requestId}:answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response }),
    }).catch(() => null);
    if (!r) return setMsg({ kind: 'error', text: NETWORK_ERROR });
    if (!r.ok) return setMsg({ kind: 'error', text: problemMessage(await r.json().catch(() => ({})), "La réponse n'a pas été envoyée.") });
    setMsg({ kind: 'ok', text: 'Réponse envoyée au cabinet.' });
    void load();
  }

  return (
    <>
      <h1 className="text-[1.75rem]">Demandes du cabinet</h1>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      <div className="mt-6" data-testid="portal-page">
        {items === null && <LoadingState label="Chargement des demandes…" />}
        {items === 'error' && <ErrorState title="Les demandes n'ont pas pu être chargées." detail={NETWORK_ERROR} />}
        {Array.isArray(items) && (
          <PortalRequests requests={items} onAnswerRequest={(rid, text) => answer(rid, text)} />
        )}
      </div>
    </>
  );
}
