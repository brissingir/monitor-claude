from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

from ui.styles import (
    BG_SURFACE, BORDER_COLOR, CRIMSON,
    TEXT_PRIMARY, TEXT_MUTED,
)


class TabBar(QWidget):
    """Custom dark-themed tab bar with Crimson accent for active tab."""

    tab_changed = Signal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self._current = 0
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self.set_tab(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

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
                    f"background: {CRIMSON}; color: {TEXT_PRIMARY}; "
                    f"border: none; border-radius: 4px; "
                    f"font-size: 12px; font-weight: bold; padding: 4px 12px;"
                )
            else:
                btn.setStyleSheet(
                    f"background: {BG_SURFACE}; color: {TEXT_MUTED}; "
                    f"border: 1px solid {BORDER_COLOR}; border-radius: 4px; "
                    f"font-size: 12px; padding: 4px 12px;"
                )
