from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import UserModel


DEFAULT_AI_OVERVIEW_COOLDOWN_DAYS = 30


@dataclass(frozen=True)
class AIOverviewQuotaStatus:
    available: bool
    cooldown_days: int
    last_generated_at: datetime | None
    next_available_at: datetime | None
    has_cached_report: bool


class AIOverviewRateLimitError(
    ValueError
):
    def __init__(
        self,
        *,
        next_available_at: datetime,
        retry_after_seconds: int,
    ):
        super().__init__(
            "AI overview cooldown is active"
        )

        self.next_available_at = (
            next_available_at
        )
        self.retry_after_seconds = max(
            1,
            retry_after_seconds,
        )


def _utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


class AIOverviewQuotaRepository:
    """
    Persist and enforce the expensive longitudinal AI overview cooldown.

    A user row is locked while the provider request is in flight.
    The timestamp is flushed but not committed until generation succeeds.
    Provider/validation failures roll the reservation back, so failed
    requests do not consume the user's cooldown.
    """

    def __init__(
        self,
        session: Session,
        *,
        cooldown_days: int = (
            DEFAULT_AI_OVERVIEW_COOLDOWN_DAYS
        ),
    ):
        if cooldown_days < 0:
            raise ValueError(
                "cooldown_days must be >= 0"
            )

        self.session = session
        self.cooldown_days = int(
            cooldown_days
        )
        self.cooldown = timedelta(
            days=self.cooldown_days
        )

        self._reserved_user: (
            UserModel | None
        ) = None

    def _get_user(
        self,
        owner_steam_id: str,
        *,
        for_update: bool = False,
    ) -> UserModel:
        steam_id = owner_steam_id.strip()

        if not steam_id:
            raise ValueError(
                "owner_steam_id must not be empty"
            )

        stmt = select(
            UserModel
        ).where(
            UserModel.steam_id
            == steam_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        user = self.session.scalar(
            stmt
        )

        if user is None:
            raise ValueError(
                "User not found"
            )

        return user

    def get_status(
        self,
        owner_steam_id: str,
        *,
        now: datetime | None = None,
    ) -> AIOverviewQuotaStatus:
        user = self._get_user(
            owner_steam_id
        )

        current = _utc(
            now
            or datetime.now(
                timezone.utc
            )
        )

        last = (
            _utc(
                user.ai_overview_last_generated_at
            )
            if (
                user.ai_overview_last_generated_at
                is not None
            )
            else None
        )

        next_available_at = None
        available = True

        if (
            self.cooldown_days > 0
            and last is not None
        ):
            next_available_at = (
                last
                + self.cooldown
            )

            available = (
                current
                >= next_available_at
            )

        return AIOverviewQuotaStatus(
            available=available,
            cooldown_days=(
                self.cooldown_days
            ),
            last_generated_at=last,
            next_available_at=(
                next_available_at
            ),
            has_cached_report=(
                user.ai_overview_last_response
                is not None
            ),
        )

    def reserve_generation(
        self,
        owner_steam_id: str,
        *,
        now: datetime | None = None,
    ) -> datetime:
        user = self._get_user(
            owner_steam_id,
            for_update=True,
        )

        current = _utc(
            now
            or datetime.now(
                timezone.utc
            )
        )

        last = (
            _utc(
                user.ai_overview_last_generated_at
            )
            if (
                user.ai_overview_last_generated_at
                is not None
            )
            else None
        )

        if (
            self.cooldown_days > 0
            and last is not None
        ):
            next_available_at = (
                last
                + self.cooldown
            )

            if current < next_available_at:
                remaining = int(
                    (
                        next_available_at
                        - current
                    ).total_seconds()
                )

                self.session.rollback()

                raise AIOverviewRateLimitError(
                    next_available_at=(
                        next_available_at
                    ),
                    retry_after_seconds=(
                        remaining
                    ),
                )

        user.ai_overview_last_generated_at = (
            current
        )

        self._reserved_user = user

        self.session.flush()

        return current

    def commit_success(
        self,
        response: Mapping[
            str,
            Any,
        ],
    ) -> None:
        if self._reserved_user is None:
            raise RuntimeError(
                "AI overview generation was not reserved"
            )

        self._reserved_user.ai_overview_last_response = dict(
            response
        )

        try:
            self.session.commit()
        finally:
            self._reserved_user = None

    def cancel_generation(
        self,
    ) -> None:
        try:
            self.session.rollback()
        finally:
            self._reserved_user = None

    def get_cached_response(
        self,
        owner_steam_id: str,
    ) -> dict[str, Any] | None:
        user = self._get_user(
            owner_steam_id
        )

        response = (
            user.ai_overview_last_response
        )

        if response is None:
            return None

        return dict(
            response
        )
