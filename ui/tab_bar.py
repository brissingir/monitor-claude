from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

from ui.styles import (
    BG_BASE, CRIMSON,
    TEXT_PRIMARY, TEXT_MUTED,
)


class TabBar(QWidget):
    """Tab bar with crimson underline indicator for active tab."""

    tab_changed = Signal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self._current = 0
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self.set_tab(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self._update_styles()

    def set_tab(self, index: int):
        if index == self._current:
            return
        self._current = index
        self._update_styles()
        self.tab_changed.emit(index)

    @property
    def current_index(self) -> int:
        return self._current

    def _update_styles(self):
        for i, btn in enumerate(self._buttons):
            if i == self._current:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: transparent;"
                    f"  color: {TEXT_PRIMARY};"
                    f"  border: none;"
                    f"  border-bottom: 2px solid {CRIMSON};"
                    f"  border-radius: 0px;"
                    f"  font-size: 12px;"
                    f"  font-weight: bold;"
                    f"  padding: 4px 16px;"
                    f"}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: transparent;"
                    f"  color: {TEXT_MUTED};"
                    f"  border: none;"
                    f"  border-bottom: 2px solid transparent;"
                    f"  border-radius: 0px;"
                    f"  font-size: 12px;"
                    f"  padding: 4px 16px;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  color: {TEXT_PRIMARY};"
                    f"  background: transparent;"
                    f"}}"
                )
