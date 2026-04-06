from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QFrame, QScrollArea,
)

from models import AppSettings
from ui.styles import (
    BG_BASE, BG_SURFACE, BG_ELEVATED,
    CRIMSON, BORDER_DEFAULT, BORDER_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)


class SettingsTab(QWidget):
    """Inline settings widget for the Config tab. Auto-saves with debounce."""

    settings_changed = Signal(object)  # emits AppSettings

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._emit_settings)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)

        # ── Polling ──────────────────────────────────────────────────────────
        layout.addWidget(self._section_header("Polling"))

        layout.addWidget(self._field_label("Interval (minutes)"))
        self._poll_spin = self._make_spin(1, 60, settings.poll_interval_seconds // 60)
        layout.addWidget(self._poll_spin)

        layout.addWidget(self._separator())

        # ── Notifications ─────────────────────────────────────────────────────
        layout.addWidget(self._section_header("Notifications"))

        self._notify_check = QCheckBox("Enable notifications")
        self._notify_check.setChecked(settings.notifications_enabled)
        self._notify_check.toggled.connect(self._schedule_save)
        layout.addWidget(self._notify_check)

        layout.addWidget(self._field_label("Warning threshold (%)"))
        self._warn_spin = self._make_spin(10, 100, int(settings.warning_threshold), step=5)
        layout.addWidget(self._warn_spin)

        layout.addWidget(self._field_label("Critical threshold (%)"))
        self._crit_spin = self._make_spin(10, 100, int(settings.critical_threshold), step=5)
        layout.addWidget(self._crit_spin)

        layout.addWidget(self._separator())

        # ── About ─────────────────────────────────────────────────────────────
        layout.addWidget(self._section_header("About"))

        about_card = QWidget()
        about_card.setStyleSheet(
            f"QWidget {{ background: {BG_SURFACE}; border: 1px solid {BORDER_DEFAULT}; border-radius: 6px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(12, 10, 12, 10)
        about_layout.setSpacing(4)

        name_lbl = QLabel("RIAS Monitor")
        name_lbl.setStyleSheet(f"color: {CRIMSON}; font-size: 14px; font-weight: bold; letter-spacing: 1px;")
        about_layout.addWidget(name_lbl)

        ver_lbl = QLabel("Claude Usage Monitor v2.0")
        ver_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        about_layout.addWidget(ver_lbl)

        layout.addWidget(about_card)
        layout.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_settings(self, settings: AppSettings):
        self._settings = settings
        for widget in [self._poll_spin, self._warn_spin, self._crit_spin, self._notify_check]:
            widget.blockSignals(True)

        self._poll_spin.setValue(settings.poll_interval_seconds // 60)
        self._warn_spin.setValue(int(settings.warning_threshold))
        self._crit_spin.setValue(int(settings.critical_threshold))
        self._notify_check.setChecked(settings.notifications_enabled)

        for widget in [self._poll_spin, self._warn_spin, self._crit_spin, self._notify_check]:
            widget.blockSignals(False)

    def _schedule_save(self):
        self._save_timer.start()

    def _emit_settings(self):
        new = AppSettings(
            poll_interval_seconds=self._poll_spin.value() * 60,
            warning_threshold=float(self._warn_spin.value()),
            critical_threshold=float(self._crit_spin.value()),
            notifications_enabled=self._notify_check.isChecked(),
        )
        self._settings = new
        self.settings_changed.emit(new)

    def _make_spin(self, min_val: int, max_val: int, value: int, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.valueChanged.connect(self._schedule_save)
        return spin

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    @staticmethod
    def _section_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold;"
        )
        return lbl

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_SUBTLE}; max-height: 1px;")
        return sep
