from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QFrame, QScrollArea,
)

from models import AppSettings
from ui.styles import (
    BG_BLACK, BG_SURFACE, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)


class SettingsTab(QWidget):
    """Inline settings widget for the Config tab. Auto-saves with debounce."""

    settings_changed = Signal(object)  # emits AppSettings

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings

        # Debounce timer for auto-save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._emit_settings)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG_BLACK}; border: none; }}"
            f"QScrollBar:vertical {{ background: {BG_BLACK}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER_COLOR}; border-radius: 3px; min-height: 20px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        # --- Polling ---
        layout.addWidget(self._section_label("Polling"))

        layout.addWidget(self._make_label("Interval (minutes)"))
        self._poll_spin = self._make_spin(1, 60, settings.poll_interval_seconds // 60)
        layout.addWidget(self._poll_spin)

        layout.addWidget(self._make_separator())

        # --- Notifications ---
        layout.addWidget(self._section_label("Notifications"))

        self._notify_check = QCheckBox("Enable notifications")
        self._notify_check.setChecked(settings.notifications_enabled)
        self._notify_check.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        self._notify_check.toggled.connect(self._schedule_save)
        layout.addWidget(self._notify_check)

        layout.addWidget(self._make_label("Warning threshold (%)"))
        self._warn_spin = self._make_spin(10, 100, int(settings.warning_threshold), step=5)
        layout.addWidget(self._warn_spin)

        layout.addWidget(self._make_label("Critical threshold (%)"))
        self._crit_spin = self._make_spin(10, 100, int(settings.critical_threshold), step=5)
        layout.addWidget(self._crit_spin)

        layout.addWidget(self._make_separator())

        # --- About ---
        layout.addWidget(self._section_label("About"))
        version_lbl = QLabel("Claude Usage Monitor v2.0")
        version_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(version_lbl)

        layout.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_settings(self, settings: AppSettings):
        """Update UI from settings without triggering save."""
        self._settings = settings
        self._poll_spin.blockSignals(True)
        self._warn_spin.blockSignals(True)
        self._crit_spin.blockSignals(True)
        self._notify_check.blockSignals(True)

        self._poll_spin.setValue(settings.poll_interval_seconds // 60)
        self._warn_spin.setValue(int(settings.warning_threshold))
        self._crit_spin.setValue(int(settings.critical_threshold))
        self._notify_check.setChecked(settings.notifications_enabled)

        self._poll_spin.blockSignals(False)
        self._warn_spin.blockSignals(False)
        self._crit_spin.blockSignals(False)
        self._notify_check.blockSignals(False)

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
        spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
                font-size: 13px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                border: none;
                background: {BORDER_COLOR};
                width: 20px;
            }}
        """)
        spin.valueChanged.connect(self._schedule_save)
        return spin

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold;"
        )
        return lbl

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR}; max-height: 1px;")
        return sep
