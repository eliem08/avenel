import { useCallback, useEffect, useState } from 'react';
import { useApi } from '@/api/useApi';
import { idem, type ChartAccount } from '@/api/client';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { Message } from '@/components/ui/Form';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

interface Slot {
  tax_code: string;
  direction: string;
  rate: number | null;
  label_fr?: string;
  source?: string | null;
  account_id: string | null;
  account_code: string | null;
  approved: boolean;
  approved_by_name: string | null;
}

const DIRECTION_FR: Record<string, string> = {
  purchase: 'Achats (TVA récupérable)',
  fixed_asset: 'Immobilisations (TVA récupérable)',
  sale: 'Ventes (TVA facturée)',
  withholding: 'Retenue à la source',
};

/**
 * Which account receives each VAT code (Part K 15). Entries are only built from approved
 * mappings; only members with a professional registration approve (decision 6 Nov 2026).
 * No account is suggested or preselected here: the firm chooses.
 */
export function TaxMappingsSection({ clientId, canWrite }: { clientId: string; canWrite: boolean }) {
  const api = useApi();
  const [slots, setSlots] = useState<Slot[] | null | 'error'>(null);
  const [canApprove, setCanApprove] = useState(false);
  const [accounts, setAccounts] = useState<ChartAccount[]>([]);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([
        api.GET('/client-entities/{id}/tax-mappings', { params: { path: { id: clientId } } }),
        api.GET('/client-entities/{id}/chart-accounts', { params: { path: { id: clientId } } }),
      ]);
      if (!m.data) return setSlots('error');
      setSlots(m.data.items as Slot[]);
      setCanApprove(m.data.can_approve);
      setAccounts(a.data?.items ?? []);
    } catch {
      setSlots('error');
    }
  }, [api, clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function choose(slot: Slot, accountId: string) {
    setMsg(null);
    try {
      const { data, error } = await api.PUT('/client-entities/{id}/tax-mappings', {
        params: { path: { id: clientId }, header: idem() },
        body: { tax_code: slot.tax_code, direction: slot.direction, account_id: accountId },
      });
      if (error || !data) return setMsg({ kind: 'error', text: problemMessage(error, "Le compte n'a pas été enregistré.") });
      setMsg({
        kind: 'ok',
        text: data.approved
          ? `Compte ${data.account_code} approuvé pour ${slot.tax_code} (${DIRECTION_FR[slot.direction] ?? slot.direction}).`
          : `Compte ${data.account_code} enregistré. Il doit être approuvé par un membre inscrit à l'Ordre avant d'être utilisé.`,
      });
      void load();
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    }
  }

  return (
    <section className="mt-8" aria-labelledby="tax-title">
      <h2 id="tax-title" className="text-xl">Comptes de TVA</h2>
      <p className="mt-1 max-w-[75ch] text-sm text-ink-2">
        Les écritures ne sont proposées que lorsque le compte de chaque taux est approuvé.
        {canApprove ? ' Votre choix vaut approbation.' : " Seuls les membres inscrits à l'Ordre peuvent approuver ; vos choix restent à approuver."}
      </p>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      {slots === null && <LoadingState label="Chargement des comptes de TVA…" />}
      {slots === 'error' && <ErrorState title="Les comptes de TVA n'ont pas pu être chargés." detail={NETWORK_ERROR} />}
      {Array.isArray(slots) && accounts.length === 0 && (
        <EmptyState title="Chargez d'abord le plan comptable de la société pour choisir les comptes." />
      )}
      {Array.isArray(slots) && accounts.length > 0 && (
        <table className="mt-3 w-full border-collapse text-sm" data-testid="tax-mappings-table">
          <thead className="bg-surface text-left text-ink-2">
            <tr className="h-9 border-b border-line">
              <th scope="col" className="px-3 font-medium">Code</th>
              <th scope="col" className="px-3 font-medium">Opérations</th>
              <th scope="col" className="px-3 text-right font-medium">Taux</th>
              <th scope="col" className="px-3 font-medium">Compte</th>
              <th scope="col" className="px-3 font-medium">État</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((s) => {
              const pending = !s.approved;
              return (
                <tr
                  key={`${s.tax_code}-${s.direction}`}
                  data-testid="tax-mapping-row"
                  data-slot={`${s.tax_code}/${s.direction}`}
                  className={`h-10 border-b border-l-[3px] border-b-line ${pending ? 'border-l-pink' : 'border-l-transparent'}`}
                >
                  <td className="px-3 tabular-nums">{s.tax_code}</td>
                  <td className="px-3">{DIRECTION_FR[s.direction] ?? s.direction}</td>
                  <td className="px-3 text-right tabular-nums">
                    {s.rate != null ? `${(s.rate * 100).toLocaleString('fr-FR')} %` : '—'}
                  </td>
                  <td className="px-3">
                    <select
                      aria-label={`Compte pour ${s.tax_code} ${DIRECTION_FR[s.direction] ?? s.direction}`}
                      className="h-8 w-full rounded-input border border-line bg-paper px-2 text-sm"
                      value={s.account_id ?? ''}
                      disabled={!canWrite}
                      onChange={(e) => e.target.value && void choose(s, e.target.value)}
                    >
                      <option value="">— Choisir un compte —</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.account_code} · {a.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className={`px-3 ${pending ? 'text-pink-ink' : 'text-ok'}`} data-testid="tax-mapping-state">
                    {s.approved ? `Approuvé${s.approved_by_name ? ` par ${s.approved_by_name}` : ''}` : s.account_id ? 'À approuver' : 'À choisir'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
