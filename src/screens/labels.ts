// Display labels only (French, Part E.8). Codes and statuses come from the API unchanged.

export const WORK_REQUEST_STATUS_FR: Record<string, string> = {
  draft: 'Brouillon',
  intake: 'Réception',
  extracting: 'Lecture',
  preparing: 'Préparation',
  reconciling: 'Rapprochement',
  quality_check: 'Contrôle',
  needs_attention: 'À traiter',
  awaiting_approval: 'À valider',
  exporting: 'Export',
  completed: 'Terminé',
  completed_with_open_items: 'Terminé avec anomalies',
  cancelled: 'Annulé',
  failed: 'En échec',
};

export const DOCUMENT_STATUS_FR: Record<string, string> = {
  received: 'Reçue',
  processing: 'En lecture',
  read: 'Lue',
  needs_review: 'À traiter',
  rejected: 'Rejetée',
  quarantined: 'En quarantaine',
};

export const DOC_TYPE_FR: Record<string, string> = {
  purchase_invoice: "Facture d'achat",
  sales_invoice: 'Facture de vente',
  credit_note: 'Avoir',
  bank_statement: 'Relevé bancaire',
  receipt: 'Reçu',
  expense_note: 'Note de frais',
  customs_document: 'Déclaration unique de marchandises (DUM)',
  other: 'Autre',
};

export const ISSUE_CODE_FR: Record<string, string> = {
  DOC_MALWARE: 'Pièce mise en quarantaine : logiciel malveillant détecté',
  TOTALS_INCONSISTENT: 'Les totaux ne concordent pas',
  INVOICE_MISSING_MANDATORY_FIELD: 'Mention obligatoire manquante',
  DUPLICATE_PROBABLE: 'Doublon probable',
  ACCOUNT_UNMAPPED: 'Compte non paramétré',
  VAT_RATE_UNKNOWN: 'Taux de TVA inconnu',
};

export const SEVERITY_FR: Record<string, string> = {
  blocking: 'Bloquante',
  review: 'À vérifier',
  info: 'Information',
};

/** Statuses where a person must act: pink rule and pink text (Part E.2). */
export const NEEDS_PERSON_DOC = new Set(['needs_review', 'quarantined']);
