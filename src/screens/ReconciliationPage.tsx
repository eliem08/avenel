import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import {
  ReconciliationScreen,
  type BankTransactionLine,
  type ProposalSummary,
  type ReconciliationMatch,
} from '@/components/domain/ReconciliationScreen';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { Message } from '@/components/ui/Form';
import { ErrorState, LoadingState } from '@/components/ui/States';

interface ApiProposal {
  id: string;
  journal_code: string;
  entry_date: string;
  label: string;
  status: string;
  lines: { account_code: string; debit_mad: number; credit_mad: number; tax_code?: string | null }[];
}

/** Summary used by the reconciliation screen: the entry total (sum of its debits, equal to its
 * credits since every proposal balances). No VAT figure is derived here: picking VAT lines by
 * account would be an accounting rule in the browser. */
function toSummary(p: ApiProposal): ProposalSummary {
  const total = Math.round(p.lines.reduce((s, l) => s + Number(l.debit_mad || 0), 0) * 100) / 100;
  return { id: p.id, journal_code: p.journal_code, entry_date: p.entry_date, label: p.label, amount_ttc: total };
}

export function ReconciliationPage() {
  const { id = '' } = useParams();
  const raw = useRawFetch();
  const { me } = useSession();
  const [data, setData] = useState<
    | null
    | 'error'
    | { clientId: string; tx: BankTransactionLine[]; proposals: ProposalSummary[]; matches: ReconciliationMatch[] }
  >(null);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [wr, tx, props, matches] = await Promise.all([
        raw(`/work-requests/${id}`),
        raw(`/reconciliation/bank-transactions?work_request_id=${id}`),
        raw(`/work-requests/${id}/proposals`),
        raw(`/reconciliation/matches?work_request_id=${id}`),
      ]);
      if (!wr.ok || !tx.ok || !props.ok || !matches.ok) return setData('error');
      const wrBody = (await wr.json()) as { client_entity_id: string };
      const txBody = (await tx.json()) as { items: BankTransactionLine[] };
      const pBody = (await props.json()) as ApiProposal[];
      setData({
        clientId: wrBody.client_entity_id,
        tx: txBody.items,
        proposals: pBody.filter((p) => p.journal_code !== 'BQ' && p.status !== 'superseded').map(toSummary),
        matches: (await matches.json()) as ReconciliationMatch[],
      });
    } catch {
      setData('error');
    }
  }, [raw, id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate(clientId: string) {
    setMsg(null);
    const r = await raw('/reconciliation/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_entity_id: clientId, work_request_id: id }),
    }).catch(() => null);
    if (!r) return setMsg({ kind: 'error', text: NETWORK_ERROR });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) return setMsg({ kind: 'error', text: problemMessage(body, "Les rapprochements n'ont pas été recherchés.") });
    const n = Array.isArray(body) ? body.length : 0;
    setMsg({ kind: 'ok', text: n ? `${n} rapprochement(s) proposé(s).` : 'Aucun rapprochement trouvé pour les lignes du relevé.' });
    void load();
  }

  async function decide(matchId: string, action: 'accept' | 'reject') {
    const r = await raw(`/reconciliation/matches/${matchId}/${action}`, { method: 'POST' }).catch(() => null);
    if (!r || !r.ok) {
      const body = r ? await r.json().catch(() => ({})) : {};
      setMsg({ kind: 'error', text: r ? problemMessage(body, "La décision n'a pas été enregistrée.") : NETWORK_ERROR });
    } else setMsg({ kind: 'ok', text: action === 'accept' ? 'Rapprochement accepté.' : 'Rapprochement rejeté.' });
    await load();
  }

  if (data === null) return <LoadingState label="Chargement du rapprochement…" />;
  if (data === 'error')
    return <ErrorState title="Le rapprochement n'a pas pu être chargé." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;

  const writable = can(me, 'write');
  return (
    <>
      <p className="text-sm">
        <Link to={`/files/${id}`} className="text-sky-ink hover:underline">Dossier mensuel</Link>
      </p>
      <div className="mt-1 flex items-baseline justify-between">
        <h1 className="text-[1.75rem]">Rapprochement bancaire</h1>
        {writable && (
          <Button onClick={() => void generate(data.clientId)} data-testid="btn-generate-matches">
            Rechercher les rapprochements
          </Button>
        )}
      </div>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      <div className="mt-4">
        <ReconciliationScreen
          bankTransactions={data.tx}
          proposals={data.proposals}
          matches={data.matches}
          onAcceptMatch={(m) => decide(m, 'accept')}
          onRejectMatch={(m) => decide(m, 'reject')}
          readOnly={!writable}
        />
      </div>
    </>
  );
}
