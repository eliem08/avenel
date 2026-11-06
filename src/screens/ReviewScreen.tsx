import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import { ProposalReview, type Proposal, type ProposalLine } from '@/components/domain/ProposalReview';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

type ApiProposal = Proposal & { source_document_id: string | null };

/**
 * Part E.5 review: document left, proposed entry right. Focusing a line shows its evidence
 * box on the source page. Edits create a new revision (server side); approval is not here
 * (Phase 5, monthly-file level only).
 */
export function ReviewScreen() {
  const { id = '' } = useParams();
  const raw = useRawFetch();
  const { me } = useSession();
  const [proposals, setProposals] = useState<ApiProposal[] | null | 'error'>(null);
  const [activeId, setActiveId] = useState<string | undefined>();
  const [pageUrl, setPageUrl] = useState<string | undefined>();

  const load = useCallback(async () => {
    try {
      const r = await raw(`/work-requests/${id}/proposals`);
      if (!r.ok) return setProposals('error');
      const items = (await r.json()) as ApiProposal[];
      setProposals(items);
      setActiveId((cur) => (cur && items.some((p) => p.id === cur) ? cur : items[0]?.id));
    } catch {
      setProposals('error');
    }
  }, [raw, id]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = Array.isArray(proposals) ? proposals.find((p) => p.id === activeId) ?? proposals[0] : undefined;
  const docId = active?.source_document_id;

  useEffect(() => {
    let url: string | undefined;
    setPageUrl(undefined);
    if (!docId) return;
    void raw(`/documents/${docId}/pages/1/image`).then(async (r) => {
      if (!r.ok) return;
      url = URL.createObjectURL(await r.blob());
      setPageUrl(url);
    });
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [raw, docId]);

  async function updateLines(proposalId: string, lines: ProposalLine[]) {
    const body = {
      lines: lines.map((l) => ({
        account_id: l.account_id,
        account_code: l.account_code,
        counterparty_id: l.counterparty_id ?? null,
        label: l.label,
        currency: l.currency,
        debit_tx: l.debit_tx ?? l.debit_mad,
        credit_tx: l.credit_tx ?? l.credit_mad,
        fx_rate: (l as ProposalLine & { fx_rate?: number }).fx_rate ?? 1,
        debit_mad: l.debit_mad,
        credit_mad: l.credit_mad,
        tax_code: l.tax_code ?? null,
        evidence_refs: l.evidence_refs, // never dropped: every line keeps its source (Part K 16)
      })),
    };
    const r = await raw(`/proposals/${proposalId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(problemMessage(await r.json().catch(() => ({})), "La modification n'a pas été enregistrée."));
    const saved = (await r.json()) as { id: string };
    setActiveId(saved.id);
    await load();
  }

  if (proposals === null) return <LoadingState label="Chargement des écritures proposées…" />;
  if (proposals === 'error')
    return <ErrorState title="Les écritures n'ont pas pu être chargées." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;

  return (
    <>
      <p className="text-sm">
        <Link to={`/files/${id}`} className="text-sky-ink hover:underline">Dossier mensuel</Link>
      </p>
      <h1 className="mt-1 text-[1.75rem]">Écritures proposées</h1>
      {proposals.length === 0 ? (
        <EmptyState title="Aucune écriture proposée. Proposez une écriture depuis une pièce lue du dossier." />
      ) : (
        <div className="mt-4" data-testid="review-screen">
          <ProposalReview
            key={active?.id}
            proposals={proposals}
            initialActiveId={active?.id}
            onUpdateLines={updateLines}
            documentPageUrl={pageUrl}
            documentPageCount={1}
            readOnly={!can(me, 'write')}
          />
        </div>
      )}
    </>
  );
}
