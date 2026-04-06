from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from ui.styles import (
    BG_SURFACE, BORDER_DEFAULT, BORDER_ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    CRIMSON, STATUS_ACTIVE,
)


class DataCard(QWidget):
    def __init__(self, title: str, accent_color: str = TEXT_PRIMARY, highlight: bool = False, parent=None):
        super().__init__(parent)
        border = BORDER_ACCENT if highlight else BORDER_DEFAULT
        self.setStyleSheet(
            f"QWidget {{ background: {BG_SURFACE}; border: 1px solid {border}; border-radius: 6px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(self._title_label)

        self._value_label = QLabel("—")
        self._value_label.setStyleSheet(
            f"color: {accent_color}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(self._value_label)

        self._sub_label = QLabel("")
        self._sub_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        self._sub_label.hide()
        layout.addWidget(self._sub_label)

    def set_value(self, value: str, subtitle: str = ""):
        self._value_label.setText(value)
        if subtitle:
            self._sub_label.setText(subtitle)
            self._sub_label.show()
        else:
            self._sub_label.hide()


class DataCardsRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tokens_card = DataCard("Tokens Today", CRIMSON, highlight=True)
        self.active_card = DataCard("Active", STATUS_ACTIVE)
        self.sessions_card = DataCard("This Week", TEXT_PRIMARY)

        layout.addWidget(self.tokens_card)
        layout.addWidget(self.active_card)
        layout.addWidget(self.sessions_card)

    def update_data(
        self,
        total_tokens: int,
        active_count: int,
        week_count: int,
    ):
        self.tokens_card.set_value(self._format_tokens(total_tokens))
        self.active_card.set_value(str(active_count), "sessions")
        self.sessions_card.set_value(str(week_count), "sessions")

    @staticmethod
    def _format_tokens(count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)
