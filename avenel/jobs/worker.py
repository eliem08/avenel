"""Background worker: runs queued jobs with retries (ARCHITECTURE.md C.1, D.1; avenel/jobs/queue.py).

One job at a time per worker process. For each job the worker sets the tenant's RLS context, runs the
handler, and marks the job succeeded in the same transaction as the handler's writes. A failure rolls the
handler's writes back, then records the retry (or the final failure and its issue) in a new transaction.
Runs in a read-only container with a tmpfs scratch directory for OCR and document preparation.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable

import psycopg

from avenel.documents.service import QuarantineError, process_uploaded_document
from avenel.jobs.queue import Job, claim_next, mark_succeeded, record_failure
from avenel.tenancy.auth import set_rls_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("avenel.worker")

IDLE_POLL_SECONDS = 5.0

Handler = Callable[[psycopg.Connection, Job], None]


def read_document(conn: psycopg.Connection, job: Job) -> None:
    """Reads one uploaded document (scan, render, OCR, classify, extract, validate)."""
    already = conn.execute(
        """
        SELECT 1 FROM extractions e
        JOIN document_versions dv ON dv.id = e.document_version_id AND dv.tenant_id = e.tenant_id
        WHERE dv.tenant_id = %s AND dv.document_id = %s LIMIT 1;
        """,
        (job.tenant_id, job.subject_id),
    ).fetchone()
    if already:  # read by an earlier attempt or by the upload request itself
        return
    try:
        process_uploaded_document(conn=conn, tenant_id=job.tenant_id, document_id=job.subject_id)
    except QuarantineError:
        # The document was quarantined and its issue recorded: that is a finished job, not a failure.
        logger.info("job %s: document %s quarantined", job.id, job.subject_id)


HANDLERS: dict[str, Handler] = {"read_document": read_document}


def run_job(db_url: str, job: Job, handlers: dict[str, Handler] | None = None) -> str:
    """Runs one claimed job. Returns "succeeded", "retry" or "failed"."""
    handlers = HANDLERS if handlers is None else handlers
    with psycopg.connect(db_url, autocommit=False) as conn:
        set_rls_context(conn, job.tenant_id)
        error: BaseException | str
        if job.exhausted:
            error = "worker stopped during the last attempt"
        else:
            try:
                handlers[job.step](conn, job)
                mark_succeeded(conn, job)
                conn.commit()
                return "succeeded"
            except Exception as exc:  # noqa: BLE001 - any handler failure becomes a retry or an issue
                conn.rollback()
                error = exc
        set_rls_context(conn, job.tenant_id)
        outcome = record_failure(conn, job, error)
        conn.commit()
        logger.warning("job %s (%s) attempt %s: %s -> %s", job.id, job.step, job.attempts, error, outcome)
        return outcome


def run_once(db_url: str, handlers: dict[str, Handler] | None = None) -> str | None:
    """Claims and runs at most one job. Returns its outcome, or None when nothing is due."""
    with psycopg.connect(db_url, autocommit=False) as conn:
        job = claim_next(conn)
    if job is None:
        return None
    return run_job(db_url, job, handlers)


def run_worker() -> None:
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel")
    logger.info("AVENEL worker started; polling the job queue every %ss when idle.", IDLE_POLL_SECONDS)
    try:
        while True:
            try:
                outcome = run_once(db_url)
            except psycopg.Error as exc:  # database unreachable: wait and try again
                logger.error("queue unavailable: %s", type(exc).__name__)
                outcome = None
            if outcome is None:
                time.sleep(IDLE_POLL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Worker shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    run_worker()
