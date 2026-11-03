import { EmptyState } from '@/components/ui/States';

export function LaterScreen({ title }: { title: string }) {
  return (
    <>
      <h1 className="text-[1.75rem]">{title}</h1>
      <EmptyState title="Cet écran n'est pas encore disponible dans cette version." />
    </>
  );
}
