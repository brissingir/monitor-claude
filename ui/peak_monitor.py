"""Peak Hours Monitor widget.

Shows real-time on/off-peak status based on Anthropic's peak hours:
  8 AM – 2 PM Eastern Time, weekdays only.

Uses manual DST computation to avoid the tzdata package dependency on Windows.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)

from ui.styles import (
    BG_BASE, BG_SURFACE, BG_ELEVATED,
    CRIMSON, CRIMSON_DARK, CRIMSON_LIGHT, SCARLET,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_DEFAULT, BORDER_SUBTLE,
    STATUS_ACTIVE, WARNING_AMBER,
)

# Peak window in Eastern Time
_PEAK_START_HOUR = 8   # 8 AM ET
_PEAK_END_HOUR   = 14  # 2 PM ET


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime:
    """Return the n-th occurrence (1-based) of weekday (0=Mon) in year/month, UTC midnight."""
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def _et_offset(dt_utc: datetime) -> timedelta:
    """Return Eastern Time UTC offset (-5h EST or -4h EDT) for a given UTC datetime."""
    y = dt_utc.year
    # Spring forward: 2nd Sunday in March at 07:00 UTC (= 2 AM EST)
    dst_start = _nth_weekday(y, 3, 6, 2).replace(hour=7)
    # Fall back: 1st Sunday in November at 06:00 UTC (= 2 AM EDT)
    dst_end   = _nth_weekday(y, 11, 6, 1).replace(hour=6)

    if dst_start <= dt_utc < dst_end:
        return timedelta(hours=-4)  # EDT
    return timedelta(hours=-5)      # EST


def _brt_offset(_dt_utc: datetime) -> timedelta:
    """Brazil / Sao Paulo is always UTC-3 since DST was abolished in 2019."""
    return timedelta(hours=-3)


def _to_et(dt_utc: datetime) -> datetime:
    offset = _et_offset(dt_utc)
    return (dt_utc + offset).replace(tzinfo=timezone(offset))


def _to_brt(dt_utc: datetime) -> datetime:
    offset = _brt_offset(dt_utc)
    return (dt_utc + offset).replace(tzinfo=timezone(offset))


def _is_peak(dt_et: datetime) -> bool:
    """Return True if dt_et is within the weekday peak window."""
    return dt_et.weekday() < 5 and _PEAK_START_HOUR <= dt_et.hour < _PEAK_END_HOUR


def _next_peak_start(dt_utc: datetime) -> datetime:
    """Return the UTC datetime when the next peak window begins."""
    dt_et = _to_et(dt_utc)
    candidate_et = dt_et.replace(hour=_PEAK_START_HOUR, minute=0, second=0, microsecond=0)
    if candidate_et <= dt_et:
        candidate_et += timedelta(days=1)
    # Skip weekends
    while candidate_et.weekday() >= 5:
        candidate_et += timedelta(days=1)
    # Convert back to UTC: subtract the ET offset
    offset = _et_offset(dt_utc)
    return candidate_et.replace(tzinfo=timezone.utc) - offset


def _next_peak_end(dt_utc: datetime) -> datetime:
    """Return the UTC datetime when today's peak window ends."""
    dt_et = _to_et(dt_utc)
    end_et = dt_et.replace(hour=_PEAK_END_HOUR, minute=0, second=0, microsecond=0)
    offset = _et_offset(dt_utc)
    return end_et.replace(tzinfo=timezone.utc) - offset


# ── Timeline bar ─────────────────────────────────────────────────────────────

class _TimelineBar(QWidget):
    """Horizontal 24-hour bar with peak region and 'now' cursor.

    `to_local` is a callable(utc_datetime) -> local_datetime.
    """

    def __init__(self, to_local, label: str, parent=None):
        super().__init__(parent)
        self._to_local = to_local
        self._label = label
        self.setFixedHeight(52)
        self.setMinimumWidth(200)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_top = 22
        bar_h   = 16

        now_utc = datetime.now(timezone.utc)
        now_local = self._to_local(now_utc)

        # Compute peak window in this bar's local time.
        # Peak is always 8–14 ET; convert ET wall-clock bounds → UTC → local.
        et_offset     = _et_offset(now_utc)
        now_et        = _to_et(now_utc)
        peak_start_et = now_et.replace(hour=_PEAK_START_HOUR, minute=0, second=0, microsecond=0)
        peak_end_et   = now_et.replace(hour=_PEAK_END_HOUR,   minute=0, second=0, microsecond=0)
        # naive-to-UTC: ET wall-clock is UTC + et_offset, so UTC = wall - et_offset
        peak_start_utc   = peak_start_et.replace(tzinfo=None).replace(tzinfo=timezone.utc) - et_offset
        peak_end_utc     = peak_end_et.replace(tzinfo=None).replace(tzinfo=timezone.utc) - et_offset
        peak_start_local = self._to_local(peak_start_utc)
        peak_end_local   = self._to_local(peak_end_utc)

        def frac(h: float) -> float:
            return h / 24.0

        peak_s_frac = frac(peak_start_local.hour + peak_start_local.minute / 60)
        peak_e_frac = frac(peak_end_local.hour + peak_end_local.minute / 60)
        now_frac    = frac(now_local.hour + now_local.minute / 60 + now_local.second / 3600)

        # Draw background track
        track_rect = QRectF(0, bar_top, w, bar_h)
        painter.setBrush(QColor(BG_SURFACE))
        painter.setPen(QPen(QColor(BORDER_DEFAULT), 1))
        painter.drawRoundedRect(track_rect, 3, 3)

        # Peak region
        px = int(peak_s_frac * w)
        pw = int((peak_e_frac - peak_s_frac) * w)
        if pw > 0:
            peak_rect = QRectF(px, bar_top, pw, bar_h)
            peak_color = QColor(CRIMSON)
            peak_color.setAlphaF(0.55)
            painter.setBrush(peak_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(peak_rect, 3, 3)

        # Now cursor (thin white line)
        nx = int(now_frac * w)
        painter.setPen(QPen(QColor(TEXT_PRIMARY), 2))
        painter.drawLine(nx, bar_top - 2, nx, bar_top + bar_h + 2)

        # Labels: timezone name + hour marks
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(TEXT_SECONDARY))
        painter.drawText(0, 0, w, 18, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(TEXT_MUTED))
        for hour_str, x_frac in [("12a", 0.0), ("6a", 0.25), ("12p", 0.5), ("6p", 0.75), ("12a", 1.0)]:
            x = int(x_frac * w)
            align = Qt.AlignmentFlag.AlignHCenter
            painter.drawText(x - 14, bar_top + bar_h + 2, 28, 12, align, hour_str)

        # Peak window label inside bar
        if pw > 30:
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.drawText(px, bar_top, pw, bar_h, Qt.AlignmentFlag.AlignCenter, "PEAK")

        painter.end()


# ── Timezone card ─────────────────────────────────────────────────────────────

class _TzCard(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QWidget {{ background: {BG_SURFACE}; border: 1px solid {BORDER_DEFAULT}; border-radius: 4px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold; font-family: 'Consolas', monospace;"
        )
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value_lbl)

    def set_value(self, text: str):
        self._value_lbl.setText(text)


# ── Main widget ───────────────────────────────────────────────────────────────

class PeakMonitorWidget(QWidget):
    """Displays on/off-peak status with countdown, timeline bars, and timezone cards."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Section header
        header_lbl = QLabel("\u26a1 PEAK STATUS")
        header_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(header_lbl)

        # Status banner
        self._status_lbl = QLabel("—")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {TEXT_PRIMARY};"
        )
        layout.addWidget(self._status_lbl)

        # Countdown label
        self._countdown_desc_lbl = QLabel("")
        self._countdown_desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_desc_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._countdown_desc_lbl)

        self._countdown_lbl = QLabel("00:00:00")
        self._countdown_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_lbl.setStyleSheet(
            f"color: {CRIMSON}; font-size: 36px; font-weight: bold; "
            f"font-family: 'Consolas', 'Courier New', monospace;"
        )
        layout.addWidget(self._countdown_lbl)

        layout.addSpacing(4)

        # Timeline bars
        self._bar_et  = _TimelineBar(_to_et,  "EASTERN TIME (ET)")
        self._bar_brt = _TimelineBar(_to_brt, "BRASÍLIA (BRT)")
        layout.addWidget(self._bar_et)
        layout.addWidget(self._bar_brt)

        layout.addSpacing(4)

        # Timezone info cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        self._card_zone = _TzCard("LOCAL ZONE")
        self._card_local = _TzCard("LOCAL TIME")
        self._card_et = _TzCard("EASTERN TIME")
        cards_row.addWidget(self._card_zone)
        cards_row.addWidget(self._card_local)
        cards_row.addWidget(self._card_et)
        layout.addLayout(cards_row)

        # Footer note
        footer = QLabel("Peak: 8 AM – 2 PM ET on weekdays  ·  Weekends: off-peak all day")
        footer.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        # 1-second timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        now_utc   = datetime.now(timezone.utc)
        now_et    = _to_et(now_utc)
        now_local = datetime.now().astimezone()

        on_peak    = _is_peak(now_et)
        is_weekend = now_et.weekday() >= 5

        # Status banner
        if is_weekend:
            self._status_lbl.setText("OFF-PEAK — Weekend")
            self._status_lbl.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {TEXT_PRIMARY};"
            )
        elif on_peak:
            self._status_lbl.setText("ON-PEAK")
            self._status_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {SCARLET};"
            )
        else:
            self._status_lbl.setText("OFF-PEAK")
            self._status_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {TEXT_PRIMARY};"
            )

        # Countdown
        if on_peak:
            target = _next_peak_end(now_utc)
            self._countdown_desc_lbl.setText("Off-peak starts in:")
            self._countdown_lbl.setStyleSheet(
                f"color: {CRIMSON}; font-size: 36px; font-weight: bold; "
                f"font-family: 'Consolas', 'Courier New', monospace;"
            )
        else:
            target = _next_peak_start(now_utc)
            self._countdown_desc_lbl.setText("Peak starts in:")
            self._countdown_lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 36px; font-weight: bold; "
                f"font-family: 'Consolas', 'Courier New', monospace;"
            )

        delta = target - now_utc
        total = max(0, int(delta.total_seconds()))
        hh = total // 3600
        mm = (total % 3600) // 60
        ss = total % 60
        self._countdown_lbl.setText(f"{hh:02d}:{mm:02d}:{ss:02d}")

        # Timeline bars repaint
        self._bar_et.update()
        self._bar_brt.update()

        # Timezone cards
        local_tz_name = str(now_local.tzinfo or "Local")
        if "/" in local_tz_name:
            local_tz_name = local_tz_name.split("/")[-1]
        self._card_zone.set_value(local_tz_name)
        self._card_local.set_value(now_local.strftime("%I:%M:%S %p"))
        self._card_et.set_value(now_et.strftime("%I:%M:%S %p"))
