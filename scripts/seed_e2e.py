"""Seed the docker-compose stack for the browser e2e test (idempotent).

Inserts one tenant, the Keycloak test user and its membership, two client
companies, one open period each and one monthly file each. Values come from
scripts/e2e_seed.json. Runs as the migration owner; never used in production.
"""

from __future__ import annotations

import calendar
import datetime
import json
import os
import sys
import uuid
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context

SEED = json.loads((Path(__file__).with_name("e2e_seed.json")).read_text(encoding="utf-8"))


def main() -> None:
    url = os.environ["SEED_DATABASE_URL"]
    t_id = uuid.UUID(SEED["tenant_id"])
    with psycopg.connect(url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE id = %s;", (t_id,))
            if cur.fetchone():
                print(f"seed_e2e: tenant {t_id} already present, nothing to do")
                return
            cur.execute(
                "INSERT INTO tenants (id, legal_name, data_residency_policy, status) VALUES (%s, %s, 'MA_ONLY', 'active');",
                (t_id, SEED["tenant_name"]),
            )
            u_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO users (id, identity_subject, email, full_name, status) VALUES (%s, %s, %s, %s, 'active');",
                (u_id, SEED["user_subject"], SEED["user_email"], "CI Accountant"),
            )
            cur.execute(
                "INSERT INTO memberships (id, user_id, tenant_id, role, status) VALUES (%s, %s, %s, %s, 'active');",
                (uuid.uuid4(), u_id, t_id, SEED["role"]),
            )
            # Client user (Phase 1 completion): sees only the company named in client_user.scoped_to.
            cu = SEED["client_user"]
            cu_id = uuid.uuid4()
            cu_membership = uuid.uuid4()
            cur.execute(
                "INSERT INTO users (id, identity_subject, email, full_name, status) VALUES (%s, %s, %s, %s, 'active');",
                (cu_id, cu["subject"], cu["email"], "CI Client"),
            )
            cur.execute(
                "INSERT INTO memberships (id, user_id, tenant_id, role, status) VALUES (%s, %s, %s, 'client_user', 'active');",
                (cu_membership, cu_id, t_id),
            )
            # Registered professional (Phase 3): approves tax mappings; MFA proof required by the API.
            ex = SEED["expert"]
            ex_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO users (id, identity_subject, email, full_name, status) VALUES (%s, %s, %s, %s, 'active');",
                (ex_id, ex["subject"], ex["email"], ex["name"]),
            )
            cur.execute(
                """INSERT INTO memberships (id, user_id, tenant_id, role, status, professional_title, professional_registration_no)
                   VALUES (%s, %s, %s, 'accountant', 'active', %s, %s);""",
                (uuid.uuid4(), ex_id, t_id, ex["professional_title"], ex["professional_registration_no"]),
            )
        set_rls_context(conn, t_id, u_id)
        for c in SEED["clients"]:
            client = create_client_entity(conn, t_id, c["legal_name"], str(u_id), ice=c["ice"])
            year, month = (int(x) for x in c["period_code"].split("-"))
            starts = datetime.date(year, month, 1)
            ends = datetime.date(year, month, calendar.monthrange(year, month)[1])
            period = open_accounting_period(
                conn, t_id, client.id, str(u_id), c["period_code"], starts, ends, datetime.date(year, 12, 31)
            )
            period_id = period["id"] if isinstance(period, dict) else period.id
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO work_requests (tenant_id, client_entity_id, accounting_period_id, service_code, status, requested_by)
                       VALUES (%s, %s, %s, 'monthly_bookkeeping', %s, %s);""",
                    (t_id, client.id, period_id, c["status"], u_id),
                )
                if c["legal_name"] == cu["scoped_to"]:
                    cur.execute(
                        "INSERT INTO membership_client_scopes (tenant_id, membership_id, client_entity_id) VALUES (%s, %s, %s);",
                        (t_id, cu_membership, client.id),
                    )
        conn.commit()
    print(f"seed_e2e: seeded tenant {t_id} with {len(SEED['clients'])} monthly files")


if __name__ == "__main__":
    main()
