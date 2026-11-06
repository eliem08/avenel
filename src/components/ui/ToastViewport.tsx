import { useToastStore } from '@/store/toastStore';

/** Floating messages (Part E.4: shadow only on floating layers). Words carry the meaning, not colour. */
export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} role="status" className="pointer-events-auto flex items-start gap-3 rounded-panel border border-line bg-paper p-3 text-sm shadow-float">
          <p className={`flex-1 ${t.kind === 'error' ? 'text-fail' : 'text-ink'}`}>{t.message}</p>
          <button type="button" onClick={() => dismiss(t.id)} className="text-ink-2" aria-label="Fermer">×</button>
        </div>
      ))}
    </div>
  );
}
