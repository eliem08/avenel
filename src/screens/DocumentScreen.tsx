import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NETWORK_ERROR, problemMessage } from '@/api/problem';
import { useRawFetch } from '@/api/raw';
import { DocumentViewer, type FieldExtraction } from '@/components/domain/DocumentViewer';
import { can, useSession } from '@/session/SessionProvider';
import { Button } from '@/components/ui/Button';
import { ErrorState, LoadingState } from '@/components/ui/States';
import { DOC_TYPE_FR } from './labels';

interface DocInfo {
  id: string;
  work_request_id: string | null;
  original_filename: string;
  status: string;
  doc_type: string | null;
}
interface Page {
  pageNumber: number;
  imageUrl: string;
  width: number;
  height: number;
}
type Fields = Record<string, FieldExtraction>;

/** Low confidence fields are shown "à confirmer" until a person confirms them (Part E.5). */
const CONFIRM_THRESHOLD = 0.9;
const MAX_PAGES = 50;

function imageSize(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => resolve({ width: 800, height: 1131 });
    img.src = url;
  });
}

export function DocumentScreen() {
  const { id = '' } = useParams();
  const raw = useRawFetch();
  const { me } = useSession();
  const [doc, setDoc] = useState<DocInfo | null | 'error' | 'missing'>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [pages, setPages] = useState<Page[]>([]);

  const load = useCallback(async () => {
    try {
      const d = await raw(`/documents/${id}`);
      if (d.status === 404) return setDoc('missing');
      if (!d.ok) return setDoc('error');
      setDoc((await d.json()) as DocInfo);

      const ex = await raw(`/documents/${id}/extraction`);
      if (ex.ok) {
        const body = (await ex.json()) as { fields: Record<string, unknown> };
        const f: Fields = {};
        for (const [k, v] of Object.entries(body.fields)) {
          if (v && typeof v === 'object' && !Array.isArray(v) && 'confidence' in v) {
            const fe = v as FieldExtraction & { confidence: number };
            f[k] = { ...fe, confirmed: fe.confirmed ?? fe.confidence >= CONFIRM_THRESHOLD };
          }
        }
        setFields(f);
      } else setFields({});

      const loaded: Page[] = [];
      for (let n = 1; n <= MAX_PAGES; n++) {
        const r = await raw(`/documents/${id}/pages/${n}/image`);
        if (!r.ok) break;
        const url = URL.createObjectURL(await r.blob());
        loaded.push({ pageNumber: n, imageUrl: url, ...(await imageSize(url)) });
      }
      setPages(loaded);
    } catch {
      setDoc('error');
    }
  }, [raw, id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Release page blobs when leaving the screen.
  useEffect(() => () => pages.forEach((p) => URL.revokeObjectURL(p.imageUrl)), [pages]);

  const initialFields = useMemo(() => fields ?? {}, [fields]);

  async function save(updated: Fields) {
    const changed: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(updated)) {
      if (String(v.value ?? '') !== String(initialFields[k]?.value ?? '')) changed[k] = v.value === '' ? null : v.value;
    }
    if (Object.keys(changed).length === 0) return;
    const r = await raw(`/documents/${id}/extraction`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields: changed }),
    });
    if (!r.ok) throw new Error(problemMessage(await r.json().catch(() => ({})), "La correction n'a pas été enregistrée."));
    await load();
  }

  if (doc === 'missing')
    return <ErrorState title="Pièce introuvable." detail="Elle n'existe pas ou vous n'y avez pas accès." />;
  if (doc === 'error')
    return <ErrorState title="La pièce n'a pas pu être chargée." detail={NETWORK_ERROR} action={<Button variant="secondary" onClick={() => void load()}>Réessayer</Button>} />;
  if (doc === null || fields === null) return <LoadingState label="Chargement de la pièce…" />;

  const readOnly = !can(me, 'write') || doc.status === 'quarantined';
  return (
    <>
      <p className="text-sm">
        {doc.work_request_id ? (
          <Link to={`/files/${doc.work_request_id}`} className="text-sky-ink hover:underline">Dossier mensuel</Link>
        ) : (
          <Link to="/queue" className="text-sky-ink hover:underline">File de travail</Link>
        )}
      </p>
      <h1 className="mt-1 text-[1.75rem]" data-testid="document-title">{doc.original_filename}</h1>
      <div className="mt-4">
        <DocumentViewer
          documentId={doc.id}
          filename={doc.original_filename}
          docType={doc.doc_type ? DOC_TYPE_FR[doc.doc_type] ?? doc.doc_type : '—'}
          pageCount={Math.max(1, pages.length)}
          pages={pages}
          initialFields={initialFields}
          onSave={save}
          readOnly={readOnly}
          isQuarantined={doc.status === 'quarantined'}
        />
      </div>
    </>
  );
}
