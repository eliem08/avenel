import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '@/api/useApi';
import { idem, type ClientEntity } from '@/api/client';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field, Input, Message } from '@/components/ui/Form';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

type State = { kind: 'loading' } | { kind: 'error' } | { kind: 'ready'; rows: ClientEntity[] };

export function ClientsScreen() {
  const api = useApi();
  const { me } = useSession();
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const { data, error } = await api.GET('/client-entities');
      if (!data || error) throw new Error('api');
      setState({ kind: 'ready', rows: data.items });
    } catch {
      setState({ kind: 'error' });
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="flex items-baseline justify-between">
        <h1 className="text-[1.75rem]">Clients</h1>
        {can(me, 'write') && (
          <Button onClick={() => setCreating(true)} data-testid="btn-new-client">
            Nouvelle société
          </Button>
        )}
      </div>
      <div className="mt-6">
        {state.kind === 'loading' && <LoadingState label="Chargement des sociétés…" />}
        {state.kind === 'error' && (
          <ErrorState
            title="Les sociétés n'ont pas pu être chargées."
            detail={NETWORK_ERROR}
            action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>}
          />
        )}
        {state.kind === 'ready' && state.rows.length === 0 && (
          <EmptyState title="Aucune société cliente. Ajoutez une société pour commencer." />
        )}
        {state.kind === 'ready' && state.rows.length > 0 && (
          <table className="w-full border-collapse text-sm" data-testid="clients-table">
            <thead className="bg-surface text-left text-ink-2">
              <tr className="h-9 border-b border-line">
                <th scope="col" className="px-3 font-medium">Société</th>
                <th scope="col" className="px-3 font-medium">ICE</th>
                <th scope="col" className="px-3 font-medium">IF</th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((c) => (
                <tr key={c.id} className="h-9 border-b border-line" data-testid="client-row">
                  <td className="px-3">
                    <Link to={`/clients/${c.id}`} className="text-sky-ink hover:underline">
                      {c.legal_name}
                    </Link>
                  </td>
                  <td className="px-3 tabular-nums">{c.ice ?? '—'}</td>
                  <td className="px-3 tabular-nums">{c.if_number ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <CreateClientDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
          setCreating(false);
          void load();
        }}
      />
    </>
  );
}

function CreateClientDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const api = useApi();
  const [legalName, setLegalName] = useState('');
  const [ice, setIce] = useState('');
  const [ifNumber, setIfNumber] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { error: apiError } = await api.POST('/client-entities', {
        params: { header: idem() },
        body: { legal_name: legalName.trim(), ice: ice.trim() || null, if_number: ifNumber.trim() || null },
      });
      if (apiError) {
        setError(problemMessage(apiError, "La société n'a pas été créée."));
        return;
      }
      setLegalName('');
      setIce('');
      setIfNumber('');
      onCreated();
    } catch {
      setError(NETWORK_ERROR);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="Nouvelle société" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-3" data-testid="form-new-client">
        <Field label="Raison sociale">
          <Input name="legal_name" required value={legalName} onChange={(e) => setLegalName(e.target.value)} />
        </Field>
        <Field label="ICE" hint="15 chiffres, facultatif.">
          <Input name="ice" inputMode="numeric" value={ice} onChange={(e) => setIce(e.target.value)} />
        </Field>
        <Field label="Identifiant fiscal (IF)" hint="Facultatif.">
          <Input name="if_number" inputMode="numeric" value={ifNumber} onChange={(e) => setIfNumber(e.target.value)} />
        </Field>
        {error && <Message kind="error">{error}</Message>}
        <div className="flex gap-2 pt-2">
          <Button type="submit" disabled={busy}>
            Créer la société
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
