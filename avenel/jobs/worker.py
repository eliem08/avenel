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
from typing import Any

import psycopg

from avenel.documents.scanner import check_intake_health
from avenel.documents.service import QuarantineError, process_uploaded_document
from avenel.extraction.ai_fill import ai_configured, fill_document_in_background
from avenel.jobs.queue import Job, claim_next, enqueue, mark_succeeded, record_failure
from avenel.tenancy.auth import set_rls_context
from avenel.workforce import orchestrator
from avenel.workforce.agents import AGENTS, require

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("avenel.worker")

IDLE_POLL_SECONDS = 5.0

Handler = Callable[[psycopg.Connection, Job], dict[str, Any] | None]


class IntakePausedError(RuntimeError):
    """The malware scanner cannot vouch for files right now; the job is retried with backoff."""


def read_document(conn: psycopg.Connection, job: Job) -> dict[str, Any] | None:
    """Document agent: reads one uploaded document (scan, render, OCR, classify, extract, validate)."""
    require(AGENTS["document"], "document.read")
    already = conn.execute(
        """
        SELECT 1 FROM extractions e
        JOIN document_versions dv ON dv.id = e.document_version_id AND dv.tenant_id = e.tenant_id
        WHERE dv.tenant_id = %s AND dv.document_id = %s LIMIT 1;
        """,
        (job.tenant_id, job.subject_id),
    ).fetchone()
    if already:  # read by an earlier attempt or by the upload request itself
        return None
    # A paused intake (scanner down or signatures stale) is temporary: retry later, do not quarantine.
    # Found on the real stack, 11 Nov 2026: treating it as a quarantine left documents unread for good.
    health = check_intake_health()
    if health.intake_paused:
        raise IntakePausedError(health.banner_message or "intake paused")
    try:
        result = process_uploaded_document(conn=conn, tenant_id=job.tenant_id, document_id=job.subject_id,
                                           defer_ai=True)
        # The AI help for empty fields runs in its own job, so the document is read without waiting for it.
        if result.get("ai_pending") and ai_configured():
            enqueue(conn, job.tenant_id, job.work_request_id, "ai_fill", job.subject_id)
            return {"ai_fill_queued": True}
        return None
    except QuarantineError as exc:
        if exc.threat_name == "SCANNER_UNAVAILABLE":
            # No scan could be done (clamd timed out or refused): temporary, like a paused intake. Raising
            # rolls back the quarantine and its issue, and the job is retried. Real stack, 13 Nov 2026.
            raise IntakePausedError("scanner unavailable during the scan") from exc
        # Malware found: the document is quarantined and its issue recorded. A finished job, not a failure.
        logger.info("job %s: document %s quarantined", job.id, job.subject_id)
        return None


def ai_fill(conn: psycopg.Connection, job: Job) -> dict[str, Any]:
    """Document agent, second part: AI suggestions for the fields reading left empty (marked for review)."""
    require(AGENTS["document"], "document.ai_fill")
    return fill_document_in_background(conn, job.tenant_id, job.subject_id)


HANDLERS: dict[str, Handler] = {
    "read_document": read_document,
    "ai_fill": ai_fill,
    "prepare_proposals": orchestrator.prepare_proposals,
    "reconcile": orchestrator.reconcile,
}


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
                summary = handlers[job.step](conn, job)
                orchestrator.after_step(conn, job, summary)  # hand off to the next agent, same transaction
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


def run_once(db_url: str, handlers: dict[str, Handler] | None = None, steps: list[str] | None = None) -> str | None:
    """Claims and runs at most one job (of `steps`, if given). Returns its outcome, or None when nothing is due."""
    with psycopg.connect(db_url, autocommit=False) as conn:
        job = claim_next(conn, steps=steps)
    if job is None:
        return None
    return run_job(db_url, job, handlers)


def run_worker() -> None:
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel")
    # AVENEL_WORKER_STEPS (comma-separated) limits this worker to some steps, e.g. "ai_fill" for the worker
    # that waits on the AI provider, so reading is never held up by it (migration 017). Empty: every step.
    steps = [s.strip() for s in os.environ.get("AVENEL_WORKER_STEPS", "").split(",") if s.strip()] or None
    logger.info("AVENEL worker started (steps: %s); polling the job queue every %ss when idle.",
                ",".join(steps) if steps else "all", IDLE_POLL_SECONDS)
    try:
        while True:
            try:
                outcome = run_once(db_url, steps=steps)
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
