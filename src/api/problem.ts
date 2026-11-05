/** Turns an API error body (RFC 9457 problem+json, Part K 6) into a sentence for the user. */
export function problemMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object') {
    const e = error as { detail?: unknown; title?: unknown };
    if (typeof e.detail === 'string' && e.detail) return e.detail;
    if (Array.isArray(e.detail) && e.detail.length > 0) {
      const first = e.detail[0] as { msg?: unknown };
      if (typeof first?.msg === 'string') return first.msg;
    }
    if (typeof e.title === 'string' && e.title) return e.title;
  }
  return fallback;
}

export const NETWORK_ERROR = "Le serveur AVENEL ne répond pas. Réessayez dans un instant ; si le problème continue, contactez l'administrateur du cabinet.";
