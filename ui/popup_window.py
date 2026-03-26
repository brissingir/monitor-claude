from datetime import datetime, timezone, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QEvent, Signal
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGraphicsDropShadowEffect, QApplication,
    QStackedWidget, QFileDialog, QMessageBox,
)

from data_store import DataStore
from exporter import export_csv, export_json
from models import UsageData, AppSettings
from process_monitor import find_claude_processes, kill_process, format_uptime
from session_scanner import get_active_session_ids
from ui.data_cards import DataCardsRow
from ui.session_list import SessionListWidget
from ui.settings_tab import SettingsTab
from ui.tab_bar import TabBar
from ui.trend_chart import TrendChart
from ui.styles import (
    BG_BLACK, BG_SURFACE, CRIMSON, ROYAL_BLUE, WARNING_ORANGE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BORDER_COLOR, GLOBAL_QSS,
    ICON_GREEN,
)


class StyledProgressBar(QProgressBar):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setRange(0, 1000)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(22)
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                background-color: {BG_SURFACE};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(400)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_utilization(self, percent: float):
        target = int(percent * 10)
        self._animation.stop()
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(target)
        self._animation.start()


class UsageBarWidget(QWidget):
    def __init__(self, name: str, color: str, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(name)
        self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._pct_label = QLabel("—")
        self._pct_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;")
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._label)
        header.addStretch()
        header.addWidget(self._pct_label)
        layout.addLayout(header)

        self._bar = StyledProgressBar(color)
        layout.addWidget(self._bar)

        self._reset_label = QLabel("")
        self._reset_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._reset_label)

    def update_data(self, utilization: float, resets_at: datetime | None):
        self._pct_label.setText(f"{utilization:.0f}%")
        self._bar.set_utilization(utilization)
        self._reset_label.setText(self._format_countdown(resets_at))

    @staticmethod
    def _format_countdown(resets_at: datetime | None) -> str:
        if not resets_at:
            return ""
        now = datetime.now(timezone.utc)
        delta = resets_at - now
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "Resetting soon..."
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        if days > 0:
            return f"Resets in {days}d {hours}h"
        if hours > 0:
            return f"Resets in {hours}h {minutes}m"
        return f"Resets in {minutes}m"


class MainPopupWindow(QWidget):
    settings_changed = Signal(object)  # emits AppSettings

    def __init__(
        self,
        on_settings_clicked,
        on_refresh_clicked,
        data_store: DataStore | None = None,
        settings: AppSettings | None = None,
    ):
        super().__init__()
        self._on_refresh = on_refresh_clicked
        self._data_store = data_store
        self._settings = settings or AppSettings()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(420)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 2)

        self._container = QWidget(self)
        self._container.setGraphicsEffect(shadow)
        self._container.setStyleSheet(GLOBAL_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(self._container)

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Claude Usage")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(28, 28)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        main_layout.addLayout(header)

        # Tab Bar
        self._tab_bar = TabBar(["Usage", "Sessions", "Config"])
        self._tab_bar.tab_changed.connect(self._on_tab_changed)
        main_layout.addWidget(self._tab_bar)

        # Stacked pages
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        # === Tab 0: Usage ===
        usage_page = QWidget()
        usage_layout = QVBoxLayout(usage_page)
        usage_layout.setContentsMargins(0, 4, 0, 0)
        usage_layout.setSpacing(10)

        self._five_hour_bar = UsageBarWidget("5-Hour Session", CRIMSON)
        usage_layout.addWidget(self._five_hour_bar)

        self._seven_day_bar = UsageBarWidget("7-Day Usage", ROYAL_BLUE)
        usage_layout.addWidget(self._seven_day_bar)

        # Optional model bars
        self._sonnet_bar = UsageBarWidget("7-Day Sonnet", ROYAL_BLUE)
        self._sonnet_bar.hide()
        usage_layout.addWidget(self._sonnet_bar)

        self._opus_bar = UsageBarWidget("7-Day Opus", CRIMSON)
        self._opus_bar.hide()
        usage_layout.addWidget(self._opus_bar)

        # Extra usage bar
        self._extra_bar = UsageBarWidget("Extra Usage", WARNING_ORANGE)
        self._extra_bar.hide()
        usage_layout.addWidget(self._extra_bar)

        usage_layout.addWidget(self._make_separator())

        # Trend chart
        self._trend_chart = TrendChart()
        usage_layout.addWidget(self._trend_chart)

        # Footer with status
        footer = QHBoxLayout()
        self._status_label = QLabel("Loading...")
        self._status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        footer.addWidget(self._status_label)
        footer.addStretch()

        refresh_btn = QPushButton("\u21bb")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._on_refresh)
        footer.addWidget(refresh_btn)
        usage_layout.addLayout(footer)

        self._stack.addWidget(usage_page)

        # === Tab 1: Sessions ===
        sessions_page = QWidget()
        sessions_layout = QVBoxLayout(sessions_page)
        sessions_layout.setContentsMargins(0, 4, 0, 0)
        sessions_layout.setSpacing(8)

        self._data_cards = DataCardsRow()
        sessions_layout.addWidget(self._data_cards)

        sessions_layout.addWidget(self._make_separator())

        sessions_header = QHBoxLayout()
        sessions_title = QLabel("Recent Sessions")
        sessions_title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        sessions_header.addWidget(sessions_title)
        sessions_header.addStretch()

        # Export buttons
        export_csv_btn = QPushButton("CSV")
        export_csv_btn.setFixedSize(40, 22)
        export_csv_btn.setToolTip("Export sessions to CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        sessions_header.addWidget(export_csv_btn)

        export_json_btn = QPushButton("JSON")
        export_json_btn.setFixedSize(46, 22)
        export_json_btn.setToolTip("Export sessions to JSON")
        export_json_btn.clicked.connect(self._export_json)
        sessions_header.addWidget(export_json_btn)

        sessions_layout.addLayout(sessions_header)

        self._session_list = SessionListWidget()
        sessions_layout.addWidget(self._session_list)

        sessions_layout.addWidget(self._make_separator())

        # Process monitor section
        proc_header = QHBoxLayout()
        proc_title = QLabel("Claude Processes")
        proc_title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        proc_header.addWidget(proc_title)
        proc_header.addStretch()

        proc_refresh_btn = QPushButton("\u21bb")
        proc_refresh_btn.setFixedSize(22, 22)
        proc_refresh_btn.setToolTip("Refresh processes")
        proc_refresh_btn.clicked.connect(self._refresh_processes)
        proc_header.addWidget(proc_refresh_btn)
        sessions_layout.addLayout(proc_header)

        self._process_container = QVBoxLayout()
        self._process_container.setSpacing(4)
        self._no_proc_label = QLabel("No Claude processes running")
        self._no_proc_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._no_proc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._process_container.addWidget(self._no_proc_label)
        sessions_layout.addLayout(self._process_container)

        self._stack.addWidget(sessions_page)

        # === Tab 2: Config ===
        self._settings_tab = SettingsTab(self._settings)
        self._settings_tab.settings_changed.connect(self._on_settings_changed)
        self._stack.addWidget(self._settings_tab)

        # Countdown refresh timer
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._refresh_countdowns)
        self._countdown_timer.start(60_000)

        self._last_data: UsageData | None = None
        self._from_cache = False

        # Click-outside detection
        if QApplication.instance():
            QApplication.instance().installEventFilter(self)

    def update_usage(self, data: UsageData, from_cache: bool = False):
        self._last_data = data
        self._from_cache = from_cache
        self._five_hour_bar.update_data(data.five_hour_utilization, data.five_hour_resets_at)
        self._seven_day_bar.update_data(data.seven_day_utilization, data.seven_day_resets_at)

        if data.seven_day_sonnet_utilization is not None:
            self._sonnet_bar.show()
            self._sonnet_bar.update_data(data.seven_day_sonnet_utilization, None)
        else:
            self._sonnet_bar.hide()

        if data.seven_day_opus_utilization is not None:
            self._opus_bar.show()
            self._opus_bar.update_data(data.seven_day_opus_utilization, None)
        else:
            self._opus_bar.hide()

        # Extra usage bar
        if data.extra_usage_enabled and data.extra_usage_utilization is not None:
            self._extra_bar.show()
            self._extra_bar.update_data(data.extra_usage_utilization, None)
        else:
            self._extra_bar.hide()

        self._update_status_text(data)
        self._refresh_dashboard()

    def refresh_sessions(self):
        self._refresh_dashboard()

    def load_settings(self, settings: AppSettings):
        self._settings = settings
        self._settings_tab.load_settings(settings)

    def set_error(self, message: str):
        self._status_label.setText(message)
        self._status_label.setStyleSheet(f"color: {CRIMSON}; font-size: 11px;")

    def set_auth_missing(self):
        self._status_label.setText("Not logged in to Claude Code")
        self._status_label.setStyleSheet(f"color: {CRIMSON}; font-size: 11px;")
        self._five_hour_bar.update_data(0, None)
        self._seven_day_bar.update_data(0, None)

    def position_near_tray(self, tray_geometry):
        if tray_geometry and not tray_geometry.isNull():
            x = tray_geometry.x() - self.width() // 2
            y = tray_geometry.y() - self.height() - 8
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.right() - self.width() - 10
                y = geo.bottom() - self.height() - 10
            else:
                x, y = 100, 100

        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = max(avail.left(), min(x, avail.right() - self.width()))
            y = max(avail.top(), min(y, avail.bottom() - self.height()))

        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = self._container.geometry().adjusted(-1, -1, 1, 1)
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()), 10, 10)
        painter.fillPath(path, QColor(BG_BLACK))
        painter.setPen(QColor(BORDER_COLOR))
        painter.drawPath(path)

    def eventFilter(self, obj, event):
        """Hide popup when clicking outside of it."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self.isVisible()
            and not self.geometry().contains(event.globalPosition().toPoint())
        ):
            self.hide()
        return False

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self._refresh_dashboard()

    def _on_tab_changed(self, index: int):
        self._stack.setCurrentIndex(index)
        if index == 1:  # Sessions tab
            self._refresh_dashboard()
            self._refresh_processes()

    def _on_settings_changed(self, new_settings: AppSettings):
        self._settings = new_settings
        self.settings_changed.emit(new_settings)

    def _export_csv(self):
        if not self._data_store:
            return
        sessions = self._data_store.get_recent_sessions(100)
        if not sessions:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", str(Path.home() / "Desktop" / "claude_sessions.csv"),
            "CSV Files (*.csv)",
        )
        if path:
            export_csv(sessions, Path(path))

    def _export_json(self):
        if not self._data_store:
            return
        sessions = self._data_store.get_recent_sessions(100)
        if not sessions:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", str(Path.home() / "Desktop" / "claude_sessions.json"),
            "JSON Files (*.json)",
        )
        if path:
            export_json(sessions, Path(path))

    def _refresh_processes(self):
        # Clear old widgets
        while self._process_container.count():
            item = self._process_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        procs = find_claude_processes()
        if not procs:
            lbl = QLabel("No Claude processes running")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._process_container.addWidget(lbl)
            return

        for p in procs:
            row_w = QWidget()
            row_w.setStyleSheet(
                f"background: {BG_SURFACE}; border: 1px solid {BORDER_COLOR}; border-radius: 4px;"
            )
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(8, 4, 8, 4)
            row_l.setSpacing(6)

            # Green dot + PID
            dot = QLabel("\u25CF")
            dot.setStyleSheet(f"color: {ICON_GREEN}; font-size: 10px; border: none; background: transparent;")
            dot.setFixedWidth(14)
            row_l.addWidget(dot)

            info = QLabel(f"PID {p.pid}  {p.memory_mb:.0f}MB  {format_uptime(p.uptime_seconds)}")
            info.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px; border: none; background: transparent;")
            row_l.addWidget(info, stretch=1)

            kill_btn = QPushButton("\u2715")
            kill_btn.setFixedSize(20, 20)
            kill_btn.setToolTip(f"Terminate PID {p.pid}")
            kill_btn.clicked.connect(lambda checked, pid=p.pid: self._kill_process(pid))
            row_l.addWidget(kill_btn)

            self._process_container.addWidget(row_w)

    def _kill_process(self, pid: int):
        reply = QMessageBox.question(
            self, "Confirm", f"Terminate Claude process PID {pid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            kill_process(pid)
            self._refresh_processes()

    def _refresh_dashboard(self):
        if not self._data_store:
            return

        # Update trend chart
        range_hours = self._trend_chart.range_hours
        since = datetime.now(timezone.utc) - timedelta(hours=range_hours)
        snapshots = self._data_store.get_snapshots_since(since)
        self._trend_chart.update_data(snapshots)

        # Update data cards
        today_totals = self._data_store.get_today_token_totals()
        active_ids = get_active_session_ids()
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        week_count = self._data_store.get_session_count_since(week_start)
        self._data_cards.update_data(
            total_tokens=today_totals["total"],
            active_count=len(active_ids),
            week_count=week_count,
        )

        # Update session list
        sessions = self._data_store.get_recent_sessions(20)
        self._session_list.update_sessions(sessions, active_ids)

    def _update_status_text(self, data: UsageData):
        now = datetime.now(timezone.utc)
        delta = now - data.fetched_at
        secs = int(delta.total_seconds())
        if secs < 60:
            text = "Updated just now"
        elif secs < 3600:
            text = f"Updated {secs // 60}m ago"
        else:
            text = f"Updated {secs // 3600}h ago"

        if self._from_cache:
            text = f"Cached — {text.lower()}"

        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

    def _refresh_countdowns(self):
        if self._last_data:
            self._five_hour_bar.update_data(
                self._last_data.five_hour_utilization,
                self._last_data.five_hour_resets_at,
            )
            self._seven_day_bar.update_data(
                self._last_data.seven_day_utilization,
                self._last_data.seven_day_resets_at,
            )
            self._update_status_text(self._last_data)

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR}; max-height: 1px;")
        return sep
