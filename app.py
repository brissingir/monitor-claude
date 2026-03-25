from datetime import datetime, timezone

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from autostart import install, uninstall, is_installed
from config import AppConfig
from models import AppSettings, UsageData
from polling_service import PollingService
from ui.popup_window import MainPopupWindow
from ui.settings_dialog import SettingsDialog
from ui.styles import CRIMSON, ROYAL_BLUE, TEXT_PRIMARY, BG_SURFACE, WARNING_ORANGE, CRITICAL_RED


class SystemTrayApp:
    def __init__(self):
        self._config = AppConfig()
        self._settings = self._config.load()
        self._last_data: UsageData | None = None
        self._last_notified_warning = False
        self._last_notified_critical = False

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

        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

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

        # Popup
        self._popup = MainPopupWindow(
            on_settings_clicked=self._open_settings,
            on_refresh_clicked=self._on_refresh,
        )

        # Polling
        self._polling = PollingService(self._settings.poll_interval_seconds * 1000)
        self._polling.usage_updated.connect(self._on_usage_updated)
        self._polling.error_occurred.connect(self._on_error)
        self._polling.auth_missing.connect(self._on_auth_missing)

    def start(self):
        self._tray.show()
        self._polling.start()

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

    def _on_usage_updated(self, data: UsageData):
        self._last_data = data
        pct = f"{data.five_hour_utilization:.0f}"
        self._tray.setIcon(self._make_icon(pct, data.five_hour_utilization))
        self._tray.setToolTip(
            f"Claude Usage\n"
            f"5h: {data.five_hour_utilization:.0f}%  |  7d: {data.seven_day_utilization:.0f}%"
        )
        self._popup.update_usage(data)
        self._check_notifications(data)

    def _on_error(self, message: str):
        self._tray.setToolTip(f"Claude Usage\n{message}")
        self._popup.set_error(message)

    def _on_auth_missing(self):
        self._tray.setIcon(self._make_icon("—"))
        self._tray.setToolTip("Claude Usage\nNot logged in to Claude Code")
        self._popup.set_auth_missing()

    def _on_refresh(self):
        self._polling.refresh_now()

    def _toggle_autostart(self, checked: bool):
        if checked:
            install()
        else:
            uninstall()
        self._autostart_action.setChecked(is_installed())

    def _open_settings(self):
        dialog = SettingsDialog(self._settings)
        if dialog.exec():
            new_settings = dialog.get_settings()
            if new_settings:
                self._settings = new_settings
                self._config.save(new_settings)
                self._polling.set_interval(new_settings.poll_interval_seconds * 1000)

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

    @staticmethod
    def _make_icon(text: str = "", utilization: float = 0) -> QIcon:
        size = 64
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background — rounded square with Crimson base
        painter.setBrush(QColor(CRIMSON))
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 14, 14)

        # Royal Blue accent stripe on the right edge
        painter.setBrush(QColor(ROYAL_BLUE))
        painter.drawRoundedRect(size - 14, 2, 12, size - 4, 6, 6)

        # "C" letter
        painter.setPen(QColor(TEXT_PRIMARY))
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size - 6, size, 0x0084, "C")  # AlignCenter

        painter.end()
        return QIcon(pixmap)
