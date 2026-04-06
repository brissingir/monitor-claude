from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QPointF, QMargins
from PySide6.QtGui import QPainter as _QPainter
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis,
)
from PySide6.QtGui import QColor, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

from models import UsageData
from ui.styles import (
    BG_BASE, BG_SURFACE, BG_ELEVATED,
    CRIMSON, CRIMSON_LIGHT, EMBER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_DEFAULT, BORDER_SUBTLE,
)


class TrendChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._range_hours = 24 * 7  # default 7 days

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with label + range selector
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Usage Trend")
        title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        # Pill-style range buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)
        self._range_btns: list[QPushButton] = []
        for label, hours in [("24h", 24), ("7d", 24 * 7), ("30d", 24 * 30)]:
            btn = QPushButton(label)
            btn.setFixedHeight(20)
            btn.setFixedWidth(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, h=hours: self._set_range(h))
            btn_row.addWidget(btn)
            self._range_btns.append(btn)

        header.addLayout(btn_row)
        layout.addLayout(header)

        # Legend
        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(12)
        for color, label in [(CRIMSON_LIGHT, "5h Session"), (EMBER, "7d Usage")]:
            dot = QLabel("─")
            dot.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
            dot.setFixedWidth(16)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            legend_row.addWidget(dot)
            legend_row.addWidget(lbl)
        legend_row.addStretch()
        layout.addLayout(legend_row)

        # Chart
        self._chart = QChart()
        self._chart.setBackgroundVisible(False)
        self._chart.setMargins(QMargins(0, 0, 0, 0))
        self._chart.legend().hide()
        self._chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        self._series_5h = QLineSeries()
        self._series_5h.setName("5-Hour")
        pen_5h = QPen(QColor(CRIMSON_LIGHT))
        pen_5h.setWidth(2)
        self._series_5h.setPen(pen_5h)

        self._series_7d = QLineSeries()
        self._series_7d.setName("7-Day")
        pen_7d = QPen(QColor(EMBER))
        pen_7d.setWidth(2)
        self._series_7d.setPen(pen_7d)

        self._chart.addSeries(self._series_5h)
        self._chart.addSeries(self._series_7d)

        # Axes
        self._axis_x = QDateTimeAxis()
        self._axis_x.setFormat("dd/MM HH:mm")
        self._axis_x.setLabelsColor(QColor(TEXT_MUTED))
        self._axis_x.setLabelsFont(QFont("Segoe UI", 8))
        self._axis_x.setGridLineColor(QColor(BORDER_SUBTLE))
        self._axis_x.setLineVisible(False)
        self._axis_x.setTickCount(4)

        self._axis_y = QValueAxis()
        self._axis_y.setRange(0, 100)
        self._axis_y.setLabelFormat("%d%%")
        self._axis_y.setLabelsColor(QColor(TEXT_MUTED))
        self._axis_y.setLabelsFont(QFont("Segoe UI", 8))
        self._axis_y.setGridLineColor(QColor(BORDER_SUBTLE))
        self._axis_y.setLineVisible(False)
        self._axis_y.setTickCount(3)

        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)

        self._series_5h.attachAxis(self._axis_x)
        self._series_5h.attachAxis(self._axis_y)
        self._series_7d.attachAxis(self._axis_x)
        self._series_7d.attachAxis(self._axis_y)

        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(_QPainter.RenderHint.Antialiasing, True)
        self._chart_view.setStyleSheet(f"background: {BG_BASE}; border: none;")
        self._chart_view.setFixedHeight(160)
        layout.addWidget(self._chart_view)

        self._update_btn_styles()

    def update_data(self, snapshots: list[UsageData]):
        self._series_5h.clear()
        self._series_7d.clear()

        if not snapshots:
            return

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self._range_hours)

        filtered = [s for s in snapshots if s.fetched_at >= cutoff]
        if not filtered:
            return

        for s in filtered:
            ms = s.fetched_at.timestamp() * 1000
            self._series_5h.append(QPointF(ms, s.five_hour_utilization))
            self._series_7d.append(QPointF(ms, s.seven_day_utilization))

        start_ms = cutoff.timestamp() * 1000
        end_ms = now.timestamp() * 1000
        self._axis_x.setMin(datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc))
        self._axis_x.setMax(datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc))

        if self._range_hours <= 24:
            self._axis_x.setFormat("HH:mm")
        elif self._range_hours <= 24 * 7:
            self._axis_x.setFormat("dd/MM HH:mm")
        else:
            self._axis_x.setFormat("dd/MM")

    def _set_range(self, hours: int):
        self._range_hours = hours
        self._update_btn_styles()

    def _update_btn_styles(self):
        hours_map = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
        for btn in self._range_btns:
            h = hours_map.get(btn.text(), 0)
            if h == self._range_hours:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {CRIMSON}; color: {TEXT_PRIMARY};"
                    f"  border: none; border-radius: 10px;"
                    f"  font-size: 10px; font-weight: bold; padding: 2px 6px;"
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {BG_SURFACE}; color: {TEXT_MUTED};"
                    f"  border: 1px solid {BORDER_DEFAULT}; border-radius: 10px;"
                    f"  font-size: 10px; padding: 2px 6px;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  background: {BG_ELEVATED}; color: {TEXT_PRIMARY};"
                    f"}}"
                )

    @property
    def range_hours(self) -> int:
        return self._range_hours
