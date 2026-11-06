import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import { useAuth } from '@/auth/AuthProvider';
import { hasFreshMfa } from '@/auth/oidc';
import { ApprovalScreen, type ApprovalWorkRequest, type CurrentReviewer, type ReviewIssueItem } from '@/components/domain/ApprovalScreen';
import { ExportScreen, type ExportResult, type ExportTarget } from '@/components/domain/ExportScreen';
import { useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { Message } from '@/components/ui/Form';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';

interface PendingApproval {
  id: string;
  client_entity_id: string;
  client_name: string;
  work_request_id: string;
  revision: number;
  subject_hash: string;
  created_at: string;
  preparer_name: string;
}

const shortHash = (h: string) => `${h.slice(0, 4)}…${h.slice(-4)}`;

/** Part E.5 approvals: the list of monthly files waiting for a registered professional. */
export function ApprovalsPage() {
  const raw = useRawFetch();
  const [items, setItems] = useState<PendingApproval[] | null | 'error' | 'forbidden'>(null);
  useEffect(() => {
    void raw('/approvals')
      .then(async (r) => setItems(r.status === 403 ? 'forbidden' : r.ok ? ((await r.json()) as PendingApproval[]) : 'error'))
      .catch(() => setItems('error'));
  }, [raw]);

  return (
    <>
      <h1 className="text-[1.75rem]">Validations</h1>
      <div className="mt-6">
        {items === null && <LoadingState label="Chargement des dossiers à valider…" />}
        {items === 'error' && <ErrorState title="Les validations n'ont pas pu être chargées." detail={NETWORK_ERROR} />}
        {items === 'forbidden' && <EmptyState title="Les validations sont réservées au cabinet." />}
        {Array.isArray(items) && items.length === 0 && <EmptyState title="Aucun dossier en attente de validation." />}
        {Array.isArray(items) && items.length > 0 && (
          <table className="w-full border-collapse text-sm" data-testid="approvals-table">
            <thead className="bg-surface text-left text-ink-2">
              <tr className="h-9 border-b border-line">
                <th scope="col" className="px-3 font-medium">Société</th>
                <th scope="col" className="px-3 font-medium">Préparé par</th>
                <th scope="col" className="px-3 font-medium">Empreinte</th>
                <th scope="col" className="px-3 font-medium">Demandé le</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="h-9 border-b border-l-[3px] border-b-line border-l-pink" data-testid="approval-row">
                  <td className="px-3">
                    <Link to={`/approvals/${a.id}`} className="text-sky-ink hover:underline">{a.client_name}</Link>
                  </td>
                  <td className="px-3">{a.preparer_name || '—'}</td>
                  <td className="px-3 tabular-nums">{shortHash(a.subject_hash)}</td>
                  <td className="px-3 tabular-nums">{a.created_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

interface FileFacts {
  approval: PendingApproval;
  workRequest: ApprovalWorkRequest;
  reviewIssues: ReviewIssueItem[];
}

/**
 * Part E.5 approval page: a summary, not a modal. "Valider le dossier" first requires an MFA
 * login no older than 5 minutes (Part K 5): otherwise the browser re-authenticates with
 * prompt=login&max_age=300 and comes back here. After approval: "Télécharger l'export".
 */
export function ApprovalDecisionPage() {
  const { id = '' } = useParams();
  const raw = useRawFetch();
  const { user, requireFreshMfa } = useAuth();
  const { me } = useSession();
  const [facts, setFacts] = useState<FileFacts | null | 'error' | 'missing'>(null);
  const [approved, setApproved] = useState<{ subjectHash: string } | null>(null);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);
  const [currentExport, setCurrentExport] = useState<ExportResult | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await raw('/approvals');
      if (!list.ok) return setFacts('error');
      const approval = ((await list.json()) as PendingApproval[]).find((a) => a.id === id);
      if (!approval) return setFacts(approved ? facts : 'missing');
      const [wr, props, iss] = await Promise.all([
        raw(`/work-requests/${approval.work_request_id}`),
        raw(`/work-requests/${approval.work_request_id}/proposals`),
        raw(`/work-requests/${approval.work_request_id}/issues`),
      ]);
      const wrBody = (await wr.json()) as { status: string; accounting_period_id?: string };
      const proposals = (await props.json()) as { status: string; lines: { debit_mad: number; credit_mad: number }[] }[];
      const issues = ((await iss.json()) as { items: { id: string; code: string; severity: string; status: string; resolution?: string; resolution_note?: string }[] }).items;
      const active = proposals.filter((p) => p.status !== 'superseded');
      const sum = (k: 'debit_mad' | 'credit_mad') => Math.round(active.flatMap((p) => p.lines).reduce((s, l) => s + Number(l[k] || 0), 0) * 100) / 100;
      const open = issues.filter((i) => ['open', 'assigned', 'waiting_client'].includes(i.status));
      setFacts({
        approval,
        workRequest: {
          id: approval.work_request_id,
          client_entity_id: approval.client_entity_id,
          legal_name: approval.client_name,
          period_code: '',
          status: wrBody.status,
          prepared_by: '',
          prepared_by_name: approval.preparer_name,
          requested_at: approval.created_at,
          subject_hash: approval.subject_hash,
          proposals_count: active.length,
          total_debit_mad: sum('debit_mad'),
          total_credit_mad: sum('credit_mad'),
          open_blocking_issues_count: open.filter((i) => i.severity === 'blocking').length,
          open_warning_issues_count: open.filter((i) => i.severity === 'review').length,
          unacknowledged_review_issues_count: open.filter((i) => i.severity === 'review').length,
        },
        reviewIssues: issues.filter((i) => i.severity === 'review').map((i) => ({ id: i.id, code: i.code, status: i.status, resolution: i.resolution, resolution_note: i.resolution_note })),
      });
    } catch {
      setFacts('error');
    }
  }, [raw, id, approved, facts]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw, id]);

  async function decide(decision: 'approved' | 'rejected', reason: string, subjectHash: string) {
    setMsg(null);
    // Step-up before deciding: MFA within 5 minutes, or re-authenticate and come back here.
    if (!hasFreshMfa(user)) {
      await requireFreshMfa(`/approvals/${id}`);
      return;
    }
    const r = await raw(`/approvals/${id}:decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, reason, subject_hash: subjectHash }),
    }).catch(() => null);
    if (!r) return setMsg({ kind: 'error', text: NETWORK_ERROR });
    if (r.status === 401 && (r.headers.get('www-authenticate') ?? '').includes('insufficient_user_authentication')) {
      await requireFreshMfa(`/approvals/${id}`);
      return;
    }
    const body = await r.json().catch(() => ({}));
    if (r.status === 409)
      return setMsg({ kind: 'error', text: problemMessage(body, 'Le dossier a changé depuis la demande de validation. Demandez une nouvelle validation.') });
    if (!r.ok) return setMsg({ kind: 'error', text: problemMessage(body, "La décision n'a pas été enregistrée.") });
    if (decision === 'approved') {
      setApproved({ subjectHash });
      setMsg({ kind: 'ok', text: 'Dossier validé.' });
    } else setMsg({ kind: 'ok', text: 'Dossier rejeté. Il revient en préparation.' });
  }

  async function generateExport(target: ExportTarget): Promise<ExportResult> {
    const r = await raw(`/work-requests/${typeof facts === 'object' && facts ? facts.approval.work_request_id : ''}/exports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: id, target }),
    });
    const body = (await r.json().catch(() => ({}))) as Record<string, unknown>;
    if (!r.ok) {
      const text = r.status === 409 ? 'Le dossier a changé depuis la validation. Demandez une nouvelle validation.' : problemMessage(body, "L'export n'a pas été généré.");
      setMsg({ kind: 'error', text });
      throw new Error(text);
    }
    const res: ExportResult = {
      id: String(body.id ?? body.export_id ?? ''),
      work_request_id: String(body.work_request_id ?? ''),
      client_entity_id: String(body.client_entity_id ?? ''),
      target,
      encoding: String(body.encoding ?? ''),
      status: 'ready',
      subject_hash: String(body.subject_hash ?? approved?.subjectHash ?? ''),
      file_sha256: String(body.file_sha256 ?? ''),
      // The API does not return the evidence pack hash; left empty rather than invented.
      evidence_pack_sha256: String(body.evidence_pack_sha256 ?? ''),
      file_size_bytes: typeof body.file_size_bytes === 'number' ? body.file_size_bytes : undefined,
      created_at: String(body.created_at ?? new Date().toISOString()),
    };
    setCurrentExport(res);
    setMsg({ kind: 'ok', text: 'Export prêt.' });
    return res;
  }

  async function download(path: string, fallbackName: string) {
    const r = await raw(path);
    if (!r.ok) return setMsg({ kind: 'error', text: problemMessage(await r.json().catch(() => ({})), "Le téléchargement a échoué.") });
    const name = /filename="?([^";]+)"?/.exec(r.headers.get('content-disposition') ?? '')?.[1] ?? fallbackName;
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (facts === null) return <LoadingState label="Chargement du dossier à valider…" />;
  if (facts === 'missing') return <ErrorState title="Validation introuvable." detail="Elle a déjà été décidée ou vous n'y avez pas accès." />;
  if (facts === 'error')
    return <ErrorState title="Le dossier n'a pas pu être chargé." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;

  const reviewer: CurrentReviewer = {
    user_id: me?.user_id ?? '',
    full_name: me?.full_name ?? '',
    role: me?.role ?? '',
    professional_title: (me?.professional_title as CurrentReviewer['professional_title']) ?? null,
    professional_registration_no: me?.professional_registration_no ?? null,
  };

  return (
    <>
      <p className="text-sm">
        <Link to="/approvals" className="text-sky-ink hover:underline">Validations</Link>
      </p>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
      <div className="mt-4" data-testid="approval-page">
        {!approved ? (
          <ApprovalScreen
            workRequest={facts.workRequest}
            reviewer={reviewer}
            reviewIssues={facts.reviewIssues}
            onApprove={(reason, hash) => decide('approved', reason, hash)}
            onReject={(reason) => decide('rejected', reason, facts.approval.subject_hash)}
          />
        ) : (
          <ExportScreen
            workRequestId={facts.approval.work_request_id}
            approvalId={id}
            clientName={facts.approval.client_name}
            periodCode=""
            approvedSubjectHash={approved.subjectHash}
            availableProfiles={[]}
            currentExport={currentExport}
            onGenerateExport={(t) => generateExport(t)}
            onDownloadFile={(eid) => download(`/exports/${eid}/file`, 'export.csv')}
            onDownloadEvidencePack={(eid) => download(`/exports/${eid}/evidence-pack`, 'dossier-probant.zip')}
          />
        )}
      </div>
    </>
  );
}
