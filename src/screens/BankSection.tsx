import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import { Button } from '@/components/ui/Button';
import { Field, Input, Message } from '@/components/ui/Form';

interface BankAccount {
  id: string;
  rib_last4: string;
  currency: string;
  journal_code: string;
}
interface Statement {
  id: string;
  period_start: string;
  period_end: string;
  opening_balance: number;
  closing_balance: number;
  balance_check: 'ok' | 'break' | 'unknown';
  filename?: string | null;
}

/** Part K 21 mask: the API returns only the last four digits. */
const masked = (last4: string) => `${'*'.repeat(20)}${last4}`;
const amount = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const BALANCE_FR: Record<Statement['balance_check'], string> = {
  ok: 'Soldes concordants',
  break: 'Soldes non concordants',
  unknown: 'Soldes non vérifiables',
};

/** Bank accounts (RIB) and statements of a monthly file (Phase 4). RIBs are shown masked only. */
export function BankSection({
  workRequestId,
  clientId,
  canWrite,
  onChanged,
}: {
  workRequestId: string;
  clientId: string;
  canWrite: boolean;
  /** Lets the file screen reload its issues (a balance break raises a blocking issue). */
  onChanged?: () => void;
}) {
  const raw = useRawFetch();
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [lineCount, setLineCount] = useState(0);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [rib, setRib] = useState('');
  const [accountId, setAccountId] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [a, t] = await Promise.all([
        raw(`/bank-accounts?client_entity_id=${clientId}`),
        raw(`/reconciliation/bank-transactions?work_request_id=${workRequestId}`),
      ]);
      const acc = a.ok ? ((await a.json()) as BankAccount[]) : [];
      setAccounts(acc);
      setAccountId((cur) => cur || acc[0]?.id || '');
      if (t.ok) {
        const body = (await t.json()) as { statements: Statement[]; items: unknown[] };
        setStatements(body.statements);
        setLineCount(body.items.length);
      }
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    }
  }, [raw, clientId, workRequestId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addAccount(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const r = await raw('/bank-accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_entity_id: clientId, rib: rib.replace(/\s/g, '') }),
    }).catch(() => null);
    if (!r) return setMsg({ kind: 'error', text: NETWORK_ERROR });
    const body = (await r.json().catch(() => ({}))) as { id?: string; rib_masked?: string };
    if (!r.ok) return setMsg({ kind: 'error', text: problemMessage(body, "Le compte bancaire n'a pas été enregistré.") });
    setRib('');
    setAccountId(body.id ?? '');
    setMsg({ kind: 'ok', text: `Compte ${body.rib_masked ?? ''} enregistré.` });
    void load();
  }

  async function uploadStatement(file: File) {
    setMsg(null);
    const form = new FormData();
    form.append('client_entity_id', clientId);
    form.append('bank_account_id', accountId);
    form.append('work_request_id', workRequestId);
    form.append('file', file);
    const r = await raw('/bank-statements/upload', { method: 'POST', body: form }).catch(() => null);
    if (!r) return setMsg({ kind: 'error', text: NETWORK_ERROR });
    const body = (await r.json().catch(() => ({}))) as { detail?: string; resubmitted?: boolean; balance_check?: string };
    if (!r.ok) setMsg({ kind: 'error', text: problemMessage(body, "Le relevé n'a pas été importé.") });
    else if (body.resubmitted) setMsg({ kind: 'ok', text: body.detail ?? 'Relevé déjà reçu.' });
    else if (body.balance_check === 'break')
      setMsg({ kind: 'error', text: `${file.name} importé, mais les soldes ne concordent pas : vérifiez le relevé (anomalie bloquante).` });
    else setMsg({ kind: 'ok', text: `${file.name} importé.` });
    void load();
    onChanged?.();
  }

  return (
    <section className="mt-8" aria-labelledby="bank-title">
      <div className="flex items-baseline justify-between">
        <h2 id="bank-title" className="text-xl">Banque</h2>
        <Link to={`/files/${workRequestId}/reconciliation`} className="text-sm text-sky-ink hover:underline" data-testid="link-reconciliation">
          Rapprochement bancaire
        </Link>
      </div>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}

      {canWrite && (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <form onSubmit={(e) => void addAccount(e)} className="flex items-end gap-2" data-testid="form-bank-account">
            <div className="w-80">
              <Field label="RIB (24 chiffres)">
                <Input name="rib" inputMode="numeric" value={rib} onChange={(e) => setRib(e.target.value)} />
              </Field>
            </div>
            <Button type="submit" variant="secondary">Ajouter le compte</Button>
          </form>
          {accounts.length > 0 && (
            <div className="flex items-end gap-2">
              <Field label="Compte du relevé">
                <select
                  className="h-9 rounded-input border border-line bg-paper px-2 text-sm"
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                  data-testid="select-bank-account"
                >
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {masked(a.rib_last4)} · {a.currency}
                    </option>
                  ))}
                </select>
              </Field>
              <Button onClick={() => fileInput.current?.click()} disabled={!accountId}>
                Importer un relevé (.csv, .xlsx, .pdf)
              </Button>
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.xlsx,.pdf"
                className="sr-only"
                data-testid="input-statement"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void uploadStatement(f);
                  e.target.value = '';
                }}
              />
            </div>
          )}
        </div>
      )}

      {statements.length > 0 && (
        <table className="mt-4 w-full border-collapse text-sm" data-testid="statements-table">
          <thead className="bg-surface text-left text-ink-2">
            <tr className="h-9 border-b border-line">
              <th scope="col" className="px-3 font-medium">Relevé</th>
              <th scope="col" className="px-3 font-medium">Période</th>
              <th scope="col" className="px-3 text-right font-medium">Solde initial (MAD)</th>
              <th scope="col" className="px-3 text-right font-medium">Solde final (MAD)</th>
              <th scope="col" className="px-3 font-medium">Contrôle</th>
            </tr>
          </thead>
          <tbody>
            {statements.map((s) => (
              <tr
                key={s.id}
                data-testid="statement-row"
                data-balance={s.balance_check}
                className={`h-9 border-b border-l-[3px] border-b-line ${s.balance_check === 'ok' ? 'border-l-transparent' : 'border-l-pink'}`}
              >
                <td className="px-3">{s.filename ?? '—'}</td>
                <td className="px-3 tabular-nums">{s.period_start} → {s.period_end}</td>
                <td className="px-3 text-right tabular-nums">{amount(s.opening_balance)}</td>
                <td className="px-3 text-right tabular-nums">{amount(s.closing_balance)}</td>
                <td className={`px-3 ${s.balance_check === 'ok' ? 'text-ok' : 'text-pink-ink'}`}>{BALANCE_FR[s.balance_check]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {statements.length > 0 && <p className="mt-2 text-[0.8125rem] text-ink-2">{lineCount} ligne(s) de relevé</p>}
    </section>
  );
}
