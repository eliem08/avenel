"""Deterministic lettrage candidates (Phase 6b, ARCHITECTURE.md D.7b).

Pure functions, no database and no model: given the open items of one account and one
counterparty, propose groups of debit and credit lines whose allocated amounts balance exactly.
No tolerance is applied. Rounding or FX tolerances are expert values (pack rule
`lettrage.tolerance_mad`, needs_expert) and are not invented here.

Candidate kinds, in the order they are tried:
  exact    one debit = one credit
  grouped  one payment settles several invoices (exact sum)
  split    one invoice is settled by several payments or credit notes (exact sum)
The invoice side is the debit on customer accounts (342x) and the credit on supplier
accounts (441x).
  partial  one payment smaller than one invoice, only when they share a reference token;
           the invoice keeps an open balance
Each line is used by at most one candidate per run.
"""

from __future__ import annotations

import datetime
import itertools
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

MAX_GROUP_SIZE = 5
MAX_COMBINATIONS = 20_000
_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9/-]{2,}")
_STOP = {"FAC", "FACT", "FACTURE", "VIR", "VIREMENT", "REGLEMENT", "PAIEMENT", "CHQ", "CHEQUE",
         "AVOIR", "CLIENT", "FOURNISSEUR", "SARL", "SA", "MAD", "REF", "RECU", "EFFET"}


@dataclass(frozen=True)
class OpenItem:
    line_id: uuid.UUID
    side: str  # 'debit' or 'credit'
    open_mad: Decimal
    entry_date: datetime.date
    label: str


@dataclass
class Candidate:
    kind: str
    allocations: list[tuple[uuid.UUID, str, Decimal]]
    total_mad: Decimal
    reasons: list[str] = field(default_factory=list)


def reference_tokens(label: str) -> set[str]:
    """Reference-like tokens (contain a digit, at least 3 chars), e.g. FAC-2026-0412 -> {FAC-2026-0412, 2026-0412}."""
    out: set[str] = set()
    for tok in _TOKEN.findall(label.upper()):
        if tok in _STOP or not any(ch.isdigit() for ch in tok):
            continue
        out.add(tok)
        for part in re.split(r"[-/]", tok):
            if len(part) >= 3 and any(ch.isdigit() for ch in part) and not re.fullmatch(r"20\d\d", part):
                out.add(part)
    return out


def _shares_ref(a: OpenItem, b: OpenItem) -> bool:
    return bool(reference_tokens(a.label) & reference_tokens(b.label))


def _days(a: OpenItem, b: OpenItem) -> int:
    return abs((a.entry_date - b.entry_date).days)


def _subset_summing(target: Decimal, pool: list[OpenItem]) -> list[OpenItem] | None:
    """Smallest subset (2..MAX_GROUP_SIZE items) whose open amounts sum exactly to target."""
    pool = [p for p in pool if p.open_mad <= target]
    tried = 0
    for size in range(2, min(MAX_GROUP_SIZE, len(pool)) + 1):
        for combo in itertools.combinations(pool, size):
            tried += 1
            if tried > MAX_COMBINATIONS:
                return None
            if sum((c.open_mad for c in combo), Decimal(0)) == target:
                return list(combo)
    return None


def propose(items: list[OpenItem], invoice_side: str = "debit") -> list[Candidate]:
    debits = sorted((i for i in items if i.side == "debit" and i.open_mad > 0), key=lambda i: (i.entry_date, str(i.line_id)))
    credits = sorted((i for i in items if i.side == "credit" and i.open_mad > 0), key=lambda i: (i.entry_date, str(i.line_id)))
    used: set[uuid.UUID] = set()
    out: list[Candidate] = []

    def free(xs: list[OpenItem]) -> list[OpenItem]:
        return [x for x in xs if x.line_id not in used]

    # 1. exact: prefer a shared reference, then the nearest date.
    for d in debits:
        if d.line_id in used:
            continue
        same = [c for c in free(credits) if c.open_mad == d.open_mad]
        if not same:
            continue
        best = min(same, key=lambda c: (not _shares_ref(d, c), _days(d, c), str(c.line_id)))
        reasons = ["montant identique"]
        if _shares_ref(d, best):
            reasons.append("référence commune")
        used |= {d.line_id, best.line_id}
        out.append(Candidate("exact", [(d.line_id, "debit", d.open_mad), (best.line_id, "credit", best.open_mad)],
                             d.open_mad, reasons))

    # 2. grouped / split, in both directions.
    for one_side, many_side in (("debit", "credit"), ("credit", "debit")):
        ones = debits if one_side == "debit" else credits
        manys = credits if one_side == "debit" else debits
        for one in ones:
            if one.line_id in used:
                continue
            subset = _subset_summing(one.open_mad, free(manys))
            if not subset:
                continue
            used |= {one.line_id, *(s.line_id for s in subset)}
            kind = "split" if one_side == invoice_side else "grouped"
            allocs = [(one.line_id, one_side, one.open_mad)] + [(s.line_id, many_side, s.open_mad) for s in subset]
            out.append(Candidate(kind, allocs, one.open_mad,
                                 [f"somme exacte de {len(subset)} pièces"]))

    # 3. partial: only with a shared reference, smaller side fully allocated.
    for d in debits:
        if d.line_id in used:
            continue
        for c in free(credits):
            if c.line_id in used or not _shares_ref(d, c) or c.open_mad == d.open_mad:
                continue
            amount = min(c.open_mad, d.open_mad)
            used |= {d.line_id, c.line_id}
            out.append(Candidate("partial", [(d.line_id, "debit", amount), (c.line_id, "credit", amount)], amount,
                                 ["référence commune", "règlement partiel : solde restant ouvert"]))
            break
    return out
