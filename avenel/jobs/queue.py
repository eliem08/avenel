"""Durable job queue on PostgreSQL (ARCHITECTURE.md D.1; migration 014; docs/plans/b-01-job-queue.md).

Each job is keyed by (work_request_id, step, subject_id, revision). A job gets at most MAX_ATTEMPTS tries,
with exponential backoff and jitter between them; after the last failure it is marked failed and a
blocking INTEGRATION_FAILURE issue is opened for the accountant.
"""

from __future__ import annotations

import json
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import psycopg

MAX_ATTEMPTS = 4  # ARCHITECTURE.md D.1
BACKOFF_BASE_SECONDS = 30.0
STALE_RUNNING_SECONDS = 900  # a job 'running' longer than this belongs to a crashed worker
ERROR_TEXT_LIMIT = 500


@dataclass(frozen=True)
class Job:
    id: uuid.UUID
    tenant_id: uuid.UUID
    work_request_id: uuid.UUID
    step: str
    subject_id: uuid.UUID
    attempts: int
    exhausted: bool = False


def backoff_seconds(attempts: int, rand: Callable[[], float] = random.random) -> float:
    """Delay before the next try: base x 2^(attempts-1), plus up to 100 % jitter."""
    return float(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)) * (1.0 + rand()))


def enqueue(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    step: str,
    subject_id: uuid.UUID,
) -> bool:
    """Queues a job in the caller's transaction. Returns False when one is already queued or running."""
    row = conn.execute(
        """
        INSERT INTO jobs (tenant_id, work_request_id, step, subject_id, revision)
        SELECT %(t)s, %(w)s, %(s)s, %(d)s,
               1 + COALESCE((SELECT max(revision) FROM jobs
                             WHERE tenant_id = %(t)s AND work_request_id = %(w)s
                               AND step = %(s)s AND subject_id = %(d)s), 0)
        ON CONFLICT (tenant_id, step, subject_id) WHERE status IN ('queued','running') DO NOTHING
        RETURNING id;
        """,
        {"t": tenant_id, "w": work_request_id, "s": step, "d": subject_id},
    ).fetchone()
    return row is not None


def claim_next(conn: psycopg.Connection, stale_seconds: int = STALE_RUNNING_SECONDS) -> Job | None:
    """Takes the next due job, across tenants, and commits the claim so other workers skip it."""
    row = conn.execute("SELECT * FROM app.claim_next_job(%s);", (stale_seconds,)).fetchone()
    conn.commit()
    if row is None:
        return None
    return Job(row[0], row[1], row[2], str(row[3]), row[4], int(row[5]), bool(row[6]))


def mark_succeeded(conn: psycopg.Connection, job: Job) -> None:
    """Call inside the handler's transaction: the work and the job state commit together."""
    conn.execute(
        """
        UPDATE jobs SET status = 'succeeded', locked_at = NULL, finished_at = now(), last_error = NULL
        WHERE tenant_id = %s AND id = %s AND status = 'running';
        """,
        (job.tenant_id, job.id),
    )


def record_failure(
    conn: psycopg.Connection,
    job: Job,
    error: BaseException | str,
    rand: Callable[[], float] = random.random,
) -> str:
    """Schedules a retry, or after the last attempt marks the job failed and opens an issue.

    Runs in the caller's transaction (tenant RLS context already set). Returns "retry" or "failed".
    """
    text = (error if isinstance(error, str) else f"{type(error).__name__}: {error}")[:ERROR_TEXT_LIMIT]
    if not job.exhausted and job.attempts < MAX_ATTEMPTS:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'queued', locked_at = NULL, last_error = %s,
                run_after = now() + make_interval(secs => %s)
            WHERE tenant_id = %s AND id = %s AND status = 'running';
            """,
            (text, backoff_seconds(job.attempts, rand), job.tenant_id, job.id),
        )
        return "retry"

    done = conn.execute(
        """
        UPDATE jobs SET status = 'failed', locked_at = NULL, finished_at = now(), last_error = %s
        WHERE tenant_id = %s AND id = %s AND status = 'running'
        RETURNING id;
        """,
        (text, job.tenant_id, job.id),
    ).fetchone()
    if done is None:  # already settled by another worker: do not open a second issue
        return "failed"
    is_document = job.step == "read_document"
    conn.execute(
        """
        INSERT INTO issues (tenant_id, client_entity_id, work_request_id, subject_document_id,
                            code, severity, status, evidence_refs)
        SELECT wr.tenant_id, wr.client_entity_id, wr.id, %s, 'INTEGRATION_FAILURE', 'blocking', 'open', %s
        FROM work_requests wr WHERE wr.tenant_id = %s AND wr.id = %s;
        """,
        (
            job.subject_id if is_document else None,
            json.dumps([{"job_id": str(job.id), "step": job.step, "attempts": job.attempts, "error": text}]),
            job.tenant_id,
            job.work_request_id,
        ),
    )
    if is_document:  # the reading did not happen: the document is not left as "processing"
        conn.execute(
            "UPDATE documents SET status = 'received' WHERE tenant_id = %s AND id = %s AND status = 'processing';",
            (job.tenant_id, job.subject_id),
        )
    return "failed"
