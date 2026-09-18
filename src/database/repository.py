from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.database.models import (
    FindingModel,
    MatchModel,
    MatchPlayerModel,
    PlayerSideStatsModel,
)
from src.domain.analysis import (
    MatchAnalysis,
    PlayerAnalysis,
    PlayerStats,
    SideStats,
)
from src.domain.history import (
    PlayerHistorySummary,
    PlayerMatchHistoryItem,
    build_player_history_summary,
)
from src.domain.insights import (
    FINDINGS_VERSION,
    Finding,
    generate_player_findings,
)


ANALYSIS_VERSION = "v1"


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_analysis(
        self,
        analysis: MatchAnalysis,
    ) -> None:
        """
        Persist one complete MatchAnalysis v1.

        Saving the same match_id replaces the previous analysis
        in one transaction.
        """
        try:
            existing = self.session.get(
                MatchModel,
                analysis.match_id,
            )

            if existing is not None:
                self.session.delete(existing)
                self.session.flush()

            match_model = MatchModel(
                match_id=analysis.match_id,
                map_name=analysis.map_name,
                duration_seconds=analysis.duration_seconds,
                rounds_played=analysis.rounds_played,
                score_ct=analysis.score_ct,
                score_t=analysis.score_t,
                winner_side=analysis.winner_side,
                is_valid=analysis.is_valid,
                validation_error=analysis.validation_error,
                analysis_version=ANALYSIS_VERSION,
                findings_version=FINDINGS_VERSION,
            )

            for player_position, player in enumerate(
                analysis.players
            ):
                stats = player.stats

                player_model = MatchPlayerModel(
                    position=player_position,
                    steam_id=player.steam_id,
                    name=player.name,
                    rounds_played=stats.rounds_played,
                    kills=stats.kills,
                    deaths=stats.deaths,
                    assists=stats.assists,
                    headshots=stats.headshots,
                    damage=stats.damage,
                    kd=stats.kd,
                    adr=stats.adr,
                    headshot_pct=stats.headshot_pct,
                    kast_rounds=stats.kast_rounds,
                    kast_pct=stats.kast_pct,
                    survived_rounds=stats.survived_rounds,
                    survival_pct=stats.survival_pct,
                    entry_kills=stats.entry_kills,
                    entry_deaths=stats.entry_deaths,
                    he_damage=stats.he_damage,
                    inferno_damage=stats.inferno_damage,
                    enemies_flashed=stats.enemies_flashed,
                    flash_duration=stats.flash_duration,
                    clutches_won=stats.clutches_won,
                    trade_kills=stats.trade_kills,
                    traded_deaths=stats.traded_deaths,
                    two_k_rounds=stats.two_k_rounds,
                    three_k_rounds=stats.three_k_rounds,
                    four_k_rounds=stats.four_k_rounds,
                    five_k_rounds=stats.five_k_rounds,
                )

                for side_name in ("CT", "T"):
                    side_stats = player.sides.get(
                        side_name
                    )

                    if side_stats is None:
                        continue

                    player_model.sides.append(
                        PlayerSideStatsModel(
                            side=side_name,
                            rounds_played=(
                                side_stats.rounds_played
                            ),
                            kills=side_stats.kills,
                            deaths=side_stats.deaths,
                            damage=side_stats.damage,
                            adr=side_stats.adr,
                            kast_rounds=(
                                side_stats.kast_rounds
                            ),
                            kast_pct=side_stats.kast_pct,
                            survived_rounds=(
                                side_stats.survived_rounds
                            ),
                            survival_pct=(
                                side_stats.survival_pct
                            ),
                            entry_kills=(
                                side_stats.entry_kills
                            ),
                            entry_deaths=(
                                side_stats.entry_deaths
                            ),
                        )
                    )

                for finding_position, finding in enumerate(
                    player.findings
                ):
                    player_model.findings.append(
                        FindingModel(
                            position=finding_position,
                            code=finding.code,
                            category=finding.category,
                            kind=finding.kind,
                            severity=finding.severity,
                            side=finding.side,
                            evidence=dict(
                                finding.evidence
                            ),
                        )
                    )

                match_model.players.append(
                    player_model
                )

            self.session.add(match_model)
            self.session.commit()

        except Exception:
            self.session.rollback()
            raise

    def get_analysis(
        self,
        match_id: str,
    ) -> MatchAnalysis | None:
        """
        Load a persisted MatchAnalysis v1.
        """
        stmt = (
            select(MatchModel)
            .options(
                selectinload(
                    MatchModel.players
                ).selectinload(
                    MatchPlayerModel.sides
                ),
                selectinload(
                    MatchModel.players
                ).selectinload(
                    MatchPlayerModel.findings
                ),
            )
            .where(
                MatchModel.match_id == match_id
            )
        )

        match_model = self.session.scalar(stmt)

        if match_model is None:
            return None

        if (
            match_model.analysis_version
            != ANALYSIS_VERSION
        ):
            raise ValueError(
                "Unsupported analysis version: "
                f"{match_model.analysis_version}"
            )

        players: list[PlayerAnalysis] = []

        for player_model in match_model.players:
            stats = PlayerStats(
                rounds_played=(
                    player_model.rounds_played
                ),
                kills=player_model.kills,
                deaths=player_model.deaths,
                assists=player_model.assists,
                headshots=player_model.headshots,
                damage=player_model.damage,
                kd=player_model.kd,
                adr=player_model.adr,
                headshot_pct=(
                    player_model.headshot_pct
                ),
                kast_rounds=(
                    player_model.kast_rounds
                ),
                kast_pct=player_model.kast_pct,
                survived_rounds=(
                    player_model.survived_rounds
                ),
                survival_pct=(
                    player_model.survival_pct
                ),
                entry_kills=(
                    player_model.entry_kills
                ),
                entry_deaths=(
                    player_model.entry_deaths
                ),
                he_damage=player_model.he_damage,
                inferno_damage=(
                    player_model.inferno_damage
                ),
                enemies_flashed=(
                    player_model.enemies_flashed
                ),
                flash_duration=(
                    player_model.flash_duration
                ),
                clutches_won=(
                    player_model.clutches_won
                ),
                trade_kills=(
                    player_model.trade_kills
                ),
                traded_deaths=(
                    player_model.traded_deaths
                ),
                two_k_rounds=(
                    player_model.two_k_rounds
                ),
                three_k_rounds=(
                    player_model.three_k_rounds
                ),
                four_k_rounds=(
                    player_model.four_k_rounds
                ),
                five_k_rounds=(
                    player_model.five_k_rounds
                ),
            )

            side_models = {
                side.side: side
                for side in player_model.sides
            }

            sides: dict[str, SideStats] = {}

            for side_name in ("CT", "T"):
                side_model = side_models.get(
                    side_name
                )

                if side_model is None:
                    continue

                sides[side_name] = SideStats(
                    rounds_played=(
                        side_model.rounds_played
                    ),
                    kills=side_model.kills,
                    deaths=side_model.deaths,
                    damage=side_model.damage,
                    adr=side_model.adr,
                    kast_rounds=(
                        side_model.kast_rounds
                    ),
                    kast_pct=side_model.kast_pct,
                    survived_rounds=(
                        side_model.survived_rounds
                    ),
                    survival_pct=(
                        side_model.survival_pct
                    ),
                    entry_kills=(
                        side_model.entry_kills
                    ),
                    entry_deaths=(
                        side_model.entry_deaths
                    ),
                )

            findings = [
                Finding(
                    code=finding.code,
                    category=finding.category,
                    kind=finding.kind,
                    severity=finding.severity,
                    side=finding.side,
                    evidence={
                        key: float(value)
                        for key, value
                        in finding.evidence.items()
                    },
                )
                for finding
                in player_model.findings
            ]

            players.append(
                PlayerAnalysis(
                    steam_id=player_model.steam_id,
                    name=player_model.name,
                    stats=stats,
                    sides=sides,
                    findings=findings,
                )
            )

        return MatchAnalysis(
            match_id=match_model.match_id,
            map_name=match_model.map_name,
            duration_seconds=(
                match_model.duration_seconds
            ),
            rounds_played=(
                match_model.rounds_played
            ),
            score_ct=match_model.score_ct,
            score_t=match_model.score_t,
            winner_side=match_model.winner_side,
            is_valid=match_model.is_valid,
            validation_error=(
                match_model.validation_error
            ),
            players=players,
        )

    def get_player_match_history(
        self,
        steam_id: str,
        *,
        limit: int = 20,
    ) -> list[PlayerMatchHistoryItem]:
        """
        Load the newest valid persisted matches for one player.

        created_at is analysis persistence time, not match start time.
        """
        steam_id = steam_id.strip()

        if not steam_id:
            raise ValueError(
                "steam_id must not be empty"
            )

        if limit < 1 or limit > 100:
            raise ValueError(
                "limit must be between 1 and 100"
            )

        stmt = (
            select(
                MatchPlayerModel,
                MatchModel,
            )
            .join(
                MatchModel,
                MatchPlayerModel.match_id
                == MatchModel.match_id,
            )
            .options(
                selectinload(
                    MatchPlayerModel.findings
                )
            )
            .where(
                MatchPlayerModel.steam_id
                == steam_id,
                MatchModel.analysis_version
                == ANALYSIS_VERSION,
                MatchModel.is_valid.is_(True),
            )
            .order_by(
                MatchModel.created_at.desc(),
                MatchModel.match_id.desc(),
            )
            .limit(limit)
        )

        rows = self.session.execute(
            stmt
        ).all()

        history: list[
            PlayerMatchHistoryItem
        ] = []

        for player_model, match_model in rows:
            findings = [
                Finding(
                    code=finding.code,
                    category=finding.category,
                    kind=finding.kind,
                    severity=finding.severity,
                    side=finding.side,
                    evidence={
                        key: float(value)
                        for key, value
                        in finding.evidence.items()
                    },
                )
                for finding
                in player_model.findings
            ]

            history.append(
                PlayerMatchHistoryItem(
                    match_id=match_model.match_id,
                    analyzed_at=match_model.created_at,
                    map_name=match_model.map_name,
                    score_ct=match_model.score_ct,
                    score_t=match_model.score_t,
                    player_name=player_model.name,
                    stats=PlayerStats(
                        rounds_played=(
                            player_model.rounds_played
                        ),
                        kills=player_model.kills,
                        deaths=player_model.deaths,
                        assists=player_model.assists,
                        headshots=player_model.headshots,
                        damage=player_model.damage,
                        kd=player_model.kd,
                        adr=player_model.adr,
                        headshot_pct=(
                            player_model.headshot_pct
                        ),
                        kast_rounds=(
                            player_model.kast_rounds
                        ),
                        kast_pct=player_model.kast_pct,
                        survived_rounds=(
                            player_model.survived_rounds
                        ),
                        survival_pct=(
                            player_model.survival_pct
                        ),
                        entry_kills=(
                            player_model.entry_kills
                        ),
                        entry_deaths=(
                            player_model.entry_deaths
                        ),
                        he_damage=player_model.he_damage,
                        inferno_damage=(
                            player_model.inferno_damage
                        ),
                        enemies_flashed=(
                            player_model.enemies_flashed
                        ),
                        flash_duration=(
                            player_model.flash_duration
                        ),
                        clutches_won=(
                            player_model.clutches_won
                        ),
                        trade_kills=(
                            player_model.trade_kills
                        ),
                        traded_deaths=(
                            player_model.traded_deaths
                        ),
                        two_k_rounds=(
                            player_model.two_k_rounds
                        ),
                        three_k_rounds=(
                            player_model.three_k_rounds
                        ),
                        four_k_rounds=(
                            player_model.four_k_rounds
                        ),
                        five_k_rounds=(
                            player_model.five_k_rounds
                        ),
                    ),
                    findings=findings,
                )
            )

        return history


    def get_player_history_summary(
        self,
        steam_id: str,
        *,
        limit: int = 10,
    ) -> PlayerHistorySummary | None:
        history = self.get_player_match_history(
            steam_id,
            limit=limit,
        )

        return build_player_history_summary(
            steam_id,
            history,
        )

    def refresh_findings(
        self,
        *,
        target_version: str = FINDINGS_VERSION,
    ) -> int:
        """
        Rebuild persisted findings from already verified metrics.

        Demo parsing is intentionally not repeated.
        Only matches using the supported analysis contract are
        eligible.

        Returns the number of matches updated.
        """
        if target_version != FINDINGS_VERSION:
            raise ValueError(
                "Unsupported findings version: "
                f"{target_version}"
            )

        stmt = (
            select(MatchModel)
            .options(
                selectinload(
                    MatchModel.players
                ).selectinload(
                    MatchPlayerModel.sides
                ),
                selectinload(
                    MatchModel.players
                ).selectinload(
                    MatchPlayerModel.findings
                ),
            )
            .where(
                MatchModel.analysis_version
                == ANALYSIS_VERSION,
                MatchModel.findings_version
                != target_version,
            )
            .order_by(
                MatchModel.created_at,
                MatchModel.match_id,
            )
        )

        matches = list(
            self.session.scalars(
                stmt
            ).unique().all()
        )

        try:
            for match_model in matches:
                for player_model in (
                    match_model.players
                ):
                    split_stats = {}

                    for side_model in (
                        player_model.sides
                    ):
                        split_stats[
                            side_model.side
                        ] = {
                            "rounds_played": float(
                                side_model.rounds_played
                            ),
                            "kills": float(
                                side_model.kills
                            ),
                            "deaths": float(
                                side_model.deaths
                            ),
                            "damage": float(
                                side_model.damage
                            ),
                            "kast_rounds": float(
                                side_model.kast_rounds
                            ),
                            "survived_rounds": float(
                                side_model.survived_rounds
                            ),
                            "entry_kills": float(
                                side_model.entry_kills
                            ),
                            "entry_deaths": float(
                                side_model.entry_deaths
                            ),
                        }

                    overall_stats = {
                        "rounds_played": float(
                            player_model.rounds_played
                        ),
                        "he_damage": float(
                            player_model.he_damage
                        ),
                        "inferno_damage": float(
                            player_model.inferno_damage
                        ),
                        "enemies_flashed": float(
                            player_model.enemies_flashed
                        ),
                        "flash_duration": float(
                            player_model.flash_duration
                        ),
                        "trade_kills": float(
                            player_model.trade_kills
                        ),
                        "two_k_rounds": float(
                            player_model.two_k_rounds
                        ),
                        "three_k_rounds": float(
                            player_model.three_k_rounds
                        ),
                        "four_k_rounds": float(
                            player_model.four_k_rounds
                        ),
                        "five_k_rounds": float(
                            player_model.five_k_rounds
                        ),
                        "clutches_won": float(
                            player_model.clutches_won
                        ),
                    }

                    generated = (
                        generate_player_findings(
                            split_stats,
                            overall_stats=(
                                overall_stats
                            ),
                        )
                    )

                    for existing in list(
                        player_model.findings
                    ):
                        self.session.delete(
                            existing
                        )

                    player_model.findings.clear()

                    # Ensure old rows are deleted before
                    # new rows reuse position values.
                    self.session.flush()

                    for position, finding in enumerate(
                        generated
                    ):
                        player_model.findings.append(
                            FindingModel(
                                position=position,
                                code=finding.code,
                                category=(
                                    finding.category
                                ),
                                kind=finding.kind,
                                severity=(
                                    finding.severity
                                ),
                                side=finding.side,
                                evidence=dict(
                                    finding.evidence
                                ),
                            )
                        )

                match_model.findings_version = (
                    target_version
                )

            self.session.commit()

            return len(matches)

        except Exception:
            self.session.rollback()
            raise
