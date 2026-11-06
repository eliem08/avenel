import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApi } from '@/api/useApi';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { sha256Hex, useRawFetch } from '@/api/raw';
import { Message } from '@/components/ui/Form';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import {
  DOC_TYPE_FR,
  DOCUMENT_STATUS_FR,
  ISSUE_CODE_FR,
  NEEDS_PERSON_DOC,
  SEVERITY_FR,
  WORK_REQUEST_STATUS_FR,
} from './labels';

interface Doc {
  id: string;
  original_filename: string;
  status: string;
  doc_type: string | null;
  received_at: string | null;
}
interface Issue {
  id: string;
  code: string;
  severity: string;
  status: string;
  subject_document_id: string | null;
}
interface FileInfo {
  id: string;
  client_entity_id: string;
  status: string;
  client_name: string;
}

const ACTIVE_ISSUE = new Set(['open', 'assigned', 'waiting_client']);
const ACCEPT = '.pdf,.png,.jpg,.jpeg,.tif,.tiff';

export function FileScreen() {
  const { id = '' } = useParams();
  const api = useApi();
  const [info, setInfo] = useState<FileInfo | null | 'error' | 'missing'>(null);
  const [docs, setDocs] = useState<Doc[] | null | 'error'>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    try {
      const wr = await api.GET('/work-requests/{id}', { params: { path: { id } } });
      if (wr.response.status === 404) return setInfo('missing');
      if (!wr.data) return setInfo('error');
      const wrData = wr.data as unknown as { id: string; client_entity_id: string; status: string };
      const ce = await api.GET('/client-entities/{id}', { params: { path: { id: wrData.client_entity_id } } });
      setInfo({ ...wrData, client_name: ce.data?.legal_name ?? '—' });
      const [d, i] = await Promise.all([
        api.GET('/work-requests/{id}/documents', { params: { path: { id } } }),
        api.GET('/work-requests/{id}/issues', { params: { path: { id } } }),
      ]);
      setDocs(d.data ? ((d.data as unknown as { items: Doc[] }).items) : 'error');
      setIssues(i.data ? ((i.data as unknown as { items: Issue[] }).items) : []);
    } catch {
      setInfo('error');
    }
  }, [api, id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (info === null) return <LoadingState label="Chargement du dossier…" />;
  if (info === 'missing')
    return <ErrorState title="Dossier introuvable." detail="Il n'existe pas ou vous n'y avez pas accès. Revenez à la file de travail." />;
  if (info === 'error')
    return <ErrorState title="Le dossier n'a pas pu être chargé." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;

  const active = issues.filter((x) => ACTIVE_ISSUE.has(x.status));
  const blocking = active.filter((x) => x.severity === 'blocking').length;

  return (
    <>
      <p className="text-sm">
        <Link to="/queue" className="text-sky-ink hover:underline">File de travail</Link>
      </p>
      <h1 className="mt-1 text-[1.75rem]" data-testid="file-title">{info.client_name}</h1>
      <p className="mt-1 text-sm text-ink-2">Dossier mensuel · {WORK_REQUEST_STATUS_FR[info.status] ?? info.status}</p>

      {active.length > 0 && (
        <div className="mt-4 border-l-[3px] border-l-pink bg-pink-wash px-3 py-2 text-sm" data-testid="issue-strip">
          <span className="font-medium text-pink-ink">
            {active.length} anomalie{active.length > 1 ? 's' : ''} à traiter
            {blocking > 0 ? ` : ${blocking} bloquante${blocking > 1 ? 's' : ''}` : ''}
          </span>
        </div>
      )}

      <p className="mt-3 text-sm">
        <Link to={`/files/${id}/review`} className="text-sky-ink hover:underline" data-testid="link-review">
          Revoir les écritures proposées
        </Link>
      </p>

      <Uploader workRequestId={id} onDone={() => void load()} />

      <section className="mt-8" aria-labelledby="docs-title">
        <h2 id="docs-title" className="text-xl">Pièces</h2>
        {notice && <Message kind={notice.ok ? 'ok' : 'error'}>{notice.text}</Message>}
        {docs === null && <LoadingState label="Chargement des pièces…" />}
        {docs === 'error' && <ErrorState title="Les pièces n'ont pas pu être chargées." detail={NETWORK_ERROR} />}
        {Array.isArray(docs) && docs.length === 0 && <EmptyState title="Aucune pièce. Déposez les pièces du mois pour commencer." />}
        {Array.isArray(docs) && docs.length > 0 && (
          <table className="mt-3 w-full border-collapse text-sm" data-testid="docs-table">
            <thead className="bg-surface text-left text-ink-2">
              <tr className="h-9 border-b border-line">
                <th scope="col" className="px-3 font-medium">Pièce</th>
                <th scope="col" className="px-3 font-medium">Type</th>
                <th scope="col" className="px-3 font-medium">État</th>
                <th scope="col" className="px-3 font-medium">Anomalies</th>
                <th scope="col" className="px-3 font-medium"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => {
                const n = active.filter((x) => x.subject_document_id === d.id).length;
                const needsPerson = NEEDS_PERSON_DOC.has(d.status) || n > 0;
                return (
                  <tr
                    key={d.id}
                    data-testid="doc-row"
                    data-status={d.status}
                    className={`h-9 border-b border-l-[3px] border-b-line ${needsPerson ? 'border-l-pink' : 'border-l-transparent'}`}
                  >
                    <td className="px-3">
                      {d.status === 'quarantined' ? (
                        <span>{d.original_filename}</span>
                      ) : (
                        <Link to={`/documents/${d.id}`} className="text-sky-ink hover:underline">{d.original_filename}</Link>
                      )}
                    </td>
                    <td className="px-3">{d.doc_type ? DOC_TYPE_FR[d.doc_type] ?? d.doc_type : '—'}</td>
                    <td className={`px-3 ${needsPerson ? 'text-pink-ink' : ''}`}>{DOCUMENT_STATUS_FR[d.status] ?? d.status}</td>
                    <td className="px-3 tabular-nums">{n || '—'}</td>
                    <td className="px-3 text-right">
                      {(d.status === 'read' || d.status === 'needs_review') && (
                        <ProposeButton documentId={d.id} onDone={(text, ok) => { setNotice({ text, ok }); void load(); }} />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {active.length > 0 && (
        <section className="mt-8" aria-labelledby="issues-title">
          <h2 id="issues-title" className="text-xl">Anomalies</h2>
          <ul className="mt-3 divide-y divide-line border-y border-line text-sm" data-testid="issues-list">
            {active.map((x) => (
              <li key={x.id} className="flex items-center gap-3 py-2" data-testid="issue-row" data-code={x.code}>
                <span className={x.severity === 'blocking' ? 'font-medium text-pink-ink' : 'text-ink-2'}>{SEVERITY_FR[x.severity] ?? x.severity}</span>
                <span>{ISSUE_CODE_FR[x.code] ?? x.code}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

type UploadState = { kind: 'idle' } | { kind: 'busy'; step: string } | { kind: 'done'; ok: boolean; text: string };

function Uploader({ workRequestId, onDone }: { workRequestId: string; onDone: () => void }) {
  const raw = useRawFetch();
  const input = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>({ kind: 'idle' });
  const [over, setOver] = useState(false);

  async function upload(file: File) {
    try {
      setState({ kind: 'busy', step: `Envoi de ${file.name}…` });
      const bytes = await file.arrayBuffer();
      const init = await raw(`/work-requests/${workRequestId}/uploads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_filename: file.name,
          byte_size: bytes.byteLength,
          mime_type: file.type || 'application/octet-stream',
          sha256: await sha256Hex(bytes),
        }),
      });
      const initBody = (await init.json().catch(() => ({}))) as { document_id?: string; resubmitted?: boolean };
      if (!init.ok || !initBody.document_id) {
        return setState({ kind: 'done', ok: false, text: problemMessage(initBody, "La pièce n'a pas été reçue.") });
      }
      if (initBody.resubmitted) {
        onDone();
        return setState({ kind: 'done', ok: true, text: `${file.name} a déjà été reçue pour cette société. Aucune nouvelle pièce créée.` });
      }
      const put = await raw(`/documents/${initBody.document_id}/content`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: bytes,
      });
      if (!put.ok) {
        return setState({ kind: 'done', ok: false, text: problemMessage(await put.json().catch(() => ({})), "Le fichier n'a pas été enregistré.") });
      }
      setState({ kind: 'busy', step: `Lecture de ${file.name}…` });
      const done = await raw(`/documents/${initBody.document_id}:complete-upload`, { method: 'POST' });
      const body = (await done.json().catch(() => ({}))) as { status?: string };
      onDone();
      if (!done.ok) return setState({ kind: 'done', ok: false, text: problemMessage(body, "La pièce n'a pas pu être lue.") });
      setState({
        kind: 'done',
        ok: true,
        text: body.status === 'needs_review' ? `${file.name} lue : des champs sont à traiter.` : `${file.name} lue.`,
      });
    } catch {
      setState({ kind: 'done', ok: false, text: NETWORK_ERROR });
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void upload(f);
  }

  const busy = state.kind === 'busy';
  return (
    <section className="mt-6" aria-label="Dépôt de pièces">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`flex items-center justify-between rounded-panel border border-dashed px-4 py-4 ${over ? 'border-sky bg-sky-wash' : 'border-line bg-surface'}`}
        data-testid="file-drop"
      >
        <p className="text-sm text-ink-2">Déposez une pièce ici (PDF ou image, 50 Mo au plus).</p>
        <Button variant="secondary" onClick={() => input.current?.click()} disabled={busy}>
          Choisir un fichier
        </Button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          data-testid="input-upload"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void upload(f);
            e.target.value = '';
          }}
        />
      </div>
      {busy && <p role="status" className="mt-2 text-sm text-ink-2" data-testid="upload-progress">{state.step}</p>}
      {state.kind === 'done' && <Message kind={state.ok ? 'ok' : 'error'}>{state.text}</Message>}
    </section>
  );
}

function ProposeButton({ documentId, onDone }: { documentId: string; onDone: (text: string, ok: boolean) => void }) {
  const raw = useRawFetch();
  const [busy, setBusy] = useState(false);
  async function propose() {
    setBusy(true);
    try {
      const r = await raw(`/documents/${documentId}:generate-proposal`, { method: 'POST' });
      const body = (await r.json().catch(() => ({}))) as { status?: string; issue_code?: string; detail?: string };
      if (!r.ok) onDone(problemMessage(body, "L'écriture n'a pas pu être proposée."), false);
      else if (body.status === 'blocked')
        onDone(
          body.issue_code === 'ACCOUNT_UNMAPPED'
            ? "Écriture non proposée : un compte de TVA n'est pas approuvé pour cette société. Approuvez-le dans la fiche client (Comptes de TVA)."
            : `Écriture non proposée : ${body.detail ?? body.issue_code ?? 'anomalie bloquante'}.`,
          false,
        );
      else onDone('Écriture proposée. Revoyez-la dans les écritures proposées.', true);
    } catch {
      onDone(NETWORK_ERROR, false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Button variant="quiet" onClick={() => void propose()} disabled={busy} data-testid={`btn-propose-${documentId}`}>
      Proposer l'écriture
    </Button>
  );
}
