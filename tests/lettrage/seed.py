"""Seeds approved journal proposals with 342x/441x lines for lettrage tests."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import psycopg

from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user

ACCOUNTS = {"3421": "Clients", "4411": "Fournisseurs", "7111": "Ventes", "6111": "Achats",
            "5141": "Banque", "34552": "TVA récupérable", "4455": "TVA facturée"}


class Ledger:
    def __init__(self, conn: psycopg.Connection, role: str = "accountant") -> None:
        self.conn = conn
        self.tenant_id = seed_tenant(conn, "Cabinet Lettrage Test")
        sub = f"lettrage-{uuid.uuid4()}"
        self.sub = sub
        self.user_id = seed_user(conn, identity_subject=sub, email=f"{sub}@avenel.ma")
        self.membership_id = seed_membership(conn, self.user_id, self.tenant_id, role)
        set_rls_context(conn, self.tenant_id, self.user_id)
        self.client_id = create_client_entity(conn, self.tenant_id, "Atlas Lettrage SARL", actor_id=str(self.user_id)).id
        self.accounts: dict[str, uuid.UUID] = {}
        with conn.cursor() as cur:
            for code, label in ACCOUNTS.items():
                aid = uuid.uuid4()
                cur.execute("INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label) VALUES (%s,%s,%s,%s,%s)",
                            (aid, self.tenant_id, self.client_id, code, label))
                self.accounts[code] = aid
        period = open_accounting_period(conn, self.tenant_id, self.client_id, actor_id=str(self.user_id),
                                        period_code="2026-03", starts_on=datetime.date(2026, 3, 1),
                                        ends_on=datetime.date(2026, 3, 31), fiscal_year_end=datetime.date(2026, 12, 31))
        self.work_request_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
                           VALUES (%s,%s,%s,%s,'monthly_bookkeeping','intake')""",
                        (self.work_request_id, self.tenant_id, self.client_id, period["id"]))
        self._rev = 0

    def counterparty(self, name: str, kind: str) -> uuid.UUID:
        cp = uuid.uuid4()
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO counterparties (id, tenant_id, client_entity_id, kind, legal_name) VALUES (%s,%s,%s,%s,%s)",
                        (cp, self.tenant_id, self.client_id, kind, name))
        return cp

    def entry(self, journal: str, day: int, label: str, lines: list[tuple[str, str, str, uuid.UUID | None]],
              status: str = "approved", due: datetime.date | None = None) -> list[uuid.UUID]:
        """lines: (account_code, 'D'|'C', amount, counterparty_id). Returns line ids in order."""
        self._rev += 1
        pid = uuid.uuid4()
        ids = []
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision,
                             journal_code, entry_date, label, proposed_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'rules')""",
                        (pid, self.tenant_id, self.client_id, self.work_request_id, self._rev, journal,
                         datetime.date(2026, 3, day), label))
            for n, (code, dc, amount, cp) in enumerate(lines, start=1):
                lid = uuid.uuid4()
                amt = Decimal(amount)
                d, c = (amt, Decimal(0)) if dc == "D" else (Decimal(0), amt)
                cur.execute("""INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no,
                                 account_id, account_code, counterparty_id, label, currency, debit_tx, credit_tx,
                                 debit_mad, credit_mad, due_date)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'MAD',%s,%s,%s,%s,%s)""",
                            (lid, self.tenant_id, self.client_id, pid, n, self.accounts[code], code, cp, label,
                             d, c, d, c, due if cp else None))
                ids.append(lid)
            if status != "proposed":
                cur.execute("UPDATE journal_proposals SET status = %s WHERE id = %s", (status, pid))
        return ids

    def sale(self, cp: uuid.UUID, day: int, ref: str, ttc: str, status: str = "approved",
             due: datetime.date | None = None) -> uuid.UUID:
        ttc_d = Decimal(ttc)
        ht = (ttc_d / Decimal("1.2")).quantize(Decimal("0.01"))
        return self.entry("VT", day, f"Facture {ref}", [("3421", "D", ttc, cp), ("7111", "C", str(ht), None),
                                                         ("4455", "C", str(ttc_d - ht), None)], status, due)[0]

    def receipt(self, cp: uuid.UUID, day: int, label: str, amount: str) -> uuid.UUID:
        return self.entry("BQ", day, label, [("5141", "D", amount, None), ("3421", "C", amount, cp)])[1]

    def credit_note(self, cp: uuid.UUID, day: int, ref: str, ttc: str) -> uuid.UUID:
        ttc_d = Decimal(ttc)
        ht = (ttc_d / Decimal("1.2")).quantize(Decimal("0.01"))
        return self.entry("VT", day, f"Avoir {ref}", [("7111", "D", str(ht), None), ("4455", "D", str(ttc_d - ht), None),
                                                       ("3421", "C", ttc, cp)])[2]

    def purchase(self, cp: uuid.UUID, day: int, ref: str, ttc: str) -> uuid.UUID:
        ttc_d = Decimal(ttc)
        ht = (ttc_d / Decimal("1.2")).quantize(Decimal("0.01"))
        return self.entry("HA", day, f"Facture {ref}", [("6111", "D", str(ht), None), ("34552", "D", str(ttc_d - ht), None),
                                                         ("4411", "C", ttc, cp)])[2]

    def payment(self, cp: uuid.UUID, day: int, label: str, amount: str) -> uuid.UUID:
        return self.entry("BQ", day, label, [("4411", "D", amount, cp), ("5141", "C", amount, None)])[0]
