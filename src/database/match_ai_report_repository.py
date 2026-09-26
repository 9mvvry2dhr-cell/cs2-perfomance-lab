from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    UserMatchModel,
)


MATCH_AI_REPORT_VERSION = "match-ai-v1"


class MatchAIReportRepository:
    """
    Cache one AI explanation per owned match.

    The user_match row is locked before a provider call so two concurrent
    requests cannot both spend tokens for the same match. Failed generations
    roll back and leave the cache empty.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self._reserved: (
            UserMatchModel | None
        ) = None

    def _get_owned_match(
        self,
        *,
        owner_steam_id: str,
        match_id: str,
        for_update: bool = False,
    ) -> UserMatchModel | None:
        owner = owner_steam_id.strip()
        match = match_id.strip()

        if not owner or not match:
            return None

        stmt = select(
            UserMatchModel
        ).where(
            UserMatchModel.owner_steam_id
            == owner,
            UserMatchModel.match_id
            == match,
        )

        if for_update:
            stmt = stmt.with_for_update()

        return self.session.scalar(
            stmt
        )

    @staticmethod
    def _current_cached_response(
        model: UserMatchModel,
    ) -> dict[str, Any] | None:
        if (
            model.ai_explanation_version
            != MATCH_AI_REPORT_VERSION
            or model.ai_explanation_response
            is None
        ):
            return None

        return dict(
            model.ai_explanation_response
        )

    def get_cached_response(
        self,
        *,
        owner_steam_id: str,
        match_id: str,
    ) -> dict[str, Any] | None:
        model = self._get_owned_match(
            owner_steam_id=owner_steam_id,
            match_id=match_id,
        )

        if model is None:
            return None

        return self._current_cached_response(
            model
        )

    def reserve_generation(
        self,
        *,
        owner_steam_id: str,
        match_id: str,
    ) -> dict[str, Any] | None:
        model = self._get_owned_match(
            owner_steam_id=owner_steam_id,
            match_id=match_id,
            for_update=True,
        )

        if model is None:
            return None

        cached = (
            self._current_cached_response(
                model
            )
        )

        if cached is not None:
            self.session.rollback()
            return cached

        self._reserved = model

        return None

    def commit_success(
        self,
        response: Mapping[str, Any],
    ) -> None:
        if self._reserved is None:
            raise RuntimeError(
                "Match AI generation was not reserved"
            )

        self._reserved.ai_explanation_response = dict(
            response
        )
        self._reserved.ai_explanation_version = (
            MATCH_AI_REPORT_VERSION
        )
        self._reserved.ai_explanation_generated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:
            self.session.commit()
        finally:
            self._reserved = None

    def cancel_generation(
        self,
    ) -> None:
        try:
            self.session.rollback()
        finally:
            self._reserved = None
