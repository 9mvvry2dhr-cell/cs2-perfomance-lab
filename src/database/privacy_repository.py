from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, selectinload

from src.database.models import (
    AnalysisJobModel,
    AuthSessionModel,
    FindingModel,
    MatchModel,
    MatchPlayerModel,
    PlayerSideStatsModel,
    UserMatchModel,
    UserModel,
)


class ActiveUserAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeleteUserDataResult:
    sessions_deleted: int
    jobs_deleted: int
    user_matches_deleted: int
    user_deleted: int
    matches_deleted: int


class PrivacyRepository:
    def __init__(self, session: Session):
        self.session = session

    def export_user_data(
        self,
        steam_id: str,
    ) -> dict:
        steam_id = steam_id.strip()

        if not steam_id:
            raise ValueError(
                "steam_id must not be empty"
            )

        user = self.session.get(
            UserModel,
            steam_id,
        )

        sessions = list(
            self.session.scalars(
                select(
                    AuthSessionModel
                ).where(
                    AuthSessionModel.steam_id
                    == steam_id
                ).order_by(
                    AuthSessionModel.created_at
                )
            ).all()
        )

        jobs = list(
            self.session.scalars(
                select(
                    AnalysisJobModel
                ).where(
                    AnalysisJobModel.owner_steam_id
                    == steam_id
                ).order_by(
                    AnalysisJobModel.created_at
                )
            ).all()
        )

        links = list(
            self.session.scalars(
                select(
                    UserMatchModel
                ).where(
                    UserMatchModel.owner_steam_id
                    == steam_id
                ).order_by(
                    UserMatchModel.created_at
                )
            ).all()
        )

        exported_matches = []

        for link in links:
            match = self.session.get(
                MatchModel,
                link.match_id,
            )

            player = self.session.scalar(
                select(
                    MatchPlayerModel
                )
                .options(
                    selectinload(
                        MatchPlayerModel.sides
                    ),
                    selectinload(
                        MatchPlayerModel.findings
                    ),
                )
                .where(
                    MatchPlayerModel.match_id
                    == link.match_id,
                    MatchPlayerModel.position
                    == link.player_position,
                )
            )

            if match is None or player is None:
                continue

            exported_matches.append(
                {
                    "match_id": match.match_id,
                    "linked_at": (
                        link.created_at.isoformat()
                    ),
                    "player_position": (
                        link.player_position
                    ),
                    "match": {
                        "map_name": match.map_name,
                        "duration_seconds": (
                            match.duration_seconds
                        ),
                        "rounds_played": (
                            match.rounds_played
                        ),
                        "score_ct": match.score_ct,
                        "score_t": match.score_t,
                        "winner_side": (
                            match.winner_side
                        ),
                        "is_valid": match.is_valid,
                        "validation_error": (
                            match.validation_error
                        ),
                        "analysis_version": (
                            match.analysis_version
                        ),
                        "findings_version": (
                            match.findings_version
                        ),
                        "created_at": (
                            match.created_at.isoformat()
                        ),
                    },
                    "player": {
                        "result": player.result,
                        "rounds_played": (
                            player.rounds_played
                        ),
                        "kills": player.kills,
                        "deaths": player.deaths,
                        "assists": player.assists,
                        "headshots": (
                            player.headshots
                        ),
                        "damage": player.damage,
                        "kd": player.kd,
                        "adr": player.adr,
                        "headshot_pct": (
                            player.headshot_pct
                        ),
                        "kast_rounds": (
                            player.kast_rounds
                        ),
                        "kast_pct": (
                            player.kast_pct
                        ),
                        "survived_rounds": (
                            player.survived_rounds
                        ),
                        "survival_pct": (
                            player.survival_pct
                        ),
                        "entry_kills": (
                            player.entry_kills
                        ),
                        "entry_deaths": (
                            player.entry_deaths
                        ),
                        "he_damage": (
                            player.he_damage
                        ),
                        "inferno_damage": (
                            player.inferno_damage
                        ),
                        "enemies_flashed": (
                            player.enemies_flashed
                        ),
                        "flash_duration": (
                            player.flash_duration
                        ),
                        "clutches_won": (
                            player.clutches_won
                        ),
                        "trade_kills": (
                            player.trade_kills
                        ),
                        "traded_deaths": (
                            player.traded_deaths
                        ),
                        "two_k_rounds": (
                            player.two_k_rounds
                        ),
                        "three_k_rounds": (
                            player.three_k_rounds
                        ),
                        "four_k_rounds": (
                            player.four_k_rounds
                        ),
                        "five_k_rounds": (
                            player.five_k_rounds
                        ),
                        "sides": [
                            {
                                "side": side.side,
                                "rounds_played": (
                                    side.rounds_played
                                ),
                                "kills": side.kills,
                                "deaths": side.deaths,
                                "damage": side.damage,
                                "adr": side.adr,
                                "kast_rounds": (
                                    side.kast_rounds
                                ),
                                "kast_pct": (
                                    side.kast_pct
                                ),
                                "survived_rounds": (
                                    side.survived_rounds
                                ),
                                "survival_pct": (
                                    side.survival_pct
                                ),
                                "entry_kills": (
                                    side.entry_kills
                                ),
                                "entry_deaths": (
                                    side.entry_deaths
                                ),
                            }
                            for side in sorted(
                                player.sides,
                                key=lambda item: (
                                    item.side
                                ),
                            )
                        ],
                        "findings": [
                            {
                                "position": (
                                    finding.position
                                ),
                                "code": finding.code,
                                "category": (
                                    finding.category
                                ),
                                "kind": finding.kind,
                                "severity": (
                                    finding.severity
                                ),
                                "side": finding.side,
                                "evidence": dict(
                                    finding.evidence
                                ),
                            }
                            for finding
                            in player.findings
                        ],
                    },
                }
            )

        return {
            "steam_id": steam_id,
            "account": (
                {
                    "created_at": (
                        user.created_at.isoformat()
                    ),
                    "last_login_at": (
                        user.last_login_at.isoformat()
                    ),
                }
                if user is not None
                else None
            ),
            "sessions": [
                {
                    "id": session.id,
                    "created_at": (
                        session.created_at.isoformat()
                    ),
                    "expires_at": (
                        session.expires_at.isoformat()
                    ),
                    "last_seen_at": (
                        session.last_seen_at.isoformat()
                    ),
                    "revoked_at": (
                        session.revoked_at.isoformat()
                        if session.revoked_at
                        is not None
                        else None
                    ),
                }
                for session in sessions
            ],
            "analysis_jobs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "original_filename": (
                        job.original_filename
                    ),
                    "file_sha256": (
                        job.file_sha256
                    ),
                    "match_id": job.match_id,
                    "error": job.error,
                    "created_at": (
                        job.created_at.isoformat()
                    ),
                    "started_at": (
                        job.started_at.isoformat()
                        if job.started_at
                        is not None
                        else None
                    ),
                    "finished_at": (
                        job.finished_at.isoformat()
                        if job.finished_at
                        is not None
                        else None
                    ),
                }
                for job in jobs
            ],
            "matches": exported_matches,
        }

    def delete_user_data(
        self,
        steam_id: str,
    ) -> DeleteUserDataResult:
        steam_id = steam_id.strip()

        if not steam_id:
            raise ValueError(
                "steam_id must not be empty"
            )

        try:
            active_job_exists = self.session.scalar(
                select(
                    exists().where(
                        AnalysisJobModel.owner_steam_id
                        == steam_id,
                        AnalysisJobModel.status.in_(
                            (
                                "queued",
                                "processing",
                            )
                        ),
                    )
                )
            )

            if active_job_exists:
                raise ActiveUserAnalysisError(
                    "User has an active analysis job"
                )

            user_model = self.session.get(
                UserModel,
                steam_id,
            )

            match_ids = list(
                self.session.scalars(
                    select(
                        UserMatchModel.match_id
                    ).where(
                        UserMatchModel.owner_steam_id
                        == steam_id
                    )
                ).all()
            )

            sessions_result = self.session.execute(
                delete(AuthSessionModel).where(
                    AuthSessionModel.steam_id
                    == steam_id
                )
            )

            jobs_result = self.session.execute(
                delete(AnalysisJobModel).where(
                    AnalysisJobModel.owner_steam_id
                    == steam_id
                )
            )

            user_matches_result = (
                self.session.execute(
                    delete(UserMatchModel).where(
                        UserMatchModel.owner_steam_id
                        == steam_id
                    )
                )
            )

            self.session.flush()

            user_deleted = 0

            if user_model is not None:
                self.session.delete(
                    user_model
                )
                user_deleted = 1

            self.session.flush()

            matches_deleted = 0

            for match_id in set(match_ids):
                retained_link_exists = (
                    self.session.scalar(
                        select(
                            exists().where(
                                UserMatchModel.match_id
                                == match_id
                            )
                        )
                    )
                )

                if retained_link_exists:
                    continue

                active_match_job_exists = (
                    self.session.scalar(
                        select(
                            exists().where(
                                AnalysisJobModel.file_sha256
                                == match_id,
                                AnalysisJobModel.status.in_(
                                    (
                                        "queued",
                                        "processing",
                                    )
                                ),
                            )
                        )
                    )
                )

                if active_match_job_exists:
                    continue

                # Production FK uses ON DELETE SET NULL.
                # Do this explicitly as well so SQLite/tests and
                # every supported database behave the same way.
                linked_jobs = list(
                    self.session.scalars(
                        select(
                            AnalysisJobModel
                        ).where(
                            AnalysisJobModel.match_id
                            == match_id
                        )
                    ).all()
                )

                for job in linked_jobs:
                    job.match_id = None

                match_model = self.session.get(
                    MatchModel,
                    match_id,
                )

                if match_model is None:
                    continue

                self.session.delete(
                    match_model
                )

                matches_deleted += 1

            self.session.commit()

            return DeleteUserDataResult(
                sessions_deleted=int(
                    sessions_result.rowcount or 0
                ),
                jobs_deleted=int(
                    jobs_result.rowcount or 0
                ),
                user_matches_deleted=int(
                    user_matches_result.rowcount or 0
                ),
                user_deleted=user_deleted,
                matches_deleted=matches_deleted,
            )

        except Exception:
            self.session.rollback()
            raise
