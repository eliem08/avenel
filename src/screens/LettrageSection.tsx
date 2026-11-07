import { useCallback, useEffect, useRef, useState } from 'react';
import { useApi } from '@/api/useApi';
import { idem } from '@/api/client';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import type { components } from '@/api/schema';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, Input, Message } from '@/components/ui/Form';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

type OpenItems = components['schemas']['OpenItemsResponse'];
type Group = components['schemas']['LettrageGroup'];
type AccountClass = 'customer' | 'supplier';

const KIND_FR: Record<string, string> = {
  exact: 'Montant identique',
  grouped: 'Un règlement, plusieurs factures',
  split: 'Une facture, plusieurs règlements',
  partial: 'Règlement partiel',
  manual: 'Lettrage manuel',
};
const STATUS_FR: Record<string, string> = { open: 'Ouvert', partial: 'Partiel', settled: 'Soldé' };

const mad = (v: string) => Number(v).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const date = (v: string) => new Date(`${v}T00:00:00`).toLocaleDateString('fr-FR');

/**
 * Lettrage of customer (342x) and supplier (441x) accounts (ARCHITECTURE.md D.7b).
 * Only approved entries appear. Candidates are computed by rules with exact amounts;
 * the accountant accepts, rejects or reverses each one. Nothing is deleted.
 */
export function LettrageSection({ clientId, canWrite }: { clientId: string; canWrite: boolean }) {
  const api = useApi();
  const [cls, setCls] = useState<AccountClass>('customer');
  const [items, setItems] = useState<OpenItems | null | 'error'>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [accepted, setAccepted] = useState<Group[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [reversing, setReversing] = useState<Group | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const prefix = cls === 'customer' ? '342' : '441';

  const seq = useRef(0);
  const load = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const [o, p, a] = await Promise.all([
        api.GET('/clients/{client_id}/open-items', { params: { path: { client_id: clientId }, query: { account_class: cls } } }),
        api.GET('/clients/{client_id}/lettrage-groups', { params: { path: { client_id: clientId }, query: { status: 'proposed' } } }),
        api.GET('/clients/{client_id}/lettrage-groups', { params: { path: { client_id: clientId }, query: { status: 'accepted' } } }),
      ]);
      if (mine !== seq.current) return;
      if (!o.data) return setItems('error');
      setItems(o.data);
      setGroups((p.data ?? []).filter((g) => g.account_code.startsWith(prefix)));
      setAccepted((a.data ?? []).filter((g) => g.account_code.startsWith(prefix)));
      setSelected(new Set());
    } catch {
      if (mine === seq.current) setItems('error');
    }
  }, [api, clientId, cls, prefix]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  async function run(action: () => Promise<{ error?: unknown; data?: unknown }>, ok: string, fail: string) {
    setMsg(null);
    setBusy(true);
    try {
      const { error, data } = await action();
      if (error || !data) setMsg({ kind: 'error', text: problemMessage(error, fail) });
      else setMsg({ kind: 'ok', text: ok });
      await load();
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    } finally {
      setBusy(false);
    }
  }

  const generate = () =>
    run(
      () => api.POST('/clients/{client_id}/lettrage-groups:generate', { params: { path: { client_id: clientId }, header: idem() } }),
      'Propositions de lettrage recalculées.',
      "Les propositions n'ont pas pu être calculées.",
    );
  const accept = (g: Group) =>
    run(
      () => api.POST('/lettrage-groups/{group_id}:accept', { params: { path: { group_id: g.id }, header: idem() } }),
      `Lettrage accepté pour ${g.counterparty_name}.`,
      "Le lettrage n'a pas été accepté.",
    );
  const reject = (g: Group) =>
    run(
      () => api.POST('/lettrage-groups/{group_id}:reject', { params: { path: { group_id: g.id }, header: idem() } }),
      'Proposition rejetée.',
      "La proposition n'a pas été rejetée.",
    );
  const manual = () => {
    if (!items || items === 'error') return Promise.resolve();
    const allocations = items.items
      .filter((i) => selected.has(i.journal_line_id))
      .map((i) => ({ journal_line_id: i.journal_line_id, amount_mad: i.open_mad }));
    return run(
      () => api.POST('/clients/{client_id}/lettrage-groups', { params: { path: { client_id: clientId }, header: idem() }, body: { allocations } }),
      'Lettrage manuel proposé : acceptez-le ci-dessous.',
      "Le lettrage manuel n'a pas été créé.",
    );
  };
  async function reverse() {
    if (!reversing) return;
    const g = reversing;
    await run(
      () => api.POST('/lettrage-groups/{group_id}:reverse', { params: { path: { group_id: g.id }, header: idem() }, body: { reason } }),
      `Lettrage ${g.letter_code} annulé. Les lignes sont de nouveau ouvertes.`,
      "Le délettrage n'a pas été enregistré.",
    );
    setReversing(null);
    setReason('');
  }

  const selectedItems = items && items !== 'error' ? items.items.filter((i) => selected.has(i.journal_line_id)) : [];
  const selDebit = selectedItems.filter((i) => i.side === 'debit').reduce((s, i) => s + Number(i.open_mad), 0);
  const selCredit = selectedItems.filter((i) => i.side === 'credit').reduce((s, i) => s + Number(i.open_mad), 0);
  const selBalanced = selectedItems.length >= 2 && Math.abs(selDebit - selCredit) < 0.005;

  return (
    <section className="mt-8" aria-labelledby="lettrage-title" data-testid="lettrage-section">
      <div className="flex items-baseline justify-between">
        <h2 id="lettrage-title" className="text-xl">Lettrage</h2>
        {canWrite && (
          <Button onClick={() => void generate()} disabled={busy} data-testid="btn-lettrage-generate">
            Proposer le lettrage
          </Button>
        )}
      </div>
      <p className="mt-1 max-w-[75ch] text-sm text-ink-2">
        Seules les écritures approuvées apparaissent. Les propositions rapprochent des montants exacts ; aucune tolérance
        n'est appliquée tant qu'un professionnel inscrit ne l'a pas fixée.
      </p>
      <div role="tablist" aria-label="Comptes" className="mt-3 flex gap-1">
        {(['customer', 'supplier'] as const).map((c) => (
          <button
            key={c}
            role="tab"
            type="button"
            aria-selected={cls === c}
            onClick={() => setCls(c)}
            data-testid={`tab-${c}`}
            className={`h-8 rounded-input px-3 text-sm ${cls === c ? 'bg-sky-wash text-ink font-medium' : 'text-ink-2 hover:bg-surface'}`}
          >
            {c === 'customer' ? 'Clients (342)' : 'Fournisseurs (441)'}
          </button>
        ))}
      </div>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      {items === null && <LoadingState label="Chargement des comptes de tiers…" />}
      {items === 'error' && <ErrorState title="Les comptes de tiers n'ont pas pu être chargés." detail={NETWORK_ERROR} />}

      {items && items !== 'error' && (
        <>
          {items.balances.length > 0 && (
            <table className="mt-3 w-full border-collapse text-sm" data-testid="lettrage-balances">
              <thead className="bg-surface text-left text-ink-2">
                <tr className="h-9 border-b border-line">
                  <th scope="col" className="px-3 font-medium">Tiers</th>
                  <th scope="col" className="px-3 font-medium">Compte</th>
                  <th scope="col" className="px-3 text-right font-medium">Pièces ouvertes</th>
                  <th scope="col" className="px-3 text-right font-medium">Solde (MAD)</th>
                </tr>
              </thead>
              <tbody>
                {items.balances.map((b) => (
                  <tr key={`${b.counterparty_id}-${b.account_code}`} className="h-10 border-b border-line" data-testid="balance-row">
                    <td className="px-3">{b.counterparty_name}</td>
                    <td className="px-3 tabular-nums">{b.account_code}</td>
                    <td className="px-3 text-right tabular-nums">{b.open_count}</td>
                    <td className="px-3 text-right tabular-nums" data-testid="balance-amount">{mad(b.balance_mad)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="mt-6 text-base font-medium">Propositions à valider</h3>
          {groups.length === 0 ? (
            <p className="mt-1 text-sm text-ink-2" data-testid="no-proposals">Aucune proposition en attente.</p>
          ) : (
            <ul className="mt-2 space-y-3">
              {groups.map((g) => (
                <li key={g.id} className="rounded-panel border border-line border-l-[3px] border-l-pink p-3" data-testid="lettrage-proposal">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm">
                      <span className="font-medium">{g.counterparty_name}</span> · {g.account_code} · {KIND_FR[g.kind] ?? g.kind}
                    </p>
                    <p className="tabular-nums text-sm font-medium">{mad(g.total_mad)} MAD</p>
                  </div>
                  <ul className="mt-2 text-sm text-ink-2">
                    {g.allocations.map((a) => (
                      <li key={a.journal_line_id} className="flex justify-between gap-3 tabular-nums">
                        <span>{date(a.entry_date)} · {a.label}</span>
                        <span>
                          {a.side === 'debit' ? 'D' : 'C'} {mad(a.amount_mad)}
                          {a.amount_mad !== a.line_amount_mad && ` sur ${mad(a.line_amount_mad)}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-xs text-ink-2">{g.reasons.join(' · ')}</p>
                  {canWrite && (
                    <div className="mt-2 flex gap-2">
                      <Button onClick={() => void accept(g)} disabled={busy} data-testid="btn-lettrage-accept">Accepter</Button>
                      <Button variant="secondary" onClick={() => void reject(g)} disabled={busy} data-testid="btn-lettrage-reject">Rejeter</Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 flex items-baseline justify-between">
            <h3 className="text-base font-medium">Pièces non lettrées</h3>
            {canWrite && selectedItems.length > 0 && (
              <div className="flex items-baseline gap-3 text-sm">
                <span className="tabular-nums" data-testid="selection-totals">
                  Débit {mad(String(selDebit))} · Crédit {mad(String(selCredit))}
                </span>
                <Button variant="secondary" onClick={() => void manual()} disabled={busy || !selBalanced} data-testid="btn-lettrage-manual">
                  Lettrer la sélection
                </Button>
              </div>
            )}
          </div>
          {items.items.length === 0 ? (
            <EmptyState title="Toutes les pièces approuvées sont lettrées." />
          ) : (
            <table className="mt-2 w-full border-collapse text-sm" data-testid="open-items-table">
              <thead className="bg-surface text-left text-ink-2">
                <tr className="h-9 border-b border-line">
                  {canWrite && <th scope="col" className="w-8 px-2"><span className="sr-only">Sélection</span></th>}
                  <th scope="col" className="px-3 font-medium">Date</th>
                  <th scope="col" className="px-3 font-medium">Tiers</th>
                  <th scope="col" className="px-3 font-medium">Libellé</th>
                  <th scope="col" className="px-3 font-medium">Échéance</th>
                  <th scope="col" className="px-3 text-right font-medium">Débit</th>
                  <th scope="col" className="px-3 text-right font-medium">Crédit</th>
                  <th scope="col" className="px-3 text-right font-medium">Reste</th>
                  <th scope="col" className="px-3 font-medium">État</th>
                </tr>
              </thead>
              <tbody>
                {items.items.map((i) => (
                  <tr key={i.journal_line_id} className="h-10 border-b border-line" data-testid="open-item-row" data-status={i.status}>
                    {canWrite && (
                      <td className="px-2">
                        <input
                          type="checkbox"
                          aria-label={`Sélectionner ${i.label}`}
                          checked={selected.has(i.journal_line_id)}
                          onChange={(e) => {
                            const next = new Set(selected);
                            if (e.target.checked) next.add(i.journal_line_id);
                            else next.delete(i.journal_line_id);
                            setSelected(next);
                          }}
                        />
                      </td>
                    )}
                    <td className="px-3 tabular-nums">{date(i.entry_date)}</td>
                    <td className="px-3">{i.counterparty_name}</td>
                    <td className="px-3">{i.label}</td>
                    <td className="px-3 tabular-nums">
                      {i.due_date ? date(i.due_date) : '—'}
                      {i.days_overdue > 0 && <span className="ml-1 text-pink-ink">({i.days_overdue} j de retard)</span>}
                    </td>
                    <td className="px-3 text-right tabular-nums">{i.side === 'debit' ? mad(i.amount_mad) : ''}</td>
                    <td className="px-3 text-right tabular-nums">{i.side === 'credit' ? mad(i.amount_mad) : ''}</td>
                    <td className="px-3 text-right tabular-nums" data-testid="open-amount">{mad(i.open_mad)}</td>
                    <td className="px-3">
                      {STATUS_FR[i.status] ?? i.status}
                      {i.letters.length > 0 && <span className="ml-1 text-ink-2">({i.letters.join(', ')})</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {accepted.length > 0 && (
            <>
              <h3 className="mt-6 text-base font-medium">Lettrages acceptés</h3>
              <ul className="mt-2 divide-y divide-line text-sm">
                {accepted.map((g) => (
                  <li key={g.id} className="flex items-center justify-between gap-3 py-2" data-testid="lettrage-accepted">
                    <span>
                      <span className="font-medium tabular-nums" data-testid="letter-code">{g.letter_code}</span> · {g.counterparty_name} ·{' '}
                      {g.account_code} · {KIND_FR[g.kind] ?? g.kind}
                    </span>
                    <span className="flex items-center gap-3">
                      <span className="tabular-nums">{mad(g.total_mad)} MAD</span>
                      {canWrite && (
                        <Button variant="quiet" onClick={() => setReversing(g)} data-testid="btn-lettrage-reverse">Délettrer</Button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}

      <Dialog open={reversing !== null} title={`Délettrer ${reversing?.letter_code ?? ''}`} onClose={() => setReversing(null)}>
        <p className="text-sm">Les lignes redeviennent ouvertes. Le lettrage annulé reste dans l'historique avec son motif.</p>
        <Field label="Motif">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="input-reverse-reason" />
        </Field>
        <div className="mt-4 flex gap-2">
          <Button variant="danger" onClick={() => void reverse()} disabled={busy || reason.trim().length < 3} data-testid="btn-reverse-confirm">
            Délettrer
          </Button>
          <Button variant="secondary" onClick={() => setReversing(null)}>Annuler</Button>
        </div>
      </Dialog>
    </section>
  );
}
