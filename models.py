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
class AppSettings:
    poll_interval_seconds: int = 60
    warning_threshold: float = 70.0
    critical_threshold: float = 90.0
    notifications_enabled: bool = True
    compact_display: bool = False
    start_with_windows: bool = False
