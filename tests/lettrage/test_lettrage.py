"""Phase 6b lettrage: golden cases and database invariants (ARCHITECTURE.md D.7b).

Exit criteria covered here:
- an invoice paid in two instalments is lettered with no open balance left;
- one payment settling three invoices is proposed as a single balanced group;
- a credit note letters against its invoice;
- a partial payment leaves the exact open balance;
- no line can be allocated beyond its amount, an unbalanced group cannot be accepted,
  groups and allocations are never deleted, only lines of approved proposals are lettered.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import psycopg
import pytest

from avenel.lettrage.matcher import OpenItem, propose, reference_tokens
from avenel.lettrage.service import (
    LettrageError,
    accept_group,
    create_manual_group,
    generate_candidates,
    letter_code_for,
    list_open_items,
    reject_group,
    reverse_group,
)
from tests.lettrage.seed import Ledger


@pytest.fixture
def ledger(db_conn: psycopg.Connection) -> Ledger:
    return Ledger(db_conn)


def _items(ledger: Ledger, cls: str = "customer", **kw) -> dict:
    return list_open_items(ledger.conn, ledger.tenant_id, ledger.client_id, cls,
                           as_of=datetime.date(2026, 4, 30), **kw)


def _open(ledger: Ledger, line_id: uuid.UUID, cls: str = "customer") -> Decimal:
    for it in _items(ledger, cls, include_settled=True)["items"]:
        if it["journal_line_id"] == str(line_id):
            return Decimal(it["open_mad"])
    raise AssertionError("line not listed")


# --- pure matcher -------------------------------------------------------------------------

def test_reference_tokens():
    assert "FAC-2026-0412" in reference_tokens("VIR CLIENT ATLAS FAC-2026-0412")
    assert "0412" in reference_tokens("Facture FAC-2026-0412")
    assert reference_tokens("VIREMENT RECU") == set()


def test_letter_codes():
    assert [letter_code_for(n) for n in (0, 1, 25, 26, 27, 701, 702)] == ["A", "B", "Z", "AA", "AB", "ZZ", "AAA"]


def test_matcher_uses_no_tolerance():
    d = OpenItem(uuid.uuid4(), "debit", Decimal("1200.00"), datetime.date(2026, 3, 1), "Facture F1")
    c = OpenItem(uuid.uuid4(), "credit", Decimal("1199.99"), datetime.date(2026, 3, 5), "VIR")
    assert propose([d, c]) == []


def test_matcher_groups_always_balance():
    import random
    rnd = random.Random(42)
    for _ in range(200):
        items = [OpenItem(uuid.uuid4(), rnd.choice(["debit", "credit"]), Decimal(rnd.choice([100, 200, 300, 500, 600])),
                          datetime.date(2026, 3, rnd.randint(1, 28)), f"F-{rnd.randint(100, 105)}") for _ in range(8)]
        seen: set = set()
        for cand in propose(items):
            deb = sum(a[2] for a in cand.allocations if a[1] == "debit")
            cre = sum(a[2] for a in cand.allocations if a[1] == "credit")
            assert deb == cre == cand.total_mad
            ids = [a[0] for a in cand.allocations]
            assert not (seen & set(ids))
            seen |= set(ids)
            by_id = {i.line_id: i for i in items}
            assert all(a[2] <= by_id[a[0]].open_mad for a in cand.allocations)


# --- golden cases on the database ---------------------------------------------------------

def test_invoice_paid_in_two_instalments(ledger: Ledger):
    cp = ledger.counterparty("Client Souss", "customer")
    inv = ledger.sale(cp, 2, "FAC-2026-0101", "12000.00")
    r1 = ledger.receipt(cp, 10, "VIR SOUSS FAC-2026-0101 ACOMPTE", "5000.00")
    r2 = ledger.receipt(cp, 25, "VIR SOUSS SOLDE", "7000.00")
    groups = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(groups) == 1 and groups[0]["kind"] == "split"
    assert {a["journal_line_id"] for a in groups[0]["allocations"]} == {str(inv), str(r1), str(r2)}
    acc = accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(groups[0]["id"]), ledger.user_id)
    assert acc["status"] == "accepted" and acc["letter_code"] == "A"
    assert _open(ledger, inv) == 0 and _items(ledger)["items"] == []
    bal = _items(ledger)["balances"]
    assert bal == [{"counterparty_id": str(cp), "counterparty_name": "Client Souss", "account_code": "3421",
                    "balance_mad": "0.00", "open_count": 0}]


def test_one_payment_settles_three_invoices(ledger: Ledger):
    cp = ledger.counterparty("Fournisseur Atlas", "supplier")
    invs = [ledger.purchase(cp, d, f"A-{d}", amt) for d, amt in ((1, "1200.00"), (3, "2400.00"), (5, "600.00"))]
    pay = ledger.payment(cp, 20, "VIR ATLAS 3 FACTURES", "4200.00")
    groups = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(groups) == 1 and groups[0]["kind"] == "grouped" and groups[0]["total_mad"] == "4200.00"
    assert {a["journal_line_id"] for a in groups[0]["allocations"]} == {str(pay), *map(str, invs)}
    accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(groups[0]["id"]), ledger.user_id)
    assert _items(ledger, "supplier")["items"] == []


def test_credit_note_letters_against_invoice(ledger: Ledger):
    cp = ledger.counterparty("Client Rif", "customer")
    inv = ledger.sale(cp, 4, "FAC-2026-0200", "3600.00")
    cn = ledger.credit_note(cp, 9, "AV-2026-0200", "3600.00")
    groups = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(groups) == 1 and groups[0]["kind"] == "exact"
    assert {a["journal_line_id"] for a in groups[0]["allocations"]} == {str(inv), str(cn)}


def test_partial_payment_leaves_exact_open_balance(ledger: Ledger):
    cp = ledger.counterparty("Client Draa", "customer")
    inv = ledger.sale(cp, 3, "FAC-2026-0300", "10000.00", due=datetime.date(2026, 4, 2))
    rec = ledger.receipt(cp, 15, "VIR DRAA FAC-2026-0300", "4000.00")
    groups = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(groups) == 1 and groups[0]["kind"] == "partial"
    accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(groups[0]["id"]), ledger.user_id)
    assert _open(ledger, inv) == Decimal("6000.00") and _open(ledger, rec) == 0
    items = _items(ledger)["items"]
    assert len(items) == 1 and items[0]["status"] == "partial" and items[0]["letters"] == ["A"]
    assert items[0]["days_overdue"] == 28
    assert _items(ledger)["balances"][0]["balance_mad"] == "6000.00"
    # The remaining 6000 can be lettered later by a second receipt.
    ledger.receipt(cp, 28, "VIR DRAA SOLDE", "6000.00")
    g2 = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(g2) == 1 and g2[0]["kind"] == "exact"
    assert accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(g2[0]["id"]), ledger.user_id)["letter_code"] == "B"
    assert _open(ledger, inv) == 0


def test_unapproved_proposals_are_not_open_items(ledger: Ledger):
    cp = ledger.counterparty("Client Proposé", "customer")
    ledger.sale(cp, 3, "FAC-X1", "1200.00", status="proposed")
    ledger.receipt(cp, 9, "VIR X1", "1200.00")
    assert [i["journal_code"] for i in _items(ledger)["items"]] == ["BQ"]
    assert generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id)) == []


def test_regenerate_supersedes_pending_candidates(ledger: Ledger):
    cp = ledger.counterparty("Client Regen", "customer")
    ledger.sale(cp, 3, "FAC-R1", "1200.00")
    ledger.receipt(cp, 9, "VIR R1", "1200.00")
    first = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    second = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))
    assert len(first) == len(second) == 1 and first[0]["id"] != second[0]["id"]
    with pytest.raises(LettrageError):
        accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(first[0]["id"]), ledger.user_id)


def test_reversal_reopens_and_keeps_history(ledger: Ledger):
    cp = ledger.counterparty("Client Rev", "customer")
    inv = ledger.sale(cp, 3, "FAC-V1", "2400.00")
    ledger.receipt(cp, 9, "VIR V1", "2400.00")
    g = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))[0]
    accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(g["id"]), ledger.user_id)
    with pytest.raises(LettrageError):
        reverse_group(ledger.conn, ledger.tenant_id, uuid.UUID(g["id"]), ledger.user_id, "  ")
    rev = reverse_group(ledger.conn, ledger.tenant_id, uuid.UUID(g["id"]), ledger.user_id, "Encaissement affecté au mauvais client")
    assert rev["status"] == "reversed" and rev["letter_code"] == "A"
    assert _open(ledger, inv) == Decimal("2400.00")
    # The letter A is never reused.
    g2 = generate_candidates(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id))[0]
    assert accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(g2["id"]), ledger.user_id)["letter_code"] == "B"
    with ledger.conn.cursor() as cur:
        cur.execute("SELECT action FROM audit_events WHERE tenant_id = %s AND resource_type = 'lettrage_group' ORDER BY id",
                    (ledger.tenant_id,))
        actions = [r[0] for r in cur.fetchall()]
    assert actions.count("lettrage.accepted") == 2 and "lettrage.reversed" in actions


def test_manual_group_must_balance_and_match_one_counterparty(ledger: Ledger):
    a = ledger.counterparty("Client A", "customer")
    b = ledger.counterparty("Client B", "customer")
    inv = ledger.sale(a, 3, "FAC-M1", "1000.00")
    rec_a = ledger.receipt(a, 9, "VIR divers", "999.00")
    rec_b = ledger.receipt(b, 9, "VIR divers", "1000.00")
    with pytest.raises(LettrageError, match="déséquilibré"):
        create_manual_group(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id),
                            [(inv, Decimal("1000.00")), (rec_a, Decimal("999.00"))])
    with pytest.raises(LettrageError, match="même compte et le même tiers"):
        create_manual_group(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id),
                            [(inv, Decimal("1000.00")), (rec_b, Decimal("1000.00"))])
    with pytest.raises(LettrageError, match="solde ouvert"):
        create_manual_group(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id),
                            [(inv, Decimal("1000.00")), (rec_a, Decimal("1000.00"))])
    g = create_manual_group(ledger.conn, ledger.tenant_id, ledger.client_id, str(ledger.user_id),
                            [(inv, Decimal("999.00")), (rec_a, Decimal("999.00"))])
    assert g["kind"] == "manual" and g["proposed_by"] == "human"
    accept_group(ledger.conn, ledger.tenant_id, uuid.UUID(g["id"]), ledger.user_id)
    assert _open(ledger, inv) == Decimal("1.00")


# --- database invariants (the trigger, not only the service) -------------------------------

def _raw_group(ledger: Ledger, cp: uuid.UUID, total: str, allocs: list[tuple[uuid.UUID, str, str]]) -> uuid.UUID:
    gid = uuid.uuid4()
    with ledger.conn.cursor() as cur:
        cur.execute("""INSERT INTO lettrage_groups (id, tenant_id, client_entity_id, counterparty_id, account_code, kind,
                         total_mad, proposed_by) VALUES (%s,%s,%s,%s,'3421','manual',%s,'human')""",
                    (gid, ledger.tenant_id, ledger.client_id, cp, total))
        for line, side, amt in allocs:
            cur.execute("""INSERT INTO lettrage_allocations (tenant_id, client_entity_id, group_id, journal_line_id, side, amount_mad)
                           VALUES (%s,%s,%s,%s,%s,%s)""", (ledger.tenant_id, ledger.client_id, gid, line, side, amt))
    return gid


def _db_accept(ledger: Ledger, gid: uuid.UUID, code: str) -> None:
    with ledger.conn.cursor() as cur:
        cur.execute("""UPDATE lettrage_groups SET status='accepted', letter_code=%s, decided_at=now()
                       WHERE id=%s""", (code, gid))


def test_db_refuses_unbalanced_group(ledger: Ledger):
    cp = ledger.counterparty("Client DB1", "customer")
    inv = ledger.sale(cp, 3, "F1", "1000.00")
    rec = ledger.receipt(cp, 4, "R1", "900.00")
    gid = _raw_group(ledger, cp, "1000.00", [(inv, "debit", "1000.00"), (rec, "credit", "900.00")])
    with pytest.raises(psycopg.errors.CheckViolation, match="not balanced"):
        _db_accept(ledger, gid, "A")


def test_db_refuses_over_allocation(ledger: Ledger):
    cp = ledger.counterparty("Client DB2", "customer")
    inv = ledger.sale(cp, 3, "F2", "1000.00")
    r1 = ledger.receipt(cp, 4, "R1", "1000.00")
    r2 = ledger.receipt(cp, 5, "R2", "1000.00")
    g1 = _raw_group(ledger, cp, "1000.00", [(inv, "debit", "1000.00"), (r1, "credit", "1000.00")])
    _db_accept(ledger, g1, "A")
    g2 = _raw_group(ledger, cp, "1000.00", [(inv, "debit", "1000.00"), (r2, "credit", "1000.00")])
    with pytest.raises(psycopg.errors.CheckViolation, match="open balance"):
        _db_accept(ledger, g2, "B")


def test_db_refuses_unapproved_line(ledger: Ledger):
    cp = ledger.counterparty("Client DB3", "customer")
    inv = ledger.sale(cp, 3, "F3", "1000.00", status="proposed")
    rec = ledger.receipt(cp, 4, "R3", "1000.00")
    gid = _raw_group(ledger, cp, "1000.00", [(inv, "debit", "1000.00"), (rec, "credit", "1000.00")])
    with pytest.raises(psycopg.errors.CheckViolation):
        _db_accept(ledger, gid, "A")


def test_db_refuses_illegal_transitions_and_deletes(ledger: Ledger):
    cp = ledger.counterparty("Client DB4", "customer")
    inv = ledger.sale(cp, 3, "F4", "1000.00")
    rec = ledger.receipt(cp, 4, "R4", "1000.00")
    gid = _raw_group(ledger, cp, "1000.00", [(inv, "debit", "1000.00"), (rec, "credit", "1000.00")])
    reject_group(ledger.conn, ledger.tenant_id, gid, ledger.user_id)
    with ledger.conn.cursor() as cur:
        cur.execute("SAVEPOINT s")
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="not allowed"):
            cur.execute("UPDATE lettrage_groups SET status='accepted', letter_code='A' WHERE id=%s", (gid,))
        cur.execute("ROLLBACK TO SAVEPOINT s")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM lettrage_groups WHERE id=%s", (gid,))
        cur.execute("ROLLBACK TO SAVEPOINT s")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM lettrage_allocations WHERE group_id=%s", (gid,))
        cur.execute("ROLLBACK TO SAVEPOINT s")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE lettrage_allocations SET amount_mad = 1 WHERE group_id=%s", (gid,))


def test_app_role_has_no_delete_on_lettrage(ledger: Ledger):
    with ledger.conn.cursor() as cur:
        cur.execute("""SELECT table_name, privilege_type FROM information_schema.role_table_grants
                       WHERE grantee = 'avenel_app' AND table_name IN ('lettrage_groups','lettrage_allocations')""")
        grants = {(r[0], r[1]) for r in cur.fetchall()}
    assert ("lettrage_groups", "DELETE") not in grants and ("lettrage_allocations", "DELETE") not in grants
    assert ("lettrage_allocations", "UPDATE") not in grants


def test_tolerance_is_an_expert_value_not_invented():
    from avenel.jurisdiction.loader import get_jurisdiction_pack
    rule = get_jurisdiction_pack().get_rule("lettrage.tolerance_mad")
    assert rule is not None and rule["value"] is None and rule["status"] == "needs_expert"
