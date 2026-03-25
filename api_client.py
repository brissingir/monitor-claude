from datetime import datetime, timezone

import requests

from models import UsageData


class RateLimitError(Exception):
    pass


class AuthError(Exception):
    pass


class UsageAPIClient:
    URL = "https://api.anthropic.com/api/oauth/usage"
    TIMEOUT = 10

    def fetch_usage(self, access_token: str) -> UsageData:
        resp = requests.get(
            self.URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "anthropic-beta": "oauth-2025-04-20",
            },
            timeout=self.TIMEOUT,
        )

        if resp.status_code == 401:
            raise AuthError("Invalid or expired token")
        if resp.status_code == 429:
            raise RateLimitError("Rate limited")
        resp.raise_for_status()

        data = resp.json()
        return self._parse(data)

    def _parse(self, data: dict) -> UsageData:
        five = data.get("five_hour") or {}
        seven = data.get("seven_day") or {}
        sonnet = data.get("seven_day_sonnet")
        opus = data.get("seven_day_opus")
        extra = data.get("extra_usage") or {}

        return UsageData(
            five_hour_utilization=float(five.get("utilization", 0)),
            five_hour_resets_at=self._parse_dt(five.get("resets_at")),
            seven_day_utilization=float(seven.get("utilization", 0)),
            seven_day_resets_at=self._parse_dt(seven.get("resets_at")),
            seven_day_sonnet_utilization=(
                float(sonnet["utilization"]) if sonnet and sonnet.get("utilization") is not None else None
            ),
            seven_day_opus_utilization=(
                float(opus["utilization"]) if opus and opus.get("utilization") is not None else None
            ),
            extra_usage_enabled=bool(extra.get("is_enabled")),
            extra_usage_utilization=(
                float(extra["utilization"]) if extra.get("utilization") is not None else None
            ),
            fetched_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
