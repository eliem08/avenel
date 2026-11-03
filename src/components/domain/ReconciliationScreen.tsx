import React, { useState, useMemo, useCallback } from 'react';
import {
  ArrowRightLeft,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Building2,
  Calendar,
  Layers,
  Filter,
} from 'lucide-react';

export interface BankTransactionLine {
  id: string;
  line_index: number;
  booking_date: string;
  value_date?: string | null;
  amount: number; // Signed: positive = credit, negative = debit
  currency: string;
  description: string;
  external_reference?: string | null;
}

export interface ProposalSummary {
  id: string;
  journal_code: string;
  entry_date: string;
  label: string;
  amount_ttc: number;
  vat_amount?: number;
  counterparty_name?: string;
  invoice_number?: string;
}

export interface ReconciliationMatchItem {
  id: string;
  bank_transaction_id?: string | null;
  journal_proposal_id?: string | null;
  amount_mad: number;
  bank_date?: string | null;
  bank_desc?: string | null;
  proposal_date?: string | null;
  proposal_label?: string | null;
}

export interface ReconciliationMatch {
  id: string;
  status: 'proposed' | 'accepted' | 'rejected' | 'superseded';
  score?: number | null;
  reasons: string[];
  difference_mad: number;
  difference_kind?: 'vat_withheld' | 'bank_fee' | 'fx' | 'rounding' | 'unexplained' | null;
  decided_by?: string | null;
  decided_at?: string | null;
  items: ReconciliationMatchItem[];
}

export interface ReconciliationScreenProps {
  bankTransactions: BankTransactionLine[];
  proposals: ProposalSummary[];
  matches: ReconciliationMatch[];
  onAcceptMatch: (matchId: string) => Promise<void> | void;
  onRejectMatch: (matchId: string) => Promise<void> | void;
  readOnly?: boolean;
}

const DIFFERENCE_KIND_LABELS: Record<string, string> = {
  vat_withheld: 'TVA retenue à la source',
  bank_fee: 'Frais bancaires',
  fx: 'Écart de change',
  rounding: "Écart d'arrondi",
  unexplained: 'Écart non expliqué',
};

export const ReconciliationScreen: React.FC<ReconciliationScreenProps> = ({
  bankTransactions,
  proposals: _proposals,
  matches,
  onAcceptMatch,
  onRejectMatch,
  readOnly = false,
}) => {
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(
    matches.length > 0 ? matches[0].id : null
  );
  const [filterStatus, setFilterStatus] = useState<'all' | 'proposed' | 'accepted'>('all');
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const filteredMatches = useMemo(() => {
    if (filterStatus === 'all') return matches;
    return matches.filter((m) => m.status === filterStatus);
  }, [matches, filterStatus]);

  const activeMatch = useMemo(() => {
    return matches.find((m) => m.id === selectedMatchId) || filteredMatches[0] || null;
  }, [matches, selectedMatchId, filteredMatches]);

  const acceptedBankTxIds = useMemo(() => {
    const ids = new Set<string>();
    matches
      .filter((m) => m.status === 'accepted')
      .forEach((m) => {
        m.items.forEach((it) => {
          if (it.bank_transaction_id) ids.add(it.bank_transaction_id);
        });
      });
    return ids;
  }, [matches]);

  const handleAccept = useCallback(
    async (matchId: string) => {
      if (readOnly || isProcessing) return;
      setIsProcessing(true);
      setErrorMessage(null);
      try {
        await onAcceptMatch(matchId);
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Impossible d'accepter le rapprochement."
        );
      } finally {
        setIsProcessing(false);
      }
    },
    [onAcceptMatch, readOnly, isProcessing]
  );

  const handleReject = useCallback(
    async (matchId: string) => {
      if (readOnly || isProcessing) return;
      setIsProcessing(true);
      setErrorMessage(null);
      try {
        await onRejectMatch(matchId);
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Impossible de rejeter le rapprochement."
        );
      } finally {
        setIsProcessing(false);
      }
    },
    [onRejectMatch, readOnly, isProcessing]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!activeMatch) return;
      if (e.key === 'Enter') {
        if (activeMatch.status === 'proposed') {
          e.preventDefault();
          handleAccept(activeMatch.id);
        }
      } else if (e.key === 'Escape') {
        if (activeMatch.status === 'proposed') {
          e.preventDefault();
          handleReject(activeMatch.id);
        }
      }
    },
    [activeMatch, handleAccept, handleReject]
  );

  return (
    <div
      className="flex flex-col h-full bg-surface text-ink focus:outline-none"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      data-testid="reconciliation-screen"
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-6 py-4 bg-paper border-b border-line">
        <div className="flex items-center space-x-3">
          <ArrowRightLeft className="w-5 h-5 text-ok" />
          <h1 className="text-lg font-semibold text-ink">
            Rapprochement bancaire
          </h1>
          <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-surface text-ink">
            {matches.filter((m) => m.status === 'accepted').length} /{' '}
            {matches.length} rapprochés
          </span>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-sm text-ink-2">
            <Filter className="w-4 h-4 text-ink-2" />
            <select
              value={filterStatus}
              onChange={(e) =>
                setFilterStatus(e.target.value as 'all' | 'proposed' | 'accepted')
              }
              className="px-2.5 py-1 text-sm border border-line rounded-panel bg-paper focus:outline-none focus:ring-1 focus:ring-ok"
              aria-label="Filtrer les rapprochements par statut"
            >
              <option value="all">Tous les statuts</option>
              <option value="proposed">À rapprocher</option>
              <option value="accepted">Rapprochés</option>
            </select>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="mx-6 mt-4 p-3 rounded-panel bg-surface border border-line flex items-center space-x-2 text-sm text-fail"
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-fail" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main two-column layout */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        {/* Left column: Bank transactions */}
        <div className="col-span-5 border-r border-line bg-paper flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-surface border-b border-line flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Building2 className="w-4 h-4 text-ink-2" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-2">
                Lignes du relevé bancaire
              </h2>
            </div>
            <span className="text-xs text-ink-2 font-mono">
              {bankTransactions.length} lignes
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-line">
            {bankTransactions.map((tx) => {
              const isAccepted = acceptedBankTxIds.has(tx.id);
              const isMatchingActive =
                activeMatch &&
                activeMatch.items.some((it) => it.bank_transaction_id === tx.id);

              return (
                <div
                  key={tx.id}
                  className={`p-3 transition-colors ${
                    isMatchingActive
                      ? 'bg-surface border-l-4 border-ok'
                      : isAccepted
                      ? 'bg-surface/60 opacity-80'
                      : 'hover:bg-surface'
                  }`}
                  data-testid={`bank-line-${tx.id}`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-medium text-ink-2 flex items-center space-x-1">
                          <Calendar className="w-3 h-3 text-ink-2" />
                          <span>{tx.booking_date}</span>
                        </span>
                        {isAccepted && (
                          <span className="inline-flex items-center text-[10px] font-semibold text-ok bg-surface px-1.5 py-0.5 rounded">
                            Rapproché
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm font-medium text-ink line-clamp-1">
                        {tx.description}
                      </p>
                      {tx.external_reference && (
                        <p className="text-xs text-ink-2 font-mono mt-0.5">
                          Réf: {tx.external_reference}
                        </p>
                      )}
                    </div>

                    <div className="text-right">
                      <span
                        className={`text-sm font-mono font-semibold ${
                          tx.amount > 0 ? 'text-ok' : 'text-ink'
                        }`}
                      >
                        {tx.amount > 0 ? '+' : ''}
                        {tx.amount.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}{' '}
                        MAD
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right column: Reconciliation Candidates & Detail */}
        <div className="col-span-7 flex flex-col bg-surface overflow-hidden">
          <div className="px-6 py-3 bg-paper border-b border-line flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-ink-2" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-2">
                Candidats de rapprochement
              </h2>
            </div>
            <span className="text-xs text-ink-2">
              {filteredMatches.length} propositions
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {filteredMatches.length === 0 ? (
              <div className="text-center py-12 text-ink-2 text-sm">
                Aucun rapprochement correspondant à ce filtre.
              </div>
            ) : (
              filteredMatches.map((m) => {
                const isSelected = activeMatch?.id === m.id;
                const bankItems = m.items.filter((it) => it.bank_transaction_id);
                const propItems = m.items.filter((it) => it.journal_proposal_id);
                const hasDiff = m.difference_mad > 0;

                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedMatchId(m.id)}
                    className={`p-5 rounded-panel border bg-paper  transition-all cursor-pointer ${
                      isSelected
                        ? 'border-ok ring-2 ring-ok/20'
                        : 'border-line hover:border-line'
                    }`}
                    data-testid={`match-card-${m.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        {m.score !== null && m.score !== undefined && (
                          <div
                            className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                              m.score >= 0.97
                                ? 'bg-surface text-ok'
                                : 'bg-pink-wash text-pink-ink'
                            }`}
                          >
                            Score: {(m.score * 100).toFixed(0)}%
                          </div>
                        )}
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-medium ${
                            m.status === 'accepted'
                              ? 'bg-surface text-ok border border-line'
                              : m.status === 'rejected'
                              ? 'bg-surface text-fail border border-line'
                              : 'bg-surface text-ink'
                          }`}
                        >
                          {m.status === 'accepted'
                            ? 'Rapproché'
                            : m.status === 'rejected'
                            ? 'Rejeté'
                            : 'À rapprocher'}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        {m.status === 'proposed' && !readOnly && (
                          <>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAccept(m.id);
                              }}
                              disabled={isProcessing}
                              className="px-3 py-1.5 text-xs font-semibold text-ink bg-ok hover:bg-ok rounded-panel transition-colors flex items-center space-x-1  disabled:opacity-50"
                              data-testid={`btn-accept-${m.id}`}
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Rapprocher</span>
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReject(m.id);
                              }}
                              disabled={isProcessing}
                              className="px-3 py-1.5 text-xs font-semibold text-ink-2 hover:text-ink hover:bg-surface rounded-panel transition-colors flex items-center space-x-1 border border-line disabled:opacity-50"
                              data-testid={`btn-reject-${m.id}`}
                            >
                              <XCircle className="w-3.5 h-3.5" />
                              <span>Rejeter</span>
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Matched pieces comparison */}
                    <div className="mt-4 grid grid-cols-2 gap-4 p-3 bg-surface rounded-panel border border-line text-xs">
                      <div>
                        <span className="font-semibold text-ink-2 uppercase tracking-wider block mb-1">
                          Banque ({bankItems.length})
                        </span>
                        {bankItems.map((bi) => (
                          <div key={bi.id} className="mt-1">
                            <p className="font-medium text-ink line-clamp-1">
                              {bi.bank_desc || 'Mouvement bancaire'}
                            </p>
                            <div className="flex justify-between items-center text-ink-2 font-mono mt-0.5">
                              <span>{bi.bank_date || ''}</span>
                              <span className="font-semibold text-ink">
                                {bi.amount_mad.toFixed(2)} MAD
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="border-l border-line pl-4">
                        <span className="font-semibold text-ink-2 uppercase tracking-wider block mb-1">
                          Pièce comptable ({propItems.length})
                        </span>
                        {propItems.map((pi) => (
                          <div key={pi.id} className="mt-1">
                            <p className="font-medium text-ink line-clamp-1">
                              {pi.proposal_label || 'Facture'}
                            </p>
                            <div className="flex justify-between items-center text-ink-2 font-mono mt-0.5">
                              <span>{pi.proposal_date || ''}</span>
                              <span className="font-semibold text-ink">
                                {pi.amount_mad.toFixed(2)} MAD
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Difference section */}
                    {hasDiff && (
                      <div className="mt-3 p-2.5 bg-pink-wash rounded border border-pink flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          <AlertCircle className="w-4 h-4 text-pink-ink flex-shrink-0" />
                          <span className="font-medium text-pink-ink">
                            {m.difference_kind
                              ? DIFFERENCE_KIND_LABELS[m.difference_kind] || m.difference_kind
                              : "Écart de règlement"}
                          </span>
                        </div>
                        <span className="font-mono font-semibold text-pink-ink">
                          {m.difference_mad.toFixed(2)} MAD
                        </span>
                      </div>
                    )}

                    {/* Reasons */}
                    {m.reasons.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {m.reasons.map((r, idx) => (
                          <span
                            key={idx}
                            className="text-[11px] bg-surface text-ink-2 px-2 py-0.5 rounded"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
