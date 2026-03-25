import json
import os
from datetime import datetime, timezone
from pathlib import Path


class CredentialReader:
    def __init__(self):
        self._cred_path = Path.home() / ".claude" / ".credentials.json"
        self._cached_token: str | None = None
        self._cached_expires_at: datetime | None = None
        self._last_mtime: float = 0.0

    def get_access_token(self) -> str | None:
        if not self._cred_path.exists():
            return None

        current_mtime = os.path.getmtime(self._cred_path)
        if current_mtime != self._last_mtime:
            self._read_credentials()
            self._last_mtime = current_mtime

        if not self._cached_token or not self.is_token_valid():
            self._read_credentials()
            if not self.is_token_valid():
                return None

        return self._cached_token

    def is_token_valid(self) -> bool:
        if not self._cached_expires_at:
            return False
        buffer = 300  # 5 minutes
        now = datetime.now(timezone.utc).timestamp()
        return self._cached_expires_at.timestamp() > (now + buffer)

    def force_reread(self):
        self._last_mtime = 0.0
        self._cached_token = None

    def _read_credentials(self):
        try:
            data = json.loads(self._cred_path.read_text(encoding="utf-8"))
            oauth = data.get("claudeAiOauth", {})
            self._cached_token = oauth.get("accessToken")
            expires_at_ms = oauth.get("expiresAt")
            if expires_at_ms:
                self._cached_expires_at = datetime.fromtimestamp(
                    expires_at_ms / 1000, tz=timezone.utc
                )
            else:
                self._cached_expires_at = None
        except (json.JSONDecodeError, OSError, KeyError):
            self._cached_token = None
            self._cached_expires_at = None
