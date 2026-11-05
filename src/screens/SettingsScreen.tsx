import { useCallback, useEffect, useState } from 'react';
import { useApi } from '@/api/useApi';
import { NETWORK_ERROR } from '@/api/problem';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

type Doc = Record<string, unknown>;
type Which = 'dpa' | 'cndp';

const TITLES: Record<Which, string> = {
  dpa: 'Accord de sous-traitance (DPA, loi 09-08)',
  cndp: 'Dossier de déclaration CNDP',
};

export function SettingsScreen() {
  const { me } = useSession();
  const [which, setWhich] = useState<Which>('dpa');
  return (
    <>
      <h1 className="text-[1.75rem]">Paramètres</h1>
      <h2 className="mt-6 text-xl">Conformité</h2>
      {!can(me, 'compliance') ? (
        <EmptyState title="Ces documents sont réservés au cabinet." />
      ) : (
        <>
          <div className="mt-3 flex gap-2" role="tablist">
            {(['dpa', 'cndp'] as const).map((w) => (
              <Button key={w} role="tab" aria-selected={which === w} variant={which === w ? 'primary' : 'secondary'} onClick={() => setWhich(w)} data-testid={`tab-${w}`}>
                {TITLES[w]}
              </Button>
            ))}
          </div>
          <ComplianceDocument which={which} />
        </>
      )}
    </>
  );
}

function ComplianceDocument({ which }: { which: Which }) {
  const api = useApi();
  const [doc, setDoc] = useState<Doc | null | 'error'>(null);

  const load = useCallback(async () => {
    setDoc(null);
    try {
      const res = which === 'dpa' ? await api.GET('/compliance/dpa') : await api.GET('/compliance/cndp-dossier');
      setDoc(!res.data || res.error ? 'error' : (res.data as Doc));
    } catch {
      setDoc('error');
    }
  }, [api, which]);

  useEffect(() => {
    void load();
  }, [load]);

  if (doc === null) return <LoadingState label="Génération du document…" />;
  if (doc === 'error')
    return <ErrorState title="Le document n'a pas pu être généré." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;

  const { title, legal_notice: notice, needs_expert_dependencies: pending, ...rest } = doc;
  return (
    <article className="mt-4 max-w-[75ch] rounded-panel border border-line bg-paper p-6" data-testid={`doc-${which}`}>
      {typeof title === 'string' && <p className="text-sm font-medium text-pink-ink">{title}</p>}
      {typeof notice === 'string' && <p className="mt-1 text-sm text-ink-2">{notice}</p>}
      {Array.isArray(pending) && pending.length > 0 && (
        <div className="mt-3 border-l-[3px] border-l-pink bg-pink-wash px-3 py-2 text-sm" data-testid="needs-expert">
          <p className="font-medium text-pink-ink">À valider par un expert : {pending.length} point(s)</p>
          <ul className="mt-1 list-disc pl-5">
            {pending.map((p) => (
              <li key={String(p)} className="tabular-nums">{String(p)}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-4 text-sm">
        <Value value={rest} />
      </div>
    </article>
  );
}

/** Renders the document exactly as the API returned it: no field is added or reworded. */
function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return <span className="text-ink-2">—</span>;
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-5">
        {value.map((v, i) => (
          <li key={i}>
            <Value value={v} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === 'object') {
    return (
      <dl className="space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <dt className="text-[0.8125rem] text-ink-2">{k.replace(/_/g, ' ')}</dt>
            <dd className="mt-0.5">
              <Value value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return <span>{String(value)}</span>;
}
