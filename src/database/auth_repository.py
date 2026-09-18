from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.session import (
    AuthenticatedSession,
    generate_session_token,
    hash_session_token,
)
from src.database.models import (
    AuthSessionModel,
    UserModel,
)


DEFAULT_SESSION_LIFETIME = timedelta(
    days=30
)


@dataclass(frozen=True)
class CreatedSession:
    token: str
    session: AuthenticatedSession


class AuthRepository:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session


    def create_session(
        self,
        steam_id: str,
        *,
        now: datetime | None = None,
        lifetime: timedelta = (
            DEFAULT_SESSION_LIFETIME
        ),
    ) -> CreatedSession:
        steam_id = steam_id.strip()

        if not steam_id:
            raise ValueError(
                "steam_id must not be empty"
            )

        if lifetime.total_seconds() <= 0:
            raise ValueError(
                "session lifetime must be positive"
            )

        now = now or datetime.now(
            timezone.utc
        )

        token = generate_session_token()

        token_hash = hash_session_token(
            token
        )

        user = self.session.get(
            UserModel,
            steam_id,
        )

        try:
            if user is None:
                user = UserModel(
                    steam_id=steam_id,
                    created_at=now,
                    last_login_at=now,
                )

                self.session.add(
                    user
                )
            else:
                user.last_login_at = now

            session_model = AuthSessionModel(
                token_hash=token_hash,
                steam_id=steam_id,
                created_at=now,
                expires_at=(
                    now + lifetime
                ),
                last_seen_at=now,
                revoked_at=None,
            )

            self.session.add(
                session_model
            )

            self.session.commit()

            return CreatedSession(
                token=token,
                session=AuthenticatedSession(
                    steam_id=steam_id,
                    session_id=(
                        session_model.id
                    ),
                    expires_at=(
                        session_model.expires_at
                    ),
                ),
            )

        except Exception:
            self.session.rollback()
            raise


    def resolve_session(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> AuthenticatedSession | None:
        if not token:
            return None

        now = now or datetime.now(
            timezone.utc
        )

        token_hash = hash_session_token(
            token
        )

        stmt = (
            select(AuthSessionModel)
            .where(
                AuthSessionModel.token_hash
                == token_hash
            )
        )

        session_model = self.session.scalar(
            stmt
        )

        if session_model is None:
            return None

        if session_model.revoked_at is not None:
            return None

        expires_at = (
            session_model.expires_at
        )

        if (
            expires_at.tzinfo is None
            and now.tzinfo is not None
        ):
            expires_at = (
                expires_at.replace(
                    tzinfo=timezone.utc
                )
            )

        if expires_at <= now:
            return None

        session_model.last_seen_at = now

        self.session.commit()

        return AuthenticatedSession(
            steam_id=session_model.steam_id,
            session_id=session_model.id,
            expires_at=expires_at,
        )


    def revoke_session(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        if not token:
            return False

        now = now or datetime.now(
            timezone.utc
        )

        token_hash = hash_session_token(
            token
        )

        stmt = (
            select(AuthSessionModel)
            .where(
                AuthSessionModel.token_hash
                == token_hash
            )
        )

        session_model = self.session.scalar(
            stmt
        )

        if session_model is None:
            return False

        if session_model.revoked_at is not None:
            return True

        try:
            session_model.revoked_at = now

            self.session.commit()

            return True

        except Exception:
            self.session.rollback()
            raise


    def revoke_all_for_user(
        self,
        steam_id: str,
        *,
        now: datetime | None = None,
    ) -> int:
        steam_id = steam_id.strip()

        if not steam_id:
            raise ValueError(
                "steam_id must not be empty"
            )

        now = now or datetime.now(
            timezone.utc
        )

        stmt = (
            select(AuthSessionModel)
            .where(
                AuthSessionModel.steam_id
                == steam_id,
                AuthSessionModel.revoked_at
                .is_(None),
            )
        )

        sessions = list(
            self.session.scalars(
                stmt
            ).all()
        )

        try:
            for session_model in sessions:
                session_model.revoked_at = now

            self.session.commit()

            return len(sessions)

        except Exception:
            self.session.rollback()
            raise
