import type { InputHTMLAttributes, ReactNode } from 'react';

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm text-ink-2">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-1 block text-[0.8125rem] text-ink-2">{hint}</span>}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-9 w-full rounded-input border border-line bg-paper px-2 text-sm text-ink tabular-nums ${props.className ?? ''}`}
    />
  );
}

/** Inline message: red for failures (Part E.2), --ok for confirmations. Status is never colour alone. */
export function Message({ kind, children }: { kind: 'error' | 'ok'; children: ReactNode }) {
  return (
    <p role={kind === 'error' ? 'alert' : 'status'} className={`mt-2 text-sm ${kind === 'error' ? 'text-fail' : 'text-ok'}`} data-testid={`msg-${kind}`}>
      {kind === 'error' ? 'Erreur : ' : ''}
      {children}
    </p>
  );
}
