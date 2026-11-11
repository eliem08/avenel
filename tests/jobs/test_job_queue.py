"""Durable job queue and worker (migration 014, avenel/jobs; ARCHITECTURE.md D.1).

Real PostgreSQL. No provider, no OCR: handlers are small functions defined here.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.jobs.queue import (
    BACKOFF_BASE_SECONDS,
    MAX_ATTEMPTS,
    Job,
    backoff_seconds,
    claim_next,
    enqueue,
)
from avenel.jobs.worker import run_once
from avenel.tenancy.auth import set_rls_context
from tests.api.test_document_reading_real_pdf import (
    _pdf,
    _upload,
    env,  # noqa: F401 - fixture: tenant, client, period, file
)

STEP = "read_document"


def _queue(db_conn: psycopg.Connection, env: dict, subject: uuid.UUID | None = None) -> uuid.UUID:  # noqa: F811
    # A job's subject is a real document of the monthly file (the issue raised on failure points to it).
    subject = subject or uuid.UUID(_upload(TestClient(app), env, _pdf()))
    assert enqueue(db_conn, env["t"], uuid.UUID(str(env["wr"])), STEP, subject) is True
    db_conn.commit()
    return subject


def _job(db_conn: psycopg.Connection, subject: uuid.UUID) -> tuple:
    db_conn.rollback()
    row = db_conn.execute(
        "SELECT status, attempts, last_error, run_after > now() FROM jobs WHERE subject_id = %s ORDER BY revision DESC",
        (subject,),
    ).fetchone()
    assert row is not None
    return tuple(row)


def _make_due(db_conn: psycopg.Connection, subject: uuid.UUID) -> None:
    db_conn.rollback()
    db_conn.execute("UPDATE jobs SET run_after = now() WHERE subject_id = %s AND status = 'queued'", (subject,))
    db_conn.commit()


@pytest.fixture(autouse=True)
def _no_other_jobs(db_conn: psycopg.Connection):
    """Each test starts with nothing due, so 'the next job' is the one it queued."""
    db_conn.execute("UPDATE jobs SET status = 'failed', locked_at = NULL, finished_at = now() "
                    "WHERE status IN ('queued','running')")
    db_conn.commit()


def test_backoff_doubles_and_adds_jitter():
    assert backoff_seconds(1, rand=lambda: 0.0) == BACKOFF_BASE_SECONDS
    assert backoff_seconds(2, rand=lambda: 0.0) == BACKOFF_BASE_SECONDS * 2
    assert backoff_seconds(3, rand=lambda: 0.0) == BACKOFF_BASE_SECONDS * 4
    assert backoff_seconds(1, rand=lambda: 0.5) == BACKOFF_BASE_SECONDS * 1.5


def test_enqueue_is_idempotent_while_a_job_is_active(db_conn, env):  # noqa: F811
    subject = _queue(db_conn, env)
    assert enqueue(db_conn, env["t"], uuid.UUID(str(env["wr"])), STEP, subject) is False
    db_conn.commit()
    assert db_conn.execute("SELECT count(*) FROM jobs WHERE subject_id = %s", (subject,)).fetchone() == (1,)


def test_a_job_is_given_to_one_worker_only(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)
    with psycopg.connect(postgres_url) as w1, psycopg.connect(postgres_url) as w2:
        first, second = claim_next(w1), claim_next(w2)
    assert first is not None and first.subject_id == subject and first.attempts == 1
    assert second is None
    assert _job(db_conn, subject)[0] == "running"


def test_success_commits_the_work_and_the_job_together(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)

    def handler(conn: psycopg.Connection, job: Job) -> None:
        conn.execute("UPDATE work_requests SET due_at = '2030-01-01' WHERE tenant_id = %s AND id = %s",
                     (job.tenant_id, job.work_request_id))

    assert run_once(postgres_url, {STEP: handler}) == "succeeded"
    assert _job(db_conn, subject)[:2] == ("succeeded", 1)
    assert db_conn.execute("SELECT due_at::date::text FROM work_requests WHERE id = %s", (env["wr"],)).fetchone() == (
        "2030-01-01",
    )
    assert run_once(postgres_url, {STEP: handler}) is None  # nothing left to do


def test_failure_rolls_back_the_work_and_schedules_a_retry(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)

    def handler(conn: psycopg.Connection, job: Job) -> None:
        conn.execute("UPDATE work_requests SET due_at = '2031-01-01' WHERE tenant_id = %s AND id = %s",
                     (job.tenant_id, job.work_request_id))
        raise RuntimeError("moteur de lecture indisponible")

    assert run_once(postgres_url, {STEP: handler}) == "retry"
    status, attempts, error, in_future = _job(db_conn, subject)
    assert (status, attempts, in_future) == ("queued", 1, True)
    assert "RuntimeError" in error
    assert db_conn.execute("SELECT due_at::date::text FROM work_requests WHERE id = %s", (env["wr"],)).fetchone() != (
        "2031-01-01",
    )
    assert run_once(postgres_url, {STEP: handler}) is None  # not due before its backoff has passed


def test_after_the_last_attempt_the_job_fails_and_one_blocking_issue_is_opened(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)

    def handler(conn: psycopg.Connection, job: Job) -> None:
        raise RuntimeError("toujours en panne")

    outcomes = []
    for _ in range(MAX_ATTEMPTS):
        _make_due(db_conn, subject)
        outcomes.append(run_once(postgres_url, {STEP: handler}))
    assert outcomes == ["retry"] * (MAX_ATTEMPTS - 1) + ["failed"]
    assert _job(db_conn, subject)[:2] == ("failed", MAX_ATTEMPTS)
    issues = db_conn.execute(
        "SELECT code, severity, status, evidence_refs->0->>'step' FROM issues WHERE work_request_id = %s", (env["wr"],)
    ).fetchall()
    assert issues == [("INTEGRATION_FAILURE", "blocking", "open", STEP)]
    assert run_once(postgres_url, {STEP: handler}) is None  # a failed job is never run again


def test_a_new_job_can_be_queued_after_a_failed_one_with_the_next_revision(db_conn, env):  # noqa: F811
    subject = _queue(db_conn, env)
    db_conn.execute("UPDATE jobs SET status = 'failed', finished_at = now() WHERE subject_id = %s", (subject,))
    db_conn.commit()
    assert enqueue(db_conn, env["t"], uuid.UUID(str(env["wr"])), STEP, subject) is True
    db_conn.commit()
    assert db_conn.execute("SELECT array_agg(revision ORDER BY revision) FROM jobs WHERE subject_id = %s",
                           (subject,)).fetchone() == ([1, 2],)


def test_a_job_left_running_by_a_crashed_worker_is_taken_again(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)
    with psycopg.connect(postgres_url) as w:
        assert claim_next(w) is not None  # this worker "crashes": it never finishes the job
    with psycopg.connect(postgres_url) as w:
        assert claim_next(w) is None  # still inside the stale delay
        again = claim_next(w, stale_seconds=0)
    assert again is not None and again.subject_id == subject and again.attempts == 2 and not again.exhausted


def test_a_crash_during_the_last_attempt_ends_in_failure_not_a_fifth_try(db_conn, env, postgres_url):  # noqa: F811
    subject = _queue(db_conn, env)
    db_conn.execute("UPDATE jobs SET status = 'running', locked_at = now() - interval '1 day', attempts = %s "
                    "WHERE subject_id = %s", (MAX_ATTEMPTS, subject))
    db_conn.commit()
    ran = []
    assert run_once(postgres_url, {STEP: lambda conn, job: ran.append(job)}) == "failed"
    assert ran == []
    assert _job(db_conn, subject)[:2] == ("failed", MAX_ATTEMPTS)


def test_attempts_cannot_exceed_the_maximum_in_the_database(db_conn, env):  # noqa: F811
    subject = _queue(db_conn, env)
    with pytest.raises(psycopg.errors.CheckViolation):
        db_conn.execute("UPDATE jobs SET attempts = %s WHERE subject_id = %s", (MAX_ATTEMPTS + 1, subject))
    db_conn.rollback()


def test_app_role_sees_only_its_tenants_jobs(db_conn, app_conn, env):  # noqa: F811
    subject = _queue(db_conn, env)
    set_rls_context(app_conn, uuid.uuid4())  # another tenant
    assert app_conn.execute("SELECT count(*) FROM jobs WHERE subject_id = %s", (subject,)).fetchone() == (0,)
    with pytest.raises(psycopg.Error):  # and cannot queue a job for a tenant it is not acting for
        enqueue(app_conn, env["t"], uuid.UUID(str(env["wr"])), STEP, subject)
    app_conn.rollback()
    set_rls_context(app_conn, env["t"])
    assert app_conn.execute("SELECT count(*) FROM jobs WHERE subject_id = %s", (subject,)).fetchone() == (1,)
    app_conn.rollback()
