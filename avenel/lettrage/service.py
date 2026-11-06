"""Lettrage service (Phase 6b, ARCHITECTURE.md D.7b).

Open items are the 342x (customers) and 441x (suppliers) lines with a counterparty on
approved or exported proposals. A line's open balance is its amount minus what accepted
lettrage groups allocate from it. Candidates come from the deterministic matcher; an
accountant accepts, rejects or later reverses each group. Balance and over-allocation are
also checked by the database trigger in migration 011.
"""

from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal
from typing import Any

import psycopg

from avenel.lettrage.matcher import OpenItem, propose

ACCOUNT_PREFIX = {"customer": "342", "supplier": "441"}


class LettrageError(ValueError):
    """Business rule refusal (maps to 409)."""


class LettrageNotFound(LookupError):
    pass


def _audit(conn: psycopg.Connection, tenant_id: uuid.UUID, actor_id: str, action: str,
           resource_id: uuid.UUID, data: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
               VALUES (%s, 'user', %s, %s, 'lettrage_group', %s, %s::jsonb)""",
            (tenant_id, actor_id, action, str(resource_id), json.dumps(data, default=str)),
        )


def letter_code_for(n: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, ... (spreadsheet-style)."""
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


_OPEN_ITEMS_SQL = """
SELECT jl.id, jl.account_code, jl.counterparty_id, cp.legal_name, jp.entry_date, jl.due_date,
       jl.label, jp.journal_code, jp.source_document_id,
       CASE WHEN jl.debit_mad > 0 THEN 'debit' ELSE 'credit' END AS side,
       greatest(jl.debit_mad, jl.credit_mad) AS amount_mad,
       coalesce((SELECT sum(a.amount_mad) FROM lettrage_allocations a
                 JOIN lettrage_groups g ON g.id = a.group_id AND g.tenant_id = a.tenant_id
                 WHERE a.tenant_id = jl.tenant_id AND a.journal_line_id = jl.id AND g.status = 'accepted'), 0)
         AS lettered_mad,
       (SELECT array_agg(DISTINCT g.letter_code ORDER BY g.letter_code) FROM lettrage_allocations a
          JOIN lettrage_groups g ON g.id = a.group_id AND g.tenant_id = a.tenant_id
          WHERE a.tenant_id = jl.tenant_id AND a.journal_line_id = jl.id AND g.status = 'accepted') AS letters
FROM journal_lines jl
JOIN journal_proposals jp ON jp.id = jl.journal_proposal_id AND jp.tenant_id = jl.tenant_id
JOIN counterparties cp ON cp.id = jl.counterparty_id AND cp.tenant_id = jl.tenant_id
WHERE jl.tenant_id = %(t)s AND jl.client_entity_id = %(c)s
  AND jp.status IN ('approved','exported')
  AND jl.counterparty_id IS NOT NULL
  AND jl.account_code LIKE %(prefix)s
ORDER BY cp.legal_name, jl.account_code, jp.entry_date, jl.id
"""


def _fetch_lines(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                 account_class: str) -> list[dict[str, Any]]:
    prefix = ACCOUNT_PREFIX[account_class]
    with conn.cursor() as cur:
        cur.execute(_OPEN_ITEMS_SQL, {"t": tenant_id, "c": client_id, "prefix": prefix + "%"})
        cols = [d.name for d in (cur.description or [])]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["open_mad"] = Decimal(r["amount_mad"]) - Decimal(r["lettered_mad"])
        r["letters"] = r["letters"] or []
    return rows


def list_open_items(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                    account_class: str, as_of: datetime.date | None = None,
                    include_settled: bool = False) -> dict[str, Any]:
    as_of = as_of or datetime.date.today()
    rows = _fetch_lines(conn, tenant_id, client_id, account_class)
    balances: dict[tuple[str, str], dict[str, Any]] = {}
    items = []
    for r in rows:
        signed = r["open_mad"] if r["side"] == "debit" else -r["open_mad"]
        key = (str(r["counterparty_id"]), r["account_code"])
        b = balances.setdefault(key, {
            "counterparty_id": str(r["counterparty_id"]), "counterparty_name": r["legal_name"],
            "account_code": r["account_code"], "balance_mad": Decimal(0), "open_count": 0})
        b["balance_mad"] += signed
        if r["open_mad"] > 0:
            b["open_count"] += 1
        if r["open_mad"] == 0 and not include_settled:
            continue
        due = r["due_date"]
        items.append({
            "journal_line_id": str(r["id"]), "account_code": r["account_code"],
            "counterparty_id": str(r["counterparty_id"]), "counterparty_name": r["legal_name"],
            "entry_date": r["entry_date"].isoformat(), "due_date": due.isoformat() if due else None,
            "days_overdue": (as_of - due).days if due and as_of > due and r["open_mad"] > 0 else 0,
            "label": r["label"], "journal_code": r["journal_code"],
            "source_document_id": str(r["source_document_id"]) if r["source_document_id"] else None,
            "side": r["side"], "amount_mad": f"{Decimal(r['amount_mad']):.2f}",
            "lettered_mad": f"{Decimal(r['lettered_mad']):.2f}", "open_mad": f"{r['open_mad']:.2f}",
            "letters": r["letters"],
            "status": "settled" if r["open_mad"] == 0 else ("partial" if Decimal(r["lettered_mad"]) > 0 else "open"),
        })
    return {
        "account_class": account_class, "as_of": as_of.isoformat(), "items": items,
        "balances": [dict(b, balance_mad=f"{b['balance_mad']:.2f}") for b in balances.values()],
    }


def _insert_group(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                  counterparty_id: uuid.UUID, account_code: str, kind: str, total: Decimal,
                  reasons: list[str], proposed_by: str,
                  allocations: list[tuple[uuid.UUID, str, Decimal]]) -> uuid.UUID:
    gid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO lettrage_groups (id, tenant_id, client_entity_id, counterparty_id, account_code,
                   kind, total_mad, reasons, proposed_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (gid, tenant_id, client_id, counterparty_id, account_code, kind, total, json.dumps(reasons), proposed_by),
        )
        for line_id, side, amount in allocations:
            cur.execute(
                """INSERT INTO lettrage_allocations (tenant_id, client_entity_id, group_id, journal_line_id, side, amount_mad)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (tenant_id, client_id, gid, line_id, side, amount),
            )
    return gid


def generate_candidates(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                        actor_id: str) -> list[dict[str, Any]]:
    """Supersedes earlier pending rule candidates of the client and proposes new ones."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE lettrage_groups SET status = 'superseded'
               WHERE tenant_id = %s AND client_entity_id = %s AND status = 'proposed' AND proposed_by = 'rules'""",
            (tenant_id, client_id),
        )
    created: list[uuid.UUID] = []
    for account_class in ACCOUNT_PREFIX:
        rows = _fetch_lines(conn, tenant_id, client_id, account_class)
        buckets: dict[tuple[uuid.UUID, str], list[OpenItem]] = {}
        for r in rows:
            if r["open_mad"] <= 0:
                continue
            buckets.setdefault((r["counterparty_id"], r["account_code"]), []).append(
                OpenItem(r["id"], r["side"], r["open_mad"], r["entry_date"], r["label"]))
        for (cp_id, account_code), items in sorted(buckets.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            invoice_side = "debit" if account_class == "customer" else "credit"
            for cand in propose(items, invoice_side):
                created.append(_insert_group(conn, tenant_id, client_id, cp_id, account_code, cand.kind,
                                             cand.total_mad, cand.reasons, "rules", cand.allocations))
    _audit(conn, tenant_id, actor_id, "lettrage.generated", client_id, {"groups": [str(g) for g in created]})
    return list_groups(conn, tenant_id, client_id, status="proposed")


def create_manual_group(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                        actor_id: str, allocations: list[tuple[uuid.UUID, Decimal]]) -> dict[str, Any]:
    if len(allocations) < 2:
        raise LettrageError("Un lettrage relie au moins deux lignes.")
    ids = [a[0] for a in allocations]
    if len(set(ids)) != len(ids):
        raise LettrageError("Une ligne apparaît deux fois.")
    rows = {r["id"]: r for cls in ACCOUNT_PREFIX for r in _fetch_lines(conn, tenant_id, client_id, cls)}
    allocs: list[tuple[uuid.UUID, str, Decimal]] = []
    keys = set()
    for line_id, amount in allocations:
        r = rows.get(line_id)
        if r is None:
            raise LettrageError("Ligne introuvable ou non approuvée.")
        if amount <= 0 or amount > r["open_mad"]:
            raise LettrageError(f"Montant supérieur au solde ouvert de la ligne ({r['open_mad']:.2f}).")
        keys.add((r["counterparty_id"], r["account_code"]))
        allocs.append((line_id, r["side"], amount))
    if len(keys) != 1:
        raise LettrageError("Toutes les lignes doivent porter le même compte et le même tiers.")
    debit = sum((a[2] for a in allocs if a[1] == "debit"), Decimal(0))
    credit = sum((a[2] for a in allocs if a[1] == "credit"), Decimal(0))
    if debit != credit:
        raise LettrageError(f"Lettrage déséquilibré : débit {debit:.2f}, crédit {credit:.2f}.")
    cp_id, account_code = keys.pop()
    gid = _insert_group(conn, tenant_id, client_id, cp_id, account_code, "manual", debit,
                        ["lettrage manuel"], "human", allocs)
    _audit(conn, tenant_id, actor_id, "lettrage.manual_proposed", gid, {"total_mad": str(debit)})
    return get_group(conn, tenant_id, gid)


def get_group(conn: psycopg.Connection, tenant_id: uuid.UUID, group_id: uuid.UUID) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT g.id, g.client_entity_id, g.counterparty_id, cp.legal_name, g.account_code, g.status, g.kind,
                      g.letter_code, g.total_mad, g.reasons, g.proposed_by, g.decided_at, g.reversed_at,
                      g.reversal_reason, g.created_at
               FROM lettrage_groups g JOIN counterparties cp ON cp.id = g.counterparty_id AND cp.tenant_id = g.tenant_id
               WHERE g.tenant_id = %s AND g.id = %s""",
            (tenant_id, group_id),
        )
        row = cur.fetchone()
        if not row:
            raise LettrageNotFound("Lettrage introuvable.")
        cur.execute(
            """SELECT a.journal_line_id, a.side, a.amount_mad, jl.label, jp.entry_date,
                      greatest(jl.debit_mad, jl.credit_mad)
               FROM lettrage_allocations a
               JOIN journal_lines jl ON jl.id = a.journal_line_id AND jl.tenant_id = a.tenant_id
               JOIN journal_proposals jp ON jp.id = jl.journal_proposal_id AND jp.tenant_id = jl.tenant_id
               WHERE a.tenant_id = %s AND a.group_id = %s ORDER BY a.side DESC, jp.entry_date, a.journal_line_id""",
            (tenant_id, group_id),
        )
        allocs = [{"journal_line_id": str(r[0]), "side": r[1], "amount_mad": f"{Decimal(r[2]):.2f}",
                   "label": r[3], "entry_date": r[4].isoformat(), "line_amount_mad": f"{Decimal(r[5]):.2f}"}
                  for r in cur.fetchall()]
    return {
        "id": str(row[0]), "client_entity_id": str(row[1]), "counterparty_id": str(row[2]),
        "counterparty_name": row[3], "account_code": row[4], "status": row[5], "kind": row[6],
        "letter_code": row[7], "total_mad": f"{Decimal(row[8]):.2f}", "reasons": row[9],
        "proposed_by": row[10], "decided_at": row[11].isoformat() if row[11] else None,
        "reversed_at": row[12].isoformat() if row[12] else None, "reversal_reason": row[13],
        "allocations": allocs,
    }


def list_groups(conn: psycopg.Connection, tenant_id: uuid.UUID, client_id: uuid.UUID,
                status: str | None = None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM lettrage_groups WHERE tenant_id = %s AND client_entity_id = %s
                 AND (%s::text IS NULL OR status = %s) ORDER BY created_at, id""",
            (tenant_id, client_id, status, status),
        )
        ids = [r[0] for r in cur.fetchall()]
    return [get_group(conn, tenant_id, i) for i in ids]


def group_client(conn: psycopg.Connection, tenant_id: uuid.UUID, group_id: uuid.UUID) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("SELECT client_entity_id FROM lettrage_groups WHERE tenant_id = %s AND id = %s", (tenant_id, group_id))
        row = cur.fetchone()
    if not row:
        raise LettrageNotFound("Lettrage introuvable.")
    return uuid.UUID(str(row[0]))


def _db_refusal(err: psycopg.Error) -> LettrageError:
    msg = str(err)
    if "not balanced" in msg:
        return LettrageError("Lettrage déséquilibré.")
    if "more than the open balance" in msg:
        return LettrageError("Une ligne est déjà lettrée pour tout ou partie de ce montant.")
    if "not allowed" in msg:
        return LettrageError("Ce lettrage n'est plus modifiable dans son état actuel.")
    return LettrageError("Lettrage refusé par la base de données.")


def accept_group(conn: psycopg.Connection, tenant_id: uuid.UUID, group_id: uuid.UUID,
                 actor_id: uuid.UUID) -> dict[str, Any]:
    g = get_group(conn, tenant_id, group_id)
    if g["status"] != "proposed":
        raise LettrageError("Ce lettrage n'est plus en attente.")
    with conn.cursor() as cur:
        # One letter sequence per client and account; serialise with a transaction lock.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"lettrage:{tenant_id}:{g['client_entity_id']}:{g['account_code']}",))
        cur.execute(
            """SELECT count(*) FROM lettrage_groups WHERE tenant_id = %s AND client_entity_id = %s
                 AND account_code = %s AND letter_code IS NOT NULL""",
            (tenant_id, g["client_entity_id"], g["account_code"]),
        )
        count_row = cur.fetchone()
        code = letter_code_for(int(count_row[0]) if count_row else 0)
        try:
            with conn.transaction():
                cur.execute(
                    """UPDATE lettrage_groups SET status = 'accepted', letter_code = %s, decided_by = %s, decided_at = now()
                       WHERE tenant_id = %s AND id = %s""",
                    (code, actor_id, tenant_id, group_id),
                )
        except psycopg.errors.CheckViolation as err:
            raise _db_refusal(err) from err
        except psycopg.errors.InsufficientPrivilege as err:
            raise _db_refusal(err) from err
    _audit(conn, tenant_id, str(actor_id), "lettrage.accepted", group_id,
           {"letter_code": code, "total_mad": g["total_mad"]})
    return get_group(conn, tenant_id, group_id)


def reject_group(conn: psycopg.Connection, tenant_id: uuid.UUID, group_id: uuid.UUID,
                 actor_id: uuid.UUID) -> dict[str, Any]:
    g = get_group(conn, tenant_id, group_id)
    if g["status"] != "proposed":
        raise LettrageError("Ce lettrage n'est plus en attente.")
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE lettrage_groups SET status = 'rejected', decided_by = %s, decided_at = now()
               WHERE tenant_id = %s AND id = %s""",
            (actor_id, tenant_id, group_id),
        )
    _audit(conn, tenant_id, str(actor_id), "lettrage.rejected", group_id, {})
    return get_group(conn, tenant_id, group_id)


def reverse_group(conn: psycopg.Connection, tenant_id: uuid.UUID, group_id: uuid.UUID,
                  actor_id: uuid.UUID, reason: str) -> dict[str, Any]:
    if not reason or not reason.strip():
        raise LettrageError("Le motif du délettrage est obligatoire.")
    g = get_group(conn, tenant_id, group_id)
    if g["status"] != "accepted":
        raise LettrageError("Seul un lettrage accepté peut être délettré.")
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE lettrage_groups SET status = 'reversed', reversed_by = %s, reversed_at = now(),
                   reversal_reason = %s
               WHERE tenant_id = %s AND id = %s""",
            (actor_id, reason.strip(), tenant_id, group_id),
        )
    _audit(conn, tenant_id, str(actor_id), "lettrage.reversed", group_id,
           {"letter_code": g["letter_code"], "reason": reason.strip()})
    return get_group(conn, tenant_id, group_id)
