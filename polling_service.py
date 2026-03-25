from PySide6.QtCore import QObject, QTimer, Signal

from api_client import AuthError, RateLimitError, UsageAPIClient
from auth import CredentialReader
from models import UsageData


class PollingService(QObject):
    usage_updated = Signal(object)
    error_occurred = Signal(str)
    auth_missing = Signal()

    BACKOFF_RATE_LIMIT = 900_000    # 15 min
    BACKOFF_NETWORK = 60_000        # 1 min
    BACKOFF_AUTH = 60_000           # 1 min

    def __init__(self, poll_interval_ms: int = 300_000):
        super().__init__()
        self._normal_interval = poll_interval_ms
        self._cred_reader = CredentialReader()
        self._api_client = UsageAPIClient()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._network_backoff = self.BACKOFF_NETWORK

    def start(self):
        self._poll()
        self._timer.start(self._normal_interval)

    def stop(self):
        self._timer.stop()

    def refresh_now(self):
        self._poll()

    def set_interval(self, ms: int):
        self._normal_interval = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def _poll(self):
        token = self._cred_reader.get_access_token()
        if not token:
            self.auth_missing.emit()
            self._timer.setInterval(self.BACKOFF_AUTH)
            return

        try:
            data = self._api_client.fetch_usage(token)
            self.usage_updated.emit(data)
            self._timer.setInterval(self._normal_interval)
            self._network_backoff = self.BACKOFF_NETWORK
        except AuthError:
            self._cred_reader.force_reread()
            token = self._cred_reader.get_access_token()
            if token:
                try:
                    data = self._api_client.fetch_usage(token)
                    self.usage_updated.emit(data)
                    self._timer.setInterval(self._normal_interval)
                    return
                except Exception:
                    pass
            self.error_occurred.emit("Authentication failed")
            self._timer.setInterval(self.BACKOFF_AUTH)
        except RateLimitError:
            self.error_occurred.emit("Rate limited — backing off")
            self._timer.setInterval(self.BACKOFF_RATE_LIMIT)
        except Exception as e:
            self.error_occurred.emit(f"Network error: {e}")
            self._timer.setInterval(self._network_backoff)
            self._network_backoff = min(self._network_backoff * 2, 600_000)
