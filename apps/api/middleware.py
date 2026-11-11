"""Idempotency middleware enforcing required Idempotency-Key on mutating HTTP methods.

Enforces:
- Required Idempotency-Key on POST, PUT, PATCH, DELETE (returns 400 if missing)
- Replay, body mismatch (422) and in-flight conflict (409) are decided per tenant, after
  authentication, from the idempotency_keys table (apps/api/idempotency.py, ADR-003)
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import Any

import psycopg
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from apps.api.idempotency import MUTATING_METHODS, PgIdempotencyStore, abandon, finish
from avenel.infrastructure.rate_limiter import PostgresRateLimiter


def get_idempotency_store() -> PgIdempotencyStore:
    return PgIdempotencyStore(os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel"))


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Requires the key, hashes the request, and records the answer once the handler is done.

    The key itself is claimed after authentication (apps/api/deps.py), per tenant, in PostgreSQL.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)
        if request.url.path in ("/openapi.json", "/docs", "/redoc"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or not idempotency_key.strip():
            return JSONResponse(
                status_code=400,
                media_type="application/problem+json",
                content={
                    "type": "https://avenel.ma/errors/idempotency-key-missing",
                    "title": "Missing Idempotency-Key Header",
                    "status": 400,
                    "detail": "L'en-tête Idempotency-Key est obligatoire pour toute requête modifiant des données.",
                },
            )

        body_bytes = await request.body()
        request.state.idempotency_key = idempotency_key.strip()
        request.state.idempotency_sha256 = hashlib.sha256(body_bytes).hexdigest()

        store = get_idempotency_store()
        try:
            response = await call_next(request)
            full_body = b"".join([chunk async for chunk in response.body_iterator])
        except Exception:
            abandon(store, request)
            raise
        finish(store, request, response.status_code, full_body)
        return Response(
            content=full_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


class RateLimitStore:
    """Shared rate limit store backed by PostgreSQL table `rate_limit_buckets` with in-memory fallback."""

    def __init__(self, db_url: str | None = None) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}
        self._db_url = db_url or os.environ.get("DATABASE_URL")
        self._pg_limiter = PostgresRateLimiter(self._db_url)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        """Checks if request is within limit across all workers using PostgreSQL shared store."""
        if self._db_url:
            try:
                with psycopg.connect(self._db_url, autocommit=True) as conn:
                    allowed, remaining = self._pg_limiter.acquire(conn, key, rate_per_minute=max_requests)
                    if not allowed:
                        return False, 0, window_seconds
                    return True, remaining, 0
            except (psycopg.Error, OSError):
                # Fallback to local in-memory on DB connection failure
                pass

        now = time.time()
        window_start = now - window_seconds
        with self._lock:
            timestamps = self._hits.setdefault(key, [])
            # Prune old timestamps
            self._hits[key] = [t for t in timestamps if t > window_start]
            count = len(self._hits[key])

            if count >= max_requests:
                earliest = self._hits[key][0]
                retry_after = max(1, int(earliest + window_seconds - now))
                return False, 0, retry_after

            self._hits[key].append(now)
            remaining = max_requests - (count + 1)
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
        if self._db_url:
            try:
                with psycopg.connect(self._db_url, autocommit=True) as conn, conn.cursor() as cur:
                    cur.execute("TRUNCATE rate_limit_buckets;")
            except (psycopg.Error, OSError):
                pass


_GLOBAL_RATE_LIMIT_STORE = RateLimitStore()


def get_rate_limit_store() -> RateLimitStore:
    return _GLOBAL_RATE_LIMIT_STORE


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces rate limits on authentication and file upload endpoints."""

    def __init__(self, app: Any, store: RateLimitStore | None = None) -> None:
        super().__init__(app)
        self.store = store or get_rate_limit_store()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path

        # Determine rate limit bucket
        max_requests = 120
        window_sec = 60
        bucket_prefix = "gen"

        if path.startswith("/v1/auth") or path in ("/v1/me", "/v1/session"):
            max_requests = 30
            bucket_prefix = "auth"
        elif "/documents" in path or "/bank-statements" in path:
            max_requests = 60
            bucket_prefix = "upload"
        else:
            # General endpoints not aggressively throttled
            return await call_next(request)

        # Bypass header for the automated test suite only (Phase 5 fix: it was honoured for any
        # caller, so anyone could switch rate limiting off in production).
        if request.headers.get("X-Test-Bypass-Rate-Limit") == "true" and os.environ.get("AVENEL_AUTH_TEST_MODE") == "1":
            return await call_next(request)

        # Extract client identifier (X-Forwarded-For or client host)
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        key = f"{bucket_prefix}:{ip}"

        allowed, remaining, retry_after = self.store.is_allowed(key, max_requests, window_sec)
        if not allowed:
            return JSONResponse(
                status_code=429,
                media_type="application/problem+json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
                content={
                    "type": "https://avenel.ma/errors/rate-limit-exceeded",
                    "title": "Trop de requêtes",
                    "status": 429,
                    "detail": f"Limite de requêtes atteinte pour cette ressource. Veuillez réessayer dans {retry_after} secondes.",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces strict security headers: CSP, HSTS, X-Content-Type-Options, etc."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self'; connect-src 'self' http://localhost:8000; "
            "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        return response
