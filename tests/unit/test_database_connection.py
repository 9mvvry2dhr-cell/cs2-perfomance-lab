import os
import unittest
from unittest.mock import patch

from sqlalchemy import text

from src.database.connection import (
    create_db_engine,
    create_session_factory,
    get_database_url,
    session_scope,
)


class DatabaseConnectionTest(unittest.TestCase):
    def test_get_database_url_reads_environment(self):
        expected = (
            "postgresql+psycopg://"
            "user:password@localhost:5432/test_db"
        )

        with patch.dict(
            os.environ,
            {"DATABASE_URL": expected},
            clear=False,
        ):
            self.assertEqual(
                get_database_url(),
                expected,
            )

    def test_get_database_url_fails_when_missing(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "DATABASE_URL is not configured",
            ):
                get_database_url()

    def test_explicit_sqlite_url_can_create_session(self):
        engine = create_db_engine(
            "sqlite+pysqlite:///:memory:"
        )

        session_factory = create_session_factory(
            engine
        )

        with session_scope(
            session_factory
        ) as session:
            value = session.scalar(
                text("SELECT 1")
            )

        self.assertEqual(
            value,
            1,
        )

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
