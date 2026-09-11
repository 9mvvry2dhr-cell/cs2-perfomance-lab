from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.repository import (
    AnalysisRepository,
)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    engine = create_db_engine()

    return create_session_factory(
        engine
    )


def get_analysis_repository(
) -> Iterator[AnalysisRepository]:
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield AnalysisRepository(
            session
        )
    finally:
        session.close()
