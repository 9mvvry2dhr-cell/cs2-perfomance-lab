import unittest
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.session import (
    hash_session_token,
)
from src.database.auth_repository import (
    AuthRepository,
)
from src.database.models import (
    AuthSessionModel,
    Base,
    UserModel,
)


class AuthRepositoryTest(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
        )

        Base.metadata.create_all(
            self.engine
        )

        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

        self.session = self.Session()

        self.repository = AuthRepository(
            self.session
        )

        self.now = datetime(
            2026,
            9,
            18,
            18,
            0,
            tzinfo=timezone.utc,
        )


    def tearDown(self):
        self.session.close()

        Base.metadata.drop_all(
            self.engine
        )

        self.engine.dispose()


    def test_create_session_persists_only_hash(
        self,
    ):
        created = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
            )
        )

        model = (
            self.session.query(
                AuthSessionModel
            )
            .one()
        )

        self.assertNotEqual(
            model.token_hash,
            created.token,
        )

        self.assertEqual(
            model.token_hash,
            hash_session_token(
                created.token
            ),
        )

        self.assertNotIn(
            created.token,
            model.token_hash,
        )


    def test_create_session_creates_user(
        self,
    ):
        self.repository.create_session(
            "76561198055629469",
            now=self.now,
        )

        user = self.session.get(
            UserModel,
            "76561198055629469",
        )

        self.assertIsNotNone(
            user
        )


    def test_resolve_valid_session(
        self,
    ):
        created = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
            )
        )

        resolved = (
            self.repository
            .resolve_session(
                created.token,
                now=(
                    self.now
                    + timedelta(
                        minutes=5
                    )
                ),
            )
        )

        self.assertIsNotNone(
            resolved
        )

        self.assertEqual(
            resolved.steam_id,
            "76561198055629469",
        )


    def test_resolve_rejects_invalid_token(
        self,
    ):
        resolved = (
            self.repository
            .resolve_session(
                "definitely-not-valid",
                now=self.now,
            )
        )

        self.assertIsNone(
            resolved
        )


    def test_expired_session_is_rejected(
        self,
    ):
        created = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
                lifetime=timedelta(
                    seconds=1
                ),
            )
        )

        resolved = (
            self.repository
            .resolve_session(
                created.token,
                now=(
                    self.now
                    + timedelta(
                        seconds=2
                    )
                ),
            )
        )

        self.assertIsNone(
            resolved
        )


    def test_revoked_session_is_rejected(
        self,
    ):
        created = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
            )
        )

        revoked = (
            self.repository
            .revoke_session(
                created.token,
                now=(
                    self.now
                    + timedelta(
                        minutes=1
                    )
                ),
            )
        )

        self.assertTrue(
            revoked
        )

        resolved = (
            self.repository
            .resolve_session(
                created.token,
                now=(
                    self.now
                    + timedelta(
                        minutes=2
                    )
                ),
            )
        )

        self.assertIsNone(
            resolved
        )


    def test_revoke_all_sessions_for_user(
        self,
    ):
        first = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
            )
        )

        second = (
            self.repository
            .create_session(
                "76561198055629469",
                now=self.now,
            )
        )

        other = (
            self.repository
            .create_session(
                "99999999999999999",
                now=self.now,
            )
        )

        count = (
            self.repository
            .revoke_all_for_user(
                "76561198055629469",
                now=self.now,
            )
        )

        self.assertEqual(
            count,
            2,
        )

        self.assertIsNone(
            self.repository.resolve_session(
                first.token,
                now=self.now,
            )
        )

        self.assertIsNone(
            self.repository.resolve_session(
                second.token,
                now=self.now,
            )
        )

        self.assertIsNotNone(
            self.repository.resolve_session(
                other.token,
                now=self.now,
            )
        )


if __name__ == "__main__":
    unittest.main()
