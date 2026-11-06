import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '@/api/useApi';
import { useAuth } from '@/auth/AuthProvider';
import { config } from '@/config';
import { idem, type AccountingPeriod, type ChartAccount, type ClientEntity } from '@/api/client';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, Input, Message } from '@/components/ui/Form';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { TaxMappingsSection } from './TaxMappingsSection';
import { LettrageSection } from './LettrageSection';

const PERIOD_STATUS_FR: Record<string, string> = {
  open: 'Ouverte',
  in_review: 'En revue',
  approved: 'Validée',
  closed: 'Clôturée',
};

export function ClientScreen() {
  const { id = '' } = useParams();
  const api = useApi();
  const { me } = useSession();
  const navigate = useNavigate();
  const [client, setClient] = useState<ClientEntity | null | 'error' | 'missing'>(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  // Bumped when the chart changes so the VAT account choices reload.
  const [chartVersion, setChartVersion] = useState(0);

  const load = useCallback(async () => {
    setClient(null);
    try {
      const { data, error, response } = await api.GET('/client-entities/{id}', { params: { path: { id } } });
      if (response.status === 404) return setClient('missing');
      if (!data || error) return setClient('error');
      setClient(data);
    } catch {
      setClient('error');
    }
  }, [api, id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function archive() {
    setArchiveError(null);
    try {
      const { error } = await api.POST('/client-entities/{id}/archive', { params: { path: { id }, header: idem() } });
      if (error) return setArchiveError(problemMessage(error, "La société n'a pas été archivée."));
      navigate('/clients');
    } catch {
      setArchiveError(NETWORK_ERROR);
    }
  }

  if (client === null) return <LoadingState label="Chargement de la société…" />;
  if (client === 'missing')
    return <ErrorState title="Société introuvable." detail="Elle n'existe pas ou vous n'y avez pas accès. Revenez à la liste des clients." />;
  if (client === 'error')
    return (
      <ErrorState
        title="La société n'a pas pu être chargée."
        detail={NETWORK_ERROR}
        action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>}
      />
    );

  return (
    <>
      <p className="text-sm">
        <Link to="/clients" className="text-sky-ink hover:underline">Clients</Link>
      </p>
      <div className="mt-1 flex items-baseline justify-between">
        <h1 className="text-[1.75rem]" data-testid="client-name">{client.legal_name}</h1>
        {can(me, 'archive') && (
          <Button variant="danger" onClick={() => setArchiving(true)} data-testid="btn-archive">
            Archiver la société
          </Button>
        )}
      </div>
      <p className="mt-1 text-sm text-ink-2 tabular-nums">
        ICE {client.ice ?? '—'} · IF {client.if_number ?? '—'} · Devise {client.functional_currency}
      </p>

      <PeriodsSection clientId={id} canWrite={can(me, 'write')} />
      <ChartSection clientId={id} canWrite={can(me, 'write')} onChanged={() => setChartVersion((v) => v + 1)} />
      <TaxMappingsSection key={chartVersion} clientId={id} canWrite={can(me, 'write')} />
      {me?.role !== 'client_user' && <LettrageSection clientId={id} canWrite={can(me, 'write') && me?.role !== 'operator'} />}

      <Dialog open={archiving} title="Archiver la société" onClose={() => setArchiving(false)}>
        <p className="text-sm">
          La société ne pourra plus recevoir de pièces ni de nouvelles périodes. Ses données restent conservées.
        </p>
        {archiveError && <Message kind="error">{archiveError}</Message>}
        <div className="mt-4 flex gap-2">
          <Button variant="danger" onClick={() => void archive()} data-testid="btn-archive-confirm">
            Archiver la société
          </Button>
          <Button variant="secondary" onClick={() => setArchiving(false)}>
            Annuler
          </Button>
        </div>
      </Dialog>
    </>
  );
}

/** First and last day of a YYYY-MM month (calendar arithmetic only, no accounting rule). */
function monthBounds(code: string): { starts_on: string; ends_on: string } | null {
  const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(code);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const last = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  return { starts_on: `${m[1]}-${m[2]}-01`, ends_on: `${m[1]}-${m[2]}-${String(last).padStart(2, '0')}` };
}

function PeriodsSection({ clientId, canWrite }: { clientId: string; canWrite: boolean }) {
  const api = useApi();
  const [rows, setRows] = useState<AccountingPeriod[] | null | 'error'>(null);
  const [code, setCode] = useState('');
  const [fye, setFye] = useState('');
  const [msg, setMsg] = useState<{ kind: 'error' | 'ok'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const { data, error } = await api.GET('/client-entities/{id}/periods', { params: { path: { id: clientId } } });
      setRows(!data || error ? 'error' : data.items);
    } catch {
      setRows('error');
    }
  }, [api, clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function open(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const b = monthBounds(code.trim());
    if (!b) return setMsg({ kind: 'error', text: 'Saisissez la période au format AAAA-MM, par exemple 2026-09.' });
    if (!fye) return setMsg({ kind: 'error', text: "Saisissez la date de clôture de l'exercice de la société." });
    try {
      const { error } = await api.POST('/client-entities/{id}/periods', {
        params: { path: { id: clientId }, header: idem() },
        body: { period_code: code.trim(), ...b, fiscal_year_end: fye },
      });
      if (error) return setMsg({ kind: 'error', text: problemMessage(error, "La période n'a pas été ouverte.") });
      setMsg({ kind: 'ok', text: `Période ${code.trim()} ouverte.` });
      setCode('');
      void load();
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    }
  }

  return (
    <section className="mt-8" aria-labelledby="periods-title">
      <h2 id="periods-title" className="text-xl">Périodes</h2>
      {rows === null && <LoadingState label="Chargement des périodes…" />}
      {rows === 'error' && <ErrorState title="Les périodes n'ont pas pu être chargées." detail={NETWORK_ERROR} />}
      {Array.isArray(rows) && rows.length === 0 && <EmptyState title="Aucune période ouverte pour cette société." />}
      {Array.isArray(rows) && rows.length > 0 && (
        <table className="mt-3 w-full border-collapse text-sm" data-testid="periods-table">
          <thead className="bg-surface text-left text-ink-2">
            <tr className="h-9 border-b border-line">
              <th scope="col" className="px-3 font-medium">Période</th>
              <th scope="col" className="px-3 font-medium">Du</th>
              <th scope="col" className="px-3 font-medium">Au</th>
              <th scope="col" className="px-3 font-medium">Clôture de l'exercice</th>
              <th scope="col" className="px-3 font-medium">État</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className="h-9 border-b border-line" data-testid="period-row">
                <td className="px-3 tabular-nums">{p.period_code}</td>
                <td className="px-3 tabular-nums">{p.starts_on}</td>
                <td className="px-3 tabular-nums">{p.ends_on}</td>
                <td className="px-3 tabular-nums">{p.fiscal_year_end ?? '—'}</td>
                <td className="px-3">{PERIOD_STATUS_FR[p.status] ?? p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canWrite && (
        <form onSubmit={(e) => void open(e)} className="mt-4 flex flex-wrap items-end gap-3" data-testid="form-open-period">
          <div className="w-36">
            <Field label="Période (AAAA-MM)">
              <Input name="period_code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="2026-09" />
            </Field>
          </div>
          <div className="w-48">
            <Field label="Clôture de l'exercice">
              <Input name="fiscal_year_end" type="date" value={fye} onChange={(e) => setFye(e.target.value)} />
            </Field>
          </div>
          <Button type="submit" data-testid="btn-open-period">Ouvrir la période</Button>
        </form>
      )}
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
    </section>
  );
}

function ChartSection({ clientId, canWrite, onChanged }: { clientId: string; canWrite: boolean; onChanged: () => void }) {
  const api = useApi();
  const { user } = useAuth();
  const [rows, setRows] = useState<ChartAccount[] | null | 'error'>(null);
  const [msg, setMsg] = useState<{ kind: 'error' | 'ok'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data, error } = await api.GET('/client-entities/{id}/chart-accounts', { params: { path: { id: clientId } } });
      setRows(!data || error ? 'error' : data.items);
    } catch {
      setRows('error');
    }
  }, [api, clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function seed() {
    setBusy(true);
    setMsg(null);
    try {
      const { data, error } = await api.POST('/client-entities/{id}/chart-accounts/seed-cgnc', { params: { path: { id: clientId }, header: idem() } });
      if (error) setMsg({ kind: 'error', text: problemMessage(error, "Le plan CGNC n'a pas été chargé.") });
      else {
        setMsg({ kind: 'ok', text: (data as { message?: string })?.message ?? 'Plan CGNC chargé.' });
        void load();
        onChanged();
      }
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    } finally {
      setBusy(false);
    }
  }

  async function importFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      // Multipart upload: sent with fetch so the browser sets the boundary. Same token, fresh Idempotency-Key.
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${config.apiBaseUrl}/client-entities/${clientId}/chart-accounts/import-file`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${user?.access_token ?? ''}`, 'Idempotency-Key': crypto.randomUUID() },
        body: form,
      });
      const body = (await res.json().catch(() => ({}))) as { message?: string };
      if (!res.ok) setMsg({ kind: 'error', text: problemMessage(body, "Le fichier n'a pas été importé.") });
      else {
        setMsg({ kind: 'ok', text: body.message ?? 'Plan comptable importé.' });
        void load();
        onChanged();
      }
    } catch {
      setMsg({ kind: 'error', text: NETWORK_ERROR });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-8" aria-labelledby="chart-title">
      <div className="flex items-baseline justify-between">
        <h2 id="chart-title" className="text-xl">Plan comptable</h2>
        {canWrite && (
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void seed()} disabled={busy} data-testid="btn-seed-cgnc">
              Charger le plan CGNC
            </Button>
            <label className="inline-flex h-9 cursor-pointer items-center rounded-input border border-line bg-paper px-4 text-sm font-medium text-ink hover:bg-surface">
              Importer un fichier (.csv, .xlsx)
              <input
                type="file"
                accept=".csv,.xlsx"
                className="sr-only"
                data-testid="input-chart-file"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void importFile(f);
                  e.target.value = '';
                }}
              />
            </label>
          </div>
        )}
      </div>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      {rows === null && <LoadingState label="Chargement du plan comptable…" />}
      {rows === 'error' && <ErrorState title="Le plan comptable n'a pas pu être chargé." detail={NETWORK_ERROR} />}
      {Array.isArray(rows) && rows.length === 0 && <EmptyState title="Aucun compte. Chargez le plan CGNC ou importez le plan de la société." />}
      {Array.isArray(rows) && rows.length > 0 && (
        <>
          <p className="mt-3 text-[0.8125rem] text-ink-2" data-testid="chart-count">{rows.length} comptes</p>
          <div className="mt-2 max-h-96 overflow-auto rounded-panel border border-line">
            <table className="w-full border-collapse text-sm" data-testid="chart-table">
              <thead className="sticky top-0 bg-surface text-left text-ink-2">
                <tr className="h-9 border-b border-line">
                  <th scope="col" className="px-3 font-medium">Compte</th>
                  <th scope="col" className="px-3 font-medium">Libellé</th>
                  <th scope="col" className="px-3 font-medium">Classe</th>
                  <th scope="col" className="px-3 font-medium">Origine</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} className="h-9 border-b border-line">
                    <td className="px-3 tabular-nums">{a.account_code}</td>
                    <td className="px-3">{a.label}</td>
                    <td className="px-3 tabular-nums">{a.cgnc_class}</td>
                    <td className="px-3 text-ink-2">{a.source ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
