from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UsageData:
    five_hour_utilization: float = 0.0
    five_hour_resets_at: datetime | None = None
    seven_day_utilization: float = 0.0
    seven_day_resets_at: datetime | None = None
    seven_day_sonnet_utilization: float | None = None
    seven_day_opus_utilization: float | None = None
    extra_usage_enabled: bool = False
    extra_usage_utilization: float | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionTokenUsage:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    message_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_creation_tokens + self.cache_read_tokens


@dataclass
class SessionData:
    session_id: str = ""
    slug: str = ""
    ai_title: str | None = None
    project_path: str = ""
    entrypoint: str = ""
    git_branch: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    user_message_count: int = 0
    token_usage: list[SessionTokenUsage] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(u.total_tokens for u in self.token_usage)

    @property
    def total_cost(self) -> float:
        from cost_estimator import estimate_cost
        return sum(estimate_cost(u.model, u) for u in self.token_usage)

    @property
    def duration_seconds(self) -> int | None:
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return None

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


@dataclass
class AppSettings:
    poll_interval_seconds: int = 60
    warning_threshold: float = 70.0
    critical_threshold: float = 90.0
    notifications_enabled: bool = True
