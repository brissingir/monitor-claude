from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QPointF, QMargins
from PySide6.QtGui import QPainter as _QPainter
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis,
)
from PySide6.QtGui import QColor, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from models import UsageData
from ui.styles import (
    BG_BLACK, BG_SURFACE, CRIMSON, CRIMSON_LIGHT,
    ROYAL_BLUE, ROYAL_BLUE_LIGHT, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, BORDER_COLOR,
)


class TrendChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._range_hours = 24 * 7  # default 7 days

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Range selector buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)
        self._range_btns: list[QPushButton] = []
        for label, hours in [("24h", 24), ("7d", 24 * 7), ("30d", 24 * 30)]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setFixedWidth(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, h=hours: self._set_range(h))
            btn_row.addWidget(btn)
            self._range_btns.append(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

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
        pen_7d = QPen(QColor(ROYAL_BLUE_LIGHT))
        pen_7d.setWidth(2)
        self._series_7d.setPen(pen_7d)

        self._chart.addSeries(self._series_5h)
        self._chart.addSeries(self._series_7d)

        # Axes
        self._axis_x = QDateTimeAxis()
        self._axis_x.setFormat("dd/MM HH:mm")
        self._axis_x.setLabelsColor(QColor(TEXT_MUTED))
        self._axis_x.setLabelsFont(QFont("Segoe UI", 8))
        self._axis_x.setGridLineColor(QColor(BORDER_COLOR))
        self._axis_x.setLineVisible(False)
        self._axis_x.setTickCount(4)

        self._axis_y = QValueAxis()
        self._axis_y.setRange(0, 100)
        self._axis_y.setLabelFormat("%d%%")
        self._axis_y.setLabelsColor(QColor(TEXT_MUTED))
        self._axis_y.setLabelsFont(QFont("Segoe UI", 8))
        self._axis_y.setGridLineColor(QColor(BORDER_COLOR))
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
        self._chart_view.setStyleSheet(f"background: {BG_BLACK}; border: none;")
        self._chart_view.setFixedHeight(140)
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

        # Update X axis range
        start_ms = cutoff.timestamp() * 1000
        end_ms = now.timestamp() * 1000
        self._axis_x.setMin(datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc))
        self._axis_x.setMax(datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc))

        # Adjust format based on range
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
        for btn in self._range_btns:
            hours_map = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
            h = hours_map.get(btn.text(), 0)
            if h == self._range_hours:
                btn.setStyleSheet(
                    f"background: {CRIMSON}; color: {TEXT_PRIMARY}; "
                    f"border: none; border-radius: 3px; font-size: 11px; font-weight: bold;"
                )
            else:
                btn.setStyleSheet(
                    f"background: {BG_SURFACE}; color: {TEXT_MUTED}; "
                    f"border: 1px solid {BORDER_COLOR}; border-radius: 3px; font-size: 11px;"
                )

    @property
    def range_hours(self) -> int:
        return self._range_hours
