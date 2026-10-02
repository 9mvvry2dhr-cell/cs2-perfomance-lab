from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import (
    distinct,
    func,
    select,
)
from sqlalchemy.orm import Session

from src.database.models import (
    AuthSessionModel,
    SiteVisitorModel,
)


ONLINE_WINDOW = timedelta(
    seconds=90
)

VISITOR_WINDOW = timedelta(
    hours=24
)


@dataclass(frozen=True)
class PresenceSummary:
    online: int
    visitors_24h: int
    logged_in_online: int


class PresenceRepository:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def touch(
        self,
        visitor_id: str,
    ) -> None:
        now = datetime.now(
            timezone.utc
        )

        visitor = self.session.get(
            SiteVisitorModel,
            visitor_id,
        )

        if visitor is None:
            visitor = SiteVisitorModel(
                visitor_id=visitor_id,
                first_seen_at=now,
                last_seen_at=now,
            )

            self.session.add(
                visitor
            )
        else:
            visitor.last_seen_at = now

        self.session.commit()

    def get_summary(
        self,
    ) -> PresenceSummary:
        now = datetime.now(
            timezone.utc
        )

        online_cutoff = (
            now - ONLINE_WINDOW
        )

        visitor_cutoff = (
            now - VISITOR_WINDOW
        )

        online = self.session.scalar(
            select(
                func.count()
            )
            .select_from(
                SiteVisitorModel
            )
            .where(
                SiteVisitorModel.last_seen_at
                >= online_cutoff
            )
        ) or 0

        visitors_24h = self.session.scalar(
            select(
                func.count()
            )
            .select_from(
                SiteVisitorModel
            )
            .where(
                SiteVisitorModel.last_seen_at
                >= visitor_cutoff
            )
        ) or 0

        logged_in_online = (
            self.session.scalar(
                select(
                    func.count(
                        distinct(
                            AuthSessionModel.steam_id
                        )
                    )
                ).where(
                    AuthSessionModel.revoked_at
                    .is_(None),
                    AuthSessionModel.expires_at
                    > now,
                    AuthSessionModel.last_seen_at
                    >= online_cutoff,
                )
            )
            or 0
        )

        return PresenceSummary(
            online=int(online),
            visitors_24h=int(
                visitors_24h
            ),
            logged_in_online=int(
                logged_in_online
            ),
        )
