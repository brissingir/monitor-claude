"""Main popup window — RIAS Monitor redesign."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QEvent, Signal,
)
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGraphicsDropShadowEffect, QApplication,
    QStackedWidget, QFileDialog, QMessageBox, QScrollArea,
)

from data_store import DataStore
from exporter import export_csv, export_json
from models import UsageData, AppSettings
from process_monitor import find_claude_processes, kill_process, format_uptime
from session_scanner import get_active_session_ids
from ui.data_cards import DataCardsRow
from ui.peak_monitor import PeakMonitorWidget
from ui.session_list import SessionListWidget
from ui.settings_tab import SettingsTab
from ui.tab_bar import TabBar
from ui.trend_chart import TrendChart
from ui.styles import (
    BG_BASE, BG_SURFACE, BG_ELEVATED, BG_OVERLAY,
    CRIMSON, CRIMSON_DARK, CRIMSON_LIGHT,
    EMBER, SCARLET, WARNING_AMBER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    BORDER_DEFAULT, BORDER_SUBTLE, BORDER_ACCENT,
    STATUS_ACTIVE, STATUS_WARNING, STATUS_CRITICAL, STATUS_INACTIVE,
    GLOBAL_QSS,
)


def _make_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {BORDER_SUBTLE}; max-height: 1px;")
    return sep


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold; "
        f"letter-spacing: 0.5px;"
    )
    return lbl


# ── Progress bar with gradient ────────────────────────────────────────────────

class _GradientBar(QProgressBar):
    def __init__(self, start_color: str, end_color: str, parent=None):
        super().__init__(parent)
        self.setRange(0, 1000)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(10)
        self.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 5px;
                background-color: {BG_ELEVATED};
            }}
            QProgressBar::chunk {{
                border-radius: 5px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {start_color},
                    stop:1 {end_color}
                );
            }}
        """)
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_utilization(self, percent: float):
        target = int(percent * 10)
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(target)
        self._anim.start()


# ── Usage bar widget ──────────────────────────────────────────────────────────

class UsageBarWidget(QWidget):
    def __init__(self, name: str, start_color: str, end_color: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(name)
        self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        header.addWidget(self._label)
        header.addStretch()

        self._pct_label = QLabel("—")
        self._pct_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;"
        )
        header.addWidget(self._pct_label)
        layout.addLayout(header)

        self._bar = _GradientBar(start_color, end_color)
        layout.addWidget(self._bar)

        self._reset_label = QLabel("")
        self._reset_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
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


# ── Today's Usage card ────────────────────────────────────────────────────────

class _TodayUsageCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QWidget {{ background: {BG_SURFACE}; border: 1px solid {BORDER_ACCENT}; border-radius: 6px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("TODAY'S USAGE")
        title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        self._cost_lbl = QLabel("")
        self._cost_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        title_row.addWidget(self._cost_lbl)
        layout.addLayout(title_row)

        # Token total
        self._tokens_lbl = QLabel("—")
        self._tokens_lbl.setStyleSheet(
            f"color: {CRIMSON}; font-size: 24px; font-weight: bold;"
        )
        layout.addWidget(self._tokens_lbl)

        # 2×2 breakdown grid
        grid = QHBoxLayout()
        grid.setSpacing(8)
        self._cache_read_lbl  = self._mini_stat("Cache Read")
        self._cache_write_lbl = self._mini_stat("Cache Write")
        self._input_lbl       = self._mini_stat("Input")
        self._output_lbl      = self._mini_stat("Output")
        for w in [self._cache_read_lbl, self._cache_write_lbl, self._input_lbl, self._output_lbl]:
            grid.addWidget(w)
        layout.addLayout(grid)

    def _mini_stat(self, label: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(1)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
        val = QLabel("—")
        val.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        val.setObjectName("val")
        l.addWidget(lbl)
        l.addWidget(val)
        return w

    def _get_val(self, w: QWidget) -> QLabel:
        return w.findChild(QLabel, "val")

    def update_data(self, totals: dict):
        total = totals.get("total", 0)
        self._tokens_lbl.setText(self._fmt(total) + " tokens")
        self._get_val(self._cache_read_lbl).setText(self._fmt(totals.get("cache_read", 0)))
        self._get_val(self._cache_write_lbl).setText(self._fmt(totals.get("cache_creation", 0)))
        self._get_val(self._input_lbl).setText(self._fmt(totals.get("input", 0)))
        self._get_val(self._output_lbl).setText(self._fmt(totals.get("output", 0)))

    @staticmethod
    def _fmt(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)


# ── Model breakdown bar ───────────────────────────────────────────────────────

class _ModelBreakdownBar(QWidget):
    """Stacked horizontal bar showing token proportion by model."""

    _MODEL_COLORS = [CRIMSON, EMBER, WARNING_AMBER, SCARLET, CRIMSON_LIGHT]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = _section_label("MODEL BREAKDOWN")
        layout.addWidget(lbl)

        self._bar_row = QHBoxLayout()
        self._bar_row.setContentsMargins(0, 0, 0, 0)
        self._bar_row.setSpacing(2)
        layout.addLayout(self._bar_row)

        self._legend_row = QHBoxLayout()
        self._legend_row.setContentsMargins(0, 0, 0, 0)
        self._legend_row.setSpacing(8)
        layout.addLayout(self._legend_row)

    def update_data(self, sessions):
        """Aggregate token_usage from sessions list."""
        # Clear previous
        while self._bar_row.count():
            item = self._bar_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self._legend_row.count():
            item = self._legend_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        totals: dict[str, int] = {}
        for session in sessions:
            for u in session.token_usage:
                name = u.model.replace("claude-", "").replace("-latest", "")
                totals[name] = totals.get(name, 0) + u.total_tokens

        grand = sum(totals.values())
        if grand == 0:
            placeholder = QLabel("No model data")
            placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            self._bar_row.addWidget(placeholder)
            return

        sorted_models = sorted(totals.items(), key=lambda x: -x[1])

        for i, (model, count) in enumerate(sorted_models):
            color = self._MODEL_COLORS[i % len(self._MODEL_COLORS)]
            pct = count / grand
            seg = QFrame()
            seg.setFixedHeight(14)
            seg.setStyleSheet(f"background: {color}; border-radius: 2px;")
            self._bar_row.addWidget(seg, stretch=max(1, int(pct * 100)))

            # Legend entry
            dot = QLabel("\u25A0")
            dot.setStyleSheet(f"color: {color}; font-size: 9px;")
            dot.setFixedWidth(10)
            name_lbl = QLabel(f"{model} {pct*100:.0f}%")
            name_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            self._legend_row.addWidget(dot)
            self._legend_row.addWidget(name_lbl)

        self._legend_row.addStretch()


# ── Peak hours heatmap ────────────────────────────────────────────────────────

class _PeakHoursHeatmap(QWidget):
    """24-column heatmap showing message/token activity by hour of day."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(_section_label("PEAK HOURS"))

        self._hours: list[int] = [0] * 24  # token counts per hour
        self._canvas = _HeatmapCanvas(self._hours)
        self._canvas.setFixedHeight(40)
        layout.addWidget(self._canvas)

        # Hour labels
        label_row = QHBoxLayout()
        label_row.setContentsMargins(0, 0, 0, 0)
        for text in ["12a", "6a", "12p", "6p", "12a"]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_row.addWidget(lbl, stretch=1 if text not in ("12a",) else 0)
        layout.addLayout(label_row)

    def update_data(self, sessions):
        self._hours = [0] * 24
        for session in sessions:
            for usage in session.token_usage:
                if session.started_at:
                    hour = session.started_at.astimezone().hour
                    self._hours[hour] += usage.total_tokens
        self._canvas.set_data(self._hours)
        self._canvas.update()


class _HeatmapCanvas(QWidget):
    def __init__(self, hours: list[int], parent=None):
        super().__init__(parent)
        self._hours = hours
        self.setMinimumWidth(100)

    def set_data(self, hours: list[int]):
        self._hours = hours

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cell_w = w / 24
        max_val = max(self._hours) if any(self._hours) else 1

        for i, val in enumerate(self._hours):
            intensity = val / max_val if max_val > 0 else 0
            color = QColor(CRIMSON)
            color.setAlphaF(max(0.08, intensity * 0.9))
            painter.setBrush(color)
            painter.setPen(QPen(QColor(BORDER_SUBTLE), 1))
            x = int(i * cell_w)
            cw = max(1, int(cell_w) - 1)
            painter.drawRoundedRect(x, 2, cw, h - 4, 2, 2)
        painter.end()


# ── Live pulse dot ────────────────────────────────────────────────────────────

class _PulseDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._bright = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start(800)

    def _pulse(self):
        self._bright = not self._bright
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(CRIMSON if self._bright else CRIMSON_DARK)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 8, 8)
        painter.end()


# ── Main popup window ─────────────────────────────────────────────────────────

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
        self.setFixedWidth(560)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)

        self._container = QWidget(self)
        self._container.setGraphicsEffect(shadow)
        self._container.setStyleSheet(GLOBAL_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(self._container)

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        logo = QLabel("RIAS")
        logo.setStyleSheet(
            f"color: {CRIMSON}; font-size: 16px; font-weight: bold; letter-spacing: 2px;"
        )
        header.addWidget(logo)

        monitor_lbl = QLabel("Monitor")
        monitor_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px;")
        header.addWidget(monitor_lbl)

        self._pulse_dot = _PulseDot()
        header.addWidget(self._pulse_dot)

        header.addStretch()

        self._plan_badge = QLabel("Pro")
        self._plan_badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: bold; "
            f"background: {BG_ELEVATED}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 8px; padding: 2px 8px;"
        )
        header.addWidget(self._plan_badge)

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip("Close")
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {TEXT_MUTED}; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        main_layout.addLayout(header)

        sep = _make_separator()
        main_layout.addWidget(sep)

        # ── Tab Bar ───────────────────────────────────────────────────────────
        self._tab_bar = TabBar(["Dashboard", "Sessions", "Processes", "Config"])
        self._tab_bar.tab_changed.connect(self._on_tab_changed)
        main_layout.addWidget(self._tab_bar)

        # ── Stacked pages ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        self._stack.addWidget(self._build_dashboard_tab())
        self._stack.addWidget(self._build_sessions_tab())
        self._stack.addWidget(self._build_processes_tab())
        self._stack.addWidget(self._build_config_tab())

        # Countdown refresh timer (every minute)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._refresh_countdowns)
        self._countdown_timer.start(60_000)

        self._last_data: UsageData | None = None
        self._from_cache = False

        if QApplication.instance():
            QApplication.instance().installEventFilter(self)

    # ── Build tabs ────────────────────────────────────────────────────────────

    def _build_dashboard_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(12)

        # Quota bars
        layout.addWidget(_section_label("QUOTAS"))

        self._five_hour_bar = UsageBarWidget("5-Hour Session", CRIMSON, SCARLET)
        layout.addWidget(self._five_hour_bar)

        self._seven_day_bar = UsageBarWidget("7-Day Usage", EMBER, WARNING_AMBER)
        layout.addWidget(self._seven_day_bar)

        self._sonnet_bar = UsageBarWidget("7-Day Sonnet", CRIMSON, EMBER)
        self._sonnet_bar.hide()
        layout.addWidget(self._sonnet_bar)

        self._opus_bar = UsageBarWidget("7-Day Opus", CRIMSON, SCARLET)
        self._opus_bar.hide()
        layout.addWidget(self._opus_bar)

        self._extra_bar = UsageBarWidget("Extra Usage", WARNING_AMBER, SCARLET)
        self._extra_bar.hide()
        layout.addWidget(self._extra_bar)

        layout.addWidget(_make_separator())

        # Today's Usage card
        self._today_card = _TodayUsageCard()
        layout.addWidget(self._today_card)

        layout.addWidget(_make_separator())

        # Trend chart
        self._trend_chart = TrendChart()
        layout.addWidget(self._trend_chart)

        layout.addWidget(_make_separator())

        # Peak Monitor
        self._peak_monitor = PeakMonitorWidget()
        layout.addWidget(self._peak_monitor)

        # Footer
        footer = QHBoxLayout()
        self._status_label = QLabel("Loading...")
        self._status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        footer.addWidget(self._status_label)
        footer.addStretch()

        refresh_btn = QPushButton("\u21bb")
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._on_refresh)
        footer.addWidget(refresh_btn)
        layout.addLayout(footer)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_sessions_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 4, 4)
        layout.setSpacing(10)

        # Data cards
        self._data_cards = DataCardsRow()
        layout.addWidget(self._data_cards)

        layout.addWidget(_make_separator())

        # Model breakdown
        self._model_breakdown = _ModelBreakdownBar()
        layout.addWidget(self._model_breakdown)

        layout.addWidget(_make_separator())

        # Sessions header + export buttons
        sess_header = QHBoxLayout()
        sess_header.addWidget(_section_label("RECENT SESSIONS"))
        sess_header.addStretch()

        export_csv_btn = QPushButton("CSV")
        export_csv_btn.setFixedSize(38, 22)
        export_csv_btn.setToolTip("Export sessions to CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        sess_header.addWidget(export_csv_btn)

        export_json_btn = QPushButton("JSON")
        export_json_btn.setFixedSize(44, 22)
        export_json_btn.setToolTip("Export sessions to JSON")
        export_json_btn.clicked.connect(self._export_json)
        sess_header.addWidget(export_json_btn)

        layout.addLayout(sess_header)

        self._session_list = SessionListWidget()
        layout.addWidget(self._session_list)

        layout.addWidget(_make_separator())

        # Peak hours heatmap
        self._heatmap = _PeakHoursHeatmap()
        layout.addWidget(self._heatmap)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_processes_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Header
        proc_header = QHBoxLayout()
        proc_header.addWidget(_section_label("CLAUDE PROCESSES"))
        proc_header.addStretch()

        self._end_all_btn = QPushButton("End All")
        self._end_all_btn.setFixedHeight(26)
        self._end_all_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {SCARLET}; "
            f"color: {SCARLET}; border-radius: 4px; padding: 2px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {SCARLET}; color: {TEXT_PRIMARY}; }}"
        )
        self._end_all_btn.clicked.connect(self._end_all_processes)
        proc_header.addWidget(self._end_all_btn)

        proc_refresh_btn = QPushButton("\u21bb")
        proc_refresh_btn.setFixedSize(26, 26)
        proc_refresh_btn.setToolTip("Refresh processes")
        proc_refresh_btn.clicked.connect(self._refresh_processes)
        proc_header.addWidget(proc_refresh_btn)

        layout.addLayout(proc_header)

        self._process_container = QVBoxLayout()
        self._process_container.setSpacing(4)
        layout.addLayout(self._process_container)
        layout.addStretch()

        # Initial populate
        self._populate_processes()
        return page

    def _build_config_tab(self) -> QWidget:
        self._settings_tab = SettingsTab(self._settings)
        self._settings_tab.settings_changed.connect(self._on_settings_changed)
        return self._settings_tab

    # ── Public interface (signals from backend) ───────────────────────────────

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

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = self._container.geometry().adjusted(-1, -1, 1, 1)
        path.addRoundedRect(
            float(rect.x()), float(rect.y()),
            float(rect.width()), float(rect.height()), 10, 10,
        )
        painter.fillPath(path, QColor(BG_BASE))
        painter.setPen(QColor(BORDER_DEFAULT))
        painter.drawPath(path)

    def eventFilter(self, obj, event):
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
        # Fade-in: store on self so Python doesn't GC it before the 150ms complete
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(150)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        self._stack.setCurrentIndex(index)
        if index == 1:
            self._refresh_dashboard()
        elif index == 2:
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
            self, "Export CSV",
            str(Path.home() / "Desktop" / "claude_sessions.csv"),
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
            self, "Export JSON",
            str(Path.home() / "Desktop" / "claude_sessions.json"),
            "JSON Files (*.json)",
        )
        if path:
            export_json(sessions, Path(path))

    def _refresh_processes(self):
        self._populate_processes()

    def _populate_processes(self):
        while self._process_container.count():
            item = self._process_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        procs = find_claude_processes()
        self._end_all_btn.setEnabled(bool(procs))

        if not procs:
            lbl = QLabel("No Claude processes running")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._process_container.addWidget(lbl)
            return

        for p in procs:
            row_w = QWidget()
            row_w.setStyleSheet(
                f"QWidget {{ background: {BG_SURFACE}; border: 1px solid {BORDER_DEFAULT}; border-radius: 4px; }}"
                f"QLabel {{ border: none; background: transparent; }}"
                f"QPushButton {{ border: none; background: transparent; }}"
            )
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(8, 6, 8, 6)
            row_l.setSpacing(8)

            dot = QLabel("\u25CF")
            dot.setStyleSheet(f"color: {STATUS_ACTIVE}; font-size: 10px;")
            dot.setFixedWidth(12)
            row_l.addWidget(dot)

            info = QLabel(f"PID {p.pid}  {p.memory_mb:.0f} MB  {format_uptime(p.uptime_seconds)}")
            info.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px;")
            row_l.addWidget(info, stretch=1)

            if hasattr(p, "cwd") and p.cwd:
                cwd = str(p.cwd)
                if len(cwd) > 30:
                    cwd = "…" + cwd[-28:]
                cwd_lbl = QLabel(cwd)
                cwd_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
                row_l.addWidget(cwd_lbl)

            kill_btn = QPushButton("\u2715")
            kill_btn.setFixedSize(20, 20)
            kill_btn.setToolTip(f"Terminate PID {p.pid}")
            kill_btn.setStyleSheet(
                f"QPushButton {{ color: {TEXT_MUTED}; font-size: 12px; }}"
                f"QPushButton:hover {{ color: {SCARLET}; }}"
            )
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
            self._populate_processes()

    def _end_all_processes(self):
        procs = find_claude_processes()
        if not procs:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Terminate all {len(procs)} Claude processes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for p in procs:
                kill_process(p.pid)
            self._populate_processes()

    def _refresh_dashboard(self):
        if not self._data_store:
            return

        range_hours = self._trend_chart.range_hours
        since = datetime.now(timezone.utc) - timedelta(hours=range_hours)
        snapshots = self._data_store.get_snapshots_since(since)
        self._trend_chart.update_data(snapshots)

        today_totals = self._data_store.get_today_token_totals()
        self._today_card.update_data(today_totals)

        active_ids = get_active_session_ids()
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        week_count = self._data_store.get_session_count_since(week_start)
        self._data_cards.update_data(
            total_tokens=today_totals["total"],
            active_count=len(active_ids),
            week_count=week_count,
        )

        sessions = self._data_store.get_recent_sessions(20)
        self._session_list.update_sessions(sessions, active_ids)
        self._model_breakdown.update_data(sessions)
        self._heatmap.update_data(sessions)

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
