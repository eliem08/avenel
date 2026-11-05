import { useEffect, useRef, type ReactNode } from 'react';

/** Native <dialog> (modal, focus trap, Escape). Shadow only on floating layers (Part E.4). */
export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="w-[28rem] max-w-[calc(100vw-2rem)] rounded-panel border border-line bg-paper p-6 text-ink shadow-float backdrop:bg-ink/40"
    >
      <h2 id="dialog-title" className="text-xl">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </dialog>
  );
}
