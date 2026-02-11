import uuid
from datetime import datetime

from pydantic import BaseModel

from cti.models.observable import ObservableType


class RecentObservable(BaseModel):
    id: uuid.UUID
    type: ObservableType
    value: str
    confidence_score: int
    created_at: datetime


class FeedRunSummary(BaseModel):
    feed_id: uuid.UUID
    feed_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    observables_created: int
    observables_updated: int
    errors: int


class ErroredFeed(BaseModel):
    feed_id: uuid.UUID
    feed_name: str
    error_message: str | None
    last_run_at: datetime | None


class DashboardStats(BaseModel):
    total_observables: int
    observables_by_type: dict[str, int]
    total_feeds: int
    active_feeds: int
    feeds_with_errors: int
    observables_today: int
    recent_observables: list[RecentObservable]
    recent_feed_runs: list[FeedRunSummary]
    errored_feeds: list[ErroredFeed] = []
