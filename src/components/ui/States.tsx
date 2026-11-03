import type { ReactNode } from 'react';

export function LoadingState({ label }: { label: string }) {
  return (
    <p role="status" aria-live="polite" className="py-8 text-sm text-ink-2" data-testid="state-loading">
      {label}
    </p>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="py-8" data-testid="state-empty">
      <p className="text-base text-ink">{title}</p>
      {children}
    </div>
  );
}

export function ErrorState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div role="alert" className="rounded-panel border border-fail bg-paper p-4" data-testid="state-error">
      <p className="text-base font-medium text-fail">{title}</p>
      <p className="mt-1 text-sm text-ink-2">{detail}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
