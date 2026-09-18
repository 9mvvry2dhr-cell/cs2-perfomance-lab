from __future__ import annotations

from src.database.connection import (
    create_db_engine,
    create_session_factory,
)
from src.database.repository import (
    AnalysisRepository,
)
from src.domain.insights import (
    FINDINGS_VERSION,
)


def main() -> None:
    engine = create_db_engine()

    session_factory = (
        create_session_factory(
            engine
        )
    )

    session = session_factory()

    try:
        repository = AnalysisRepository(
            session
        )

        updated = (
            repository.refresh_findings()
        )

        print(
            "Findings backfill complete: "
            f"{updated} match(es) -> "
            f"{FINDINGS_VERSION}"
        )

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
