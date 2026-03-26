import logging
from datetime import datetime, timezone, timedelta

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from autostart import install, uninstall, is_installed
from config import AppConfig
from data_store import DataStore
from hotkey import GlobalHotkey
from models import AppSettings, UsageData
from polling_service import PollingService
from session_scanner import SessionScanner
from ui.popup_window import MainPopupWindow
from ui.styles import (
    CRIMSON, ROYAL_BLUE, TEXT_PRIMARY, BG_SURFACE,
    WARNING_ORANGE, CRITICAL_RED, ICON_GREEN,
)

logger = logging.getLogger("monitor.app")


class SystemTrayApp:
    def __init__(self):
        self._config = AppConfig()
        self._settings = self._config.load()
        self._last_data: UsageData | None = None
        self._last_notified_warning = False
        self._last_notified_critical = False

        # Data store
        self._data_store = DataStore(self._config.data_dir / "usage_history.db")

        # Tray icon
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(self._make_icon("—"))
        self._tray.setToolTip("Claude Usage Monitor\nLoading...")
        self._tray.activated.connect(self._on_tray_activated)

        # Context menu
        menu = QMenu()
        refresh_action = QAction("Refresh Now", menu)
        refresh_action.triggered.connect(self._on_refresh)
        menu.addAction(refresh_action)

        self._autostart_action = QAction("Start with Windows", menu)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(is_installed())
        self._autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self._autostart_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

        # Popup (with inline settings — no separate dialog)
        self._popup = MainPopupWindow(
            on_settings_clicked=lambda: None,  # unused now
            on_refresh_clicked=self._on_refresh,
            data_store=self._data_store,
            settings=self._settings,
        )
        self._popup.settings_changed.connect(self._on_settings_changed)

        # Polling (with data store for persistence)
        self._polling = PollingService(
            self._settings.poll_interval_seconds * 1000,
            data_store=self._data_store,
        )
        self._polling.usage_updated.connect(self._on_usage_updated)
        self._polling.error_occurred.connect(self._on_error)
        self._polling.auth_missing.connect(self._on_auth_missing)

        # Session scanner (separate timer, default 5 min)
        self._scanner = SessionScanner(
            self._data_store,
            scan_interval_ms=300_000,
        )
        self._scanner.scan_completed.connect(self._on_scan_completed)

        # Global hotkey (Ctrl+Shift+C)
        self._hotkey = GlobalHotkey()
        self._hotkey.activated.connect(self._toggle_popup)

    def start(self):
        self._tray.show()
        self._load_cached_data()
        self._polling.start()
        self._scanner.start()
        self._hotkey.start()

    def _load_cached_data(self):
        cached = self._data_store.get_latest_snapshot()
        if cached:
            logger.info("Loaded cached snapshot from %s", cached.fetched_at.isoformat())
            self._on_usage_updated(cached, from_cache=True)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_popup()

    def _toggle_popup(self):
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._popup.position_near_tray(self._tray.geometry())
            self._popup.show()
            self._popup.activateWindow()

    def _on_usage_updated(self, data: UsageData, from_cache: bool = False):
        self._last_data = data
        max_util = max(data.five_hour_utilization, data.seven_day_utilization)
        pct = f"{data.five_hour_utilization:.0f}"
        self._tray.setIcon(self._make_icon(pct, max_util))
        spark = self._make_sparkline()
        self._tray.setToolTip(
            f"Claude Usage\n"
            f"5h: {data.five_hour_utilization:.0f}%  |  7d: {data.seven_day_utilization:.0f}%"
            + (f"\n{spark}" if spark else "")
        )
        self._popup.update_usage(data, from_cache=from_cache)
        if not from_cache:
            self._check_notifications(data)

    def _on_error(self, message: str):
        logger.warning("Error displayed: %s", message)
        self._tray.setToolTip(f"Claude Usage\n{message}")
        self._popup.set_error(message)

    def _on_auth_missing(self):
        self._tray.setIcon(self._make_icon("—"))
        self._tray.setToolTip("Claude Usage\nNot logged in to Claude Code")
        self._popup.set_auth_missing()

    def _on_scan_completed(self, updated: int):
        if updated > 0:
            logger.info("Session scan found %d updates", updated)
            self._popup.refresh_sessions()

    def _on_refresh(self):
        self._polling.refresh_now()

    def _on_settings_changed(self, new_settings: AppSettings):
        logger.info("Settings updated via inline tab")
        self._settings = new_settings
        self._config.save(new_settings)
        self._polling.set_interval(new_settings.poll_interval_seconds * 1000)

    def _toggle_autostart(self, checked: bool):
        if checked:
            install()
        else:
            uninstall()
        self._autostart_action.setChecked(is_installed())

    def _check_notifications(self, data: UsageData):
        if not self._settings.notifications_enabled:
            return

        max_util = max(data.five_hour_utilization, data.seven_day_utilization)

        if max_util >= self._settings.critical_threshold and not self._last_notified_critical:
            self._tray.showMessage(
                "Claude Usage — Critical",
                f"5h: {data.five_hour_utilization:.0f}%  |  7d: {data.seven_day_utilization:.0f}%",
                QSystemTrayIcon.MessageIcon.Critical,
                5000,
            )
            self._last_notified_critical = True
            self._last_notified_warning = True
        elif max_util >= self._settings.warning_threshold and not self._last_notified_warning:
            self._tray.showMessage(
                "Claude Usage — Warning",
                f"5h: {data.five_hour_utilization:.0f}%  |  7d: {data.seven_day_utilization:.0f}%",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
            self._last_notified_warning = True

        if max_util < self._settings.warning_threshold:
            self._last_notified_warning = False
            self._last_notified_critical = False
        elif max_util < self._settings.critical_threshold:
            self._last_notified_critical = False

    def _make_sparkline(self, count: int = 12) -> str:
        """Generate a Unicode sparkline from the last `count` snapshots."""
        blocks = " ▁▂▃▄▅▆▇█"
        since = datetime.now(timezone.utc) - timedelta(hours=count)
        snapshots = self._data_store.get_snapshots_since(since)
        if len(snapshots) < 2:
            return ""
        # Use the max utilization (5h or 7d) for each point
        values = [max(s.five_hour_utilization, s.seven_day_utilization) for s in snapshots[-count:]]
        max_val = max(values) if values else 1
        if max_val == 0:
            return "".join(blocks[0] for _ in values)
        return "".join(blocks[min(8, int(v / max_val * 8))] for v in values)

    @staticmethod
    def _make_icon(text: str = "", utilization: float = 0) -> QIcon:
        size = 64
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dynamic background color based on utilization
        if utilization >= 90:
            bg_color = CRITICAL_RED
        elif utilization >= 70:
            bg_color = WARNING_ORANGE
        else:
            bg_color = ICON_GREEN

        # Background — rounded square
        painter.setBrush(QColor(bg_color))
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 14, 14)

        # Accent stripe on the right edge
        painter.setBrush(QColor(ROYAL_BLUE))
        painter.drawRoundedRect(size - 14, 2, 12, size - 4, 6, 6)

        # "C" letter
        painter.setPen(QColor(TEXT_PRIMARY))
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size - 6, size, 0x0084, "C")  # AlignCenter

        painter.end()
        return QIcon(pixmap)
