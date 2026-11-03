import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'quiet' | 'danger';
const styles: Record<Variant, string> = {
  // Part E.2: primary is --sky fill with --ink text, never white on sky.
  primary: 'bg-sky text-ink hover:bg-sky-ink hover:text-paper',
  secondary: 'border border-line bg-paper text-ink hover:bg-surface',
  quiet: 'text-sky-ink hover:bg-sky-wash',
  danger: 'border border-fail bg-paper text-fail hover:bg-surface',
};

export function Button({ variant = 'primary', className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`inline-flex h-9 items-center gap-2 rounded-input px-4 text-sm font-medium disabled:opacity-60 ${styles[variant]} ${className}`}
      {...rest}
    />
  );
}
