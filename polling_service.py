import logging

from PySide6.QtCore import QObject, QTimer, QThread, Signal

from api_client import AuthError, RateLimitError, UsageAPIClient
from auth import CredentialReader
from data_store import DataStore
from models import UsageData

logger = logging.getLogger("monitor.polling")


class _PollWorker(QObject):
    finished = Signal(object)  # UsageData
    error = Signal(str, str)   # (error_type, message)

    def __init__(self, cred_reader: CredentialReader, api_client: UsageAPIClient):
        super().__init__()
        self._cred_reader = cred_reader
        self._api_client = api_client

    def run(self):
        token = self._cred_reader.get_access_token()
        if not token:
            self.error.emit("auth_missing", "")
            return

        try:
            data = self._api_client.fetch_usage(token)
            self.finished.emit(data)
        except AuthError:
            self._cred_reader.force_reread()
            token = self._cred_reader.get_access_token()
            if token:
                try:
                    data = self._api_client.fetch_usage(token)
                    self.finished.emit(data)
                    return
                except Exception:
                    pass
            self.error.emit("auth", "Authentication failed")
        except RateLimitError:
            self.error.emit("rate_limit", "Rate limited — backing off")
        except Exception as e:
            self.error.emit("network", f"Network error: {e}")


class PollingService(QObject):
    usage_updated = Signal(object)
    error_occurred = Signal(str)
    auth_missing = Signal()

    BACKOFF_RATE_LIMIT = 900_000    # 15 min
    BACKOFF_NETWORK = 60_000        # 1 min
    BACKOFF_AUTH = 60_000           # 1 min

    def __init__(self, poll_interval_ms: int = 300_000, data_store: DataStore | None = None):
        super().__init__()
        self._normal_interval = poll_interval_ms
        self._cred_reader = CredentialReader()
        self._api_client = UsageAPIClient()
        self._data_store = data_store
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._start_poll)
        self._network_backoff = self.BACKOFF_NETWORK
        self._worker_thread: QThread | None = None

    def start(self):
        self._start_poll()
        self._timer.start(self._normal_interval)

    def stop(self):
        self._timer.stop()
        self._cleanup_thread()

    def refresh_now(self):
        self._start_poll()

    def set_interval(self, ms: int):
        self._normal_interval = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def _start_poll(self):
        if self._worker_thread and self._worker_thread.isRunning():
            logger.debug("Poll already in progress, skipping")
            return

        self._cleanup_thread()

        thread = QThread()
        worker = _PollWorker(self._cred_reader, self._api_client)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_poll_success)
        worker.error.connect(self._on_poll_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        # prevent GC
        self._worker_thread = thread
        self._worker = worker

        thread.start()

    def _on_poll_success(self, data: UsageData):
        logger.info(
            "Poll OK: 5h=%.1f%% 7d=%.1f%%",
            data.five_hour_utilization,
            data.seven_day_utilization,
        )
        if self._data_store:
            try:
                self._data_store.save_snapshot(data)
            except Exception as e:
                logger.error("Failed to save snapshot: %s", e)

        self.usage_updated.emit(data)
        self._timer.setInterval(self._normal_interval)
        self._network_backoff = self.BACKOFF_NETWORK

    def _on_poll_error(self, error_type: str, message: str):
        if error_type == "auth_missing":
            logger.warning("No credentials found")
            self.auth_missing.emit()
            self._timer.setInterval(self.BACKOFF_AUTH)
        elif error_type == "auth":
            logger.warning("Auth failed: %s", message)
            self.error_occurred.emit(message)
            self._timer.setInterval(self.BACKOFF_AUTH)
        elif error_type == "rate_limit":
            logger.warning("Rate limited, backing off to 15min")
            self.error_occurred.emit(message)
            self._timer.setInterval(self.BACKOFF_RATE_LIMIT)
        else:
            logger.error("Poll error: %s", message)
            self.error_occurred.emit(message)
            self._timer.setInterval(self._network_backoff)
            self._network_backoff = min(self._network_backoff * 2, 600_000)

    def _cleanup_thread(self):
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        self._worker_thread = None
