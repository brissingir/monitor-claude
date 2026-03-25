from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QPushButton, QFrame,
)

from models import AppSettings
from ui.styles import BG_BLACK, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, GLOBAL_QSS


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._result_settings: AppSettings | None = None

        self.setWindowTitle("Settings")
        self.setFixedSize(320, 360)
        self.setStyleSheet(GLOBAL_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR}; max-height: 1px;")
        layout.addWidget(sep)

        # Poll interval
        layout.addWidget(self._make_label("Polling Interval (minutes)"))
        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(1, 60)
        self._poll_spin.setValue(settings.poll_interval_seconds // 60)
        self._poll_spin.setStyleSheet(self._spin_style())
        layout.addWidget(self._poll_spin)

        # Warning threshold
        layout.addWidget(self._make_label("Warning Threshold (%)"))
        self._warn_spin = QSpinBox()
        self._warn_spin.setRange(10, 100)
        self._warn_spin.setSingleStep(5)
        self._warn_spin.setValue(int(settings.warning_threshold))
        self._warn_spin.setStyleSheet(self._spin_style())
        layout.addWidget(self._warn_spin)

        # Critical threshold
        layout.addWidget(self._make_label("Critical Threshold (%)"))
        self._crit_spin = QSpinBox()
        self._crit_spin.setRange(10, 100)
        self._crit_spin.setSingleStep(5)
        self._crit_spin.setValue(int(settings.critical_threshold))
        self._crit_spin.setStyleSheet(self._spin_style())
        layout.addWidget(self._crit_spin)

        # Notifications
        self._notify_check = QCheckBox("Enable notifications")
        self._notify_check.setChecked(settings.notifications_enabled)
        self._notify_check.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(self._notify_check)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BORDER_COLOR};
                border: 1px solid {BORDER_COLOR};
                padding: 6px 16px;
            }}
            QPushButton:hover {{ background-color: #333333; }}
        """)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_settings(self) -> AppSettings | None:
        return self._result_settings

    def _save(self):
        self._result_settings = AppSettings(
            poll_interval_seconds=self._poll_spin.value() * 60,
            warning_threshold=float(self._warn_spin.value()),
            critical_threshold=float(self._crit_spin.value()),
            notifications_enabled=self._notify_check.isChecked(),
            compact_display=self._settings.compact_display,
            start_with_windows=self._settings.start_with_windows,
        )
        self.accept()

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    @staticmethod
    def _spin_style() -> str:
        return f"""
            QSpinBox {{
                background-color: #111111;
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
                font-size: 13px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                border: none;
                background: #222222;
                width: 20px;
            }}
        """
