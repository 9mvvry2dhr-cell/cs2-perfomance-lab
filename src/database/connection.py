from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL_ENV = "DATABASE_URL"


def get_database_url() -> str:
    """
    Return the configured database URL.

    Production/runtime code must configure DATABASE_URL explicitly.
    """
    database_url = os.getenv(
        DATABASE_URL_ENV,
        "",
    ).strip()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured"
        )

    return database_url


def create_db_engine(
    database_url: str | None = None,
) -> Engine:
    """
    Create a SQLAlchemy engine.

    An explicit URL can be supplied by tests.
    Runtime code otherwise reads DATABASE_URL.
    """
    url = (
        database_url
        if database_url is not None
        else get_database_url()
    )

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: Engine,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """
    Provide a transaction-safe session boundary.
    """
    session = session_factory()

    try:
        yield session

    finally:
        session.close()
