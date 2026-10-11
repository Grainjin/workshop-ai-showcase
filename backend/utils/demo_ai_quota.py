"""Durable demo quotas: UTC days and fixed UTC minute windows.

Only top-level synchronous chat, agent preview and confirmation routes charge this quota. All require
verified authentication and use `user:<id>`, never tokens, emails or request headers.
There is currently no allowed unauthenticated AI entry point needing an IP fallback.
The keyed digest also protects low-entropy subjects if such a caller is added later;
that caller must use the direct peer address, not untrusted forwarding headers.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import hashlib
import hmac
import math
from threading import Lock

from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from backend import config, models


_quota_engines: dict[Engine, tuple[object, dict, Engine]] = {}
_quota_engines_lock = Lock()


def dispose_demo_ai_quota_engines(source: Engine | None = None) -> None:
    """Close cached quota pools at shutdown or when their source engine is disposed."""
    with _quota_engines_lock:
        if source is None:
            cached = list(_quota_engines.values())
            _quota_engines.clear()
        else:
            entry = _quota_engines.pop(source, None)
            cached = [entry] if entry is not None else []
        for _, _, engine in cached:
            engine.dispose()


def get_demo_ai_quota_engine(source: Engine) -> Engine:
    """Reuse a small independent pool with the caller's connection configuration.

    SQLAlchemy does not expose an engine's original creator/connect_args through a
    public getter. Reuse the pool's creator and event dispatch exactly as its own
    QueuePool.recreate() does; focused PostgreSQL tests guard this compatibility
    boundary (record-aware creator, connect_args and connection setup hooks).
    Rebuilding from URL alone would silently lose schema/SSL/creator settings.
    """
    # An in-memory SQLite database belongs to its connection. Keep the existing
    # serial-test behavior; independent production admission uses PostgreSQL.
    if source.dialect.name == "sqlite" and source.url.database in {None, "", ":memory:"}:
        return source
    with _quota_engines_lock:
        options = dict(source.get_execution_options())
        cached = _quota_engines.get(source)
        if cached is not None:
            pool, previous_options, engine = cached
            if pool is source.pool and previous_options == options:
                return engine
            engine.dispose()
            del _quota_engines[source]
        creator = getattr(source.pool, "_creator", None)
        if not callable(creator):
            raise RuntimeError("Unsupported SQLAlchemy pool: missing connection creator")
        pool = QueuePool(
            creator, pool_size=2, max_overflow=0, timeout=30,
            pre_ping=True, dialect=source.dialect, _dispatch=source.pool.dispatch,
        )
        engine = Engine(
            pool, source.dialect, source.url, execution_options=options,
            echo=source.echo, hide_parameters=source.hide_parameters,
        )
        # Public event registration preserves engine-level connection setup as
        # well as the pool's DBAPI connect/checkout/reset hooks copied above.
        def connection_setup(connection):
            source.dispatch.engine_connect(connection)

        event.listen(engine, "engine_connect", connection_setup)
        if not event.contains(source, "engine_disposed", dispose_demo_ai_quota_engines):
            event.listen(source, "engine_disposed", dispose_demo_ai_quota_engines)
        _quota_engines[source] = (source.pool, options, engine)
        return engine


@dataclass(frozen=True)
class DemoQuotaResult:
    allowed: bool
    remaining_daily: int
    retry_after_seconds: int | None


def consume_demo_ai_quota(
    subject: str, db: Session, now: datetime | None = None
) -> DemoQuotaResult:
    if not config.DEMO_MODE:
        return DemoQuotaResult(True, config.DEMO_AI_DAILY_LIMIT, None)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    minute_start = now.replace(second=0, microsecond=0)
    key = (config.JWT_PRIVATE_KEY or config.SECRET_KEY).encode()
    subject_hash = hmac.new(key, subject.encode(), hashlib.sha256).hexdigest()
    daily_limit = config.DEMO_AI_DAILY_LIMIT
    minute_limit = config.DEMO_AI_PER_MINUTE_LIMIT
    # A separate transaction durably charges before external work, without committing
    # unrelated caller work. Caller rollback/model failure cannot refund the quota.
    engine = get_demo_ai_quota_engine(db.get_bind().engine)
    insert = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
    with Session(engine) as quota_db, quota_db.begin():
        quota_db.execute(
            insert(models.DemoAIUsage).values(
                usage_date=now.date(), subject_hash=subject_hash,
                daily_count=0, minute_start=minute_start, minute_count=0,
            ).on_conflict_do_nothing(index_elements=["usage_date", "subject_hash"])
        )
        # The unique insert handles first-row races; PostgreSQL row locking serializes
        # both counters together. SQLite support is for serial local tests only.
        row = quota_db.execute(
            select(models.DemoAIUsage).where(
                models.DemoAIUsage.usage_date == now.date(),
                models.DemoAIUsage.subject_hash == subject_hash,
            ).with_for_update()
        ).scalar_one()
        remaining = max(0, daily_limit - row.daily_count)
        if remaining == 0:
            tomorrow = datetime.combine(now.date() + timedelta(days=1), time(), timezone.utc)
            return DemoQuotaResult(False, 0, max(1, math.ceil((tomorrow - now).total_seconds())))
        stored_minute = row.minute_start
        if stored_minute.tzinfo is None:  # SQLite serial test compatibility
            stored_minute = stored_minute.replace(tzinfo=timezone.utc)
        stored_minute = stored_minute.astimezone(timezone.utc)
        if minute_start > stored_minute:
            row.minute_start = minute_start
            row.minute_count = 0
            stored_minute = minute_start
        if row.minute_count >= minute_limit:
            retry = math.ceil((stored_minute + timedelta(minutes=1) - now).total_seconds())
            return DemoQuotaResult(False, remaining, max(1, retry))
        row.daily_count += 1
        row.minute_count += 1
        return DemoQuotaResult(True, remaining - 1, None)


def enforce_demo_ai_quota(current_user: models.User, db: Session) -> None:
    result = consume_demo_ai_quota(f"user:{current_user.id}", db)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "DEMO_AI_LIMIT_REACHED",
                "message": "The demo AI request limit has been reached. Please try again later.",
                "remaining_daily": result.remaining_daily,
                "retry_after_seconds": result.retry_after_seconds,
            },
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
