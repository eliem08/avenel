"""Phase 5 completion: client portal requests respect client scope (Phase 1 exit criterion).

Before: a client user with no scoped company listed every waiting request of the firm, one with
several companies saw only the first, and any user could answer any request by id.
"""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_document_reading_real_pdf import _h, env  # noqa: F401
from tests.api.test_tax_mappings_api import _proposal, mp  # noqa: F401
from tests.helpers import seed_membership, seed_user


def _send_first_issue_to_client(c: TestClient, mp: dict) -> str:  # noqa: F811
    _proposal(c, mp)
    items = c.get(f"/v1/work-requests/{mp['wr']}/issues", headers=_h(mp["sub"], mp["t"])).json()["items"]
    issue = next(i for i in items if i["status"] == "open")
    r = c.post(f"/v1/issues/{issue['id']}:send-to-client", headers=_h(mp["sub"], mp["t"]),
               json={"prompt": "Merci de confirmer la nature de cette dépense."})
    assert r.status_code == 200, r.text
    return issue["id"]


def test_client_user_without_scope_sees_nothing(mp, db_conn: psycopg.Connection):  # noqa: F811
    c = TestClient(app)
    _send_first_issue_to_client(c, mp)
    lone = f"lone-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=lone, email=f"{lone}@c.ma"), mp["t"], "client_user")
    db_conn.commit()
    r = c.get("/v1/portal/requests", headers=_h(lone, mp["t"]))
    assert r.status_code == 200
    assert r.json() == []


def test_scoped_client_user_sees_and_answers_own_request(mp):  # noqa: F811
    c = TestClient(app)
    iid = _send_first_issue_to_client(c, mp)
    listed = c.get("/v1/portal/requests", headers=_h(mp["cu"], mp["t"])).json()
    assert [x["id"] for x in listed] == [iid]
    r = c.post(f"/v1/portal/requests/{iid}:answer", headers=_h(mp["cu"], mp["t"]), json={"response": "Fournitures de bureau."})
    assert r.status_code == 200, r.text


def test_others_cannot_answer(mp, db_conn: psycopg.Connection):  # noqa: F811
    c = TestClient(app)
    iid = _send_first_issue_to_client(c, mp)
    lone = f"lone-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=lone, email=f"{lone}@c.ma"), mp["t"], "client_user")
    db_conn.commit()
    body = {"response": "réponse"}
    assert c.post(f"/v1/portal/requests/{iid}:answer", headers=_h(lone, mp["t"]), json=body).status_code == 404
    assert c.post(f"/v1/portal/requests/{iid}:answer", headers=_h(mp["other"]), json=body).status_code == 404
    assert c.post(f"/v1/portal/requests/{iid}:answer", headers=_h(mp["sub"], mp["t"]), json=body).status_code == 403
