from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPainterPath, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGraphicsDropShadowEffect,
)

from models import UsageData
from ui.styles import (
    BG_BLACK, BG_SURFACE, CRIMSON, ROYAL_BLUE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BORDER_COLOR, GLOBAL_QSS,
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
    def __init__(self, on_settings_clicked, on_refresh_clicked):
        super().__init__()
        self._on_settings = on_settings_clicked
        self._on_refresh = on_refresh_clicked

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(340)

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
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Claude Usage")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        settings_btn = QPushButton("\u2699")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._on_settings)
        header.addWidget(settings_btn)

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(28, 28)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        main_layout.addLayout(header)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"color: {BORDER_COLOR}; max-height: 1px;")
        main_layout.addWidget(sep1)

        # Usage bars
        self._five_hour_bar = UsageBarWidget("5-Hour Session", CRIMSON)
        main_layout.addWidget(self._five_hour_bar)

        self._seven_day_bar = UsageBarWidget("7-Day Usage", ROYAL_BLUE)
        main_layout.addWidget(self._seven_day_bar)

        # Optional bars (hidden by default)
        self._sonnet_bar = UsageBarWidget("7-Day Sonnet", ROYAL_BLUE)
        self._sonnet_bar.hide()
        main_layout.addWidget(self._sonnet_bar)

        self._opus_bar = UsageBarWidget("7-Day Opus", CRIMSON)
        self._opus_bar.hide()
        main_layout.addWidget(self._opus_bar)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {BORDER_COLOR}; max-height: 1px;")
        main_layout.addWidget(sep2)

        # Footer
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
        main_layout.addLayout(footer)

        # Countdown refresh timer
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._refresh_countdowns)
        self._countdown_timer.start(60_000)

        self._last_data: UsageData | None = None

    def update_usage(self, data: UsageData):
        self._last_data = data
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

        self._update_status_text(data)
        self.adjustSize()

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
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.right() - self.width() - 10
                y = geo.bottom() - self.height() - 10
            else:
                x, y = 100, 100

        from PySide6.QtWidgets import QApplication
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

    def focusOutEvent(self, event):
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()

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
