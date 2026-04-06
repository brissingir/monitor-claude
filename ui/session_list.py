from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame,
)

from cost_estimator import format_cost
from models import SessionData
from ui.styles import (
    BG_BASE, BG_SURFACE, BG_ELEVATED, BORDER_DEFAULT,
    CRIMSON, EMBER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    STATUS_ACTIVE,
)


class SessionRow(QWidget):
    def __init__(self, session: SessionData, is_active: bool = False, parent=None):
        super().__init__(parent)
        self._session = session
        self._expanded = False
        self._is_active = is_active

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(expanded=False)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(10, 6, 10, 6)
        self._main_layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(6)

        if is_active:
            dot = QLabel("\u25CF")
            dot.setStyleSheet(
                f"color: {STATUS_ACTIVE}; font-size: 10px; border: none; background: transparent;"
            )
            dot.setFixedWidth(14)
            header.addWidget(dot)

        title_text = session.ai_title or session.slug or "Untitled session"
        if len(title_text) > 40:
            title_text = title_text[:37] + "..."
        title = QLabel(title_text)
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold; "
            f"border: none; background: transparent;"
        )
        header.addWidget(title, stretch=1)

        tokens_text = self._format_tokens(session.total_tokens)
        model_color = self._get_model_color(session)
        tokens_lbl = QLabel(tokens_text)
        tokens_lbl.setStyleSheet(
            f"color: {model_color}; font-size: 11px; font-weight: bold; "
            f"border: none; background: transparent;"
        )
        header.addWidget(tokens_lbl)

        self._main_layout.addLayout(header)

        # Subtitle row
        sub = QHBoxLayout()
        sub.setSpacing(4)

        project = session.project_path.replace("\\", "/").split("/")[-1] if session.project_path else ""
        if project:
            proj_lbl = QLabel(project)
            proj_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
            )
            sub.addWidget(proj_lbl)
            sub.addWidget(self._dot_separator())

        dur = session.duration_seconds
        if dur is not None:
            dur_text = f"{dur // 3600}h {(dur % 3600) // 60}m" if dur >= 3600 else f"{dur // 60}m"
            dur_lbl = QLabel(dur_text)
            dur_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
            )
            sub.addWidget(dur_lbl)
            sub.addWidget(self._dot_separator())

        msg_lbl = QLabel(f"{session.user_message_count} msgs")
        msg_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        sub.addWidget(msg_lbl)
        sub.addStretch()

        if session.started_at:
            time_lbl = QLabel(self._format_relative_time(session.started_at))
            time_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
            )
            sub.addWidget(time_lbl)

        self._main_layout.addLayout(sub)

        # Detail section (hidden by default)
        self._detail_widget = QWidget()
        self._detail_widget.hide()
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 4, 0, 0)
        detail_layout.setSpacing(2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_DEFAULT}; max-height: 1px; border: none;")
        detail_layout.addWidget(sep)

        for usage in session.token_usage:
            model_name = usage.model.replace("claude-", "").replace("-", " ").title()
            row = QHBoxLayout()
            m_lbl = QLabel(f"  {model_name}")
            m_lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 10px; border: none; background: transparent;"
            )
            row.addWidget(m_lbl)
            row.addStretch()
            detail_text = (
                f"in:{self._format_tokens(usage.input_tokens)} "
                f"out:{self._format_tokens(usage.output_tokens)} "
                f"cache:{self._format_tokens(usage.cache_read_tokens)}"
            )
            d_lbl = QLabel(detail_text)
            d_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
            )
            row.addWidget(d_lbl)
            detail_layout.addLayout(row)

        info_row = QHBoxLayout()
        cost_val = format_cost(session.total_cost)
        info_parts = [f"Cost: ~{cost_val}"]
        if session.entrypoint:
            ep = session.entrypoint.replace("claude-", "")
            info_parts.append(ep)
        if session.git_branch and session.git_branch != "HEAD":
            info_parts.append(f"branch: {session.git_branch}")
        info_lbl = QLabel("  " + "  |  ".join(info_parts))
        info_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        info_row.addWidget(info_lbl)
        detail_layout.addLayout(info_row)

        self._main_layout.addWidget(self._detail_widget)

    def mousePressEvent(self, event):
        self._expanded = not self._expanded
        self._detail_widget.setVisible(self._expanded)
        self._apply_style(expanded=self._expanded)

    def _apply_style(self, expanded: bool):
        bg = BG_ELEVATED if expanded else BG_SURFACE
        self.setStyleSheet(
            f"QWidget {{ background: {bg}; border: 1px solid {BORDER_DEFAULT}; border-radius: 4px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )

    def _dot_separator(self) -> QLabel:
        lbl = QLabel("\u00B7")
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        lbl.setFixedWidth(8)
        return lbl

    @staticmethod
    def _get_model_color(session: SessionData) -> str:
        for u in session.token_usage:
            if "opus" in u.model:
                return CRIMSON
            if "sonnet" in u.model:
                return EMBER
        return TEXT_SECONDARY

    @staticmethod
    def _format_tokens(count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.0f}K"
        return str(count)

    @staticmethod
    def _format_relative_time(dt: datetime) -> str:
        now = datetime.now(timezone.utc)
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"


class SessionListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFixedHeight(250)

        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def update_sessions(self, sessions: list[SessionData], active_ids: set[str]):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not sessions:
            empty = QLabel("No sessions found")
            empty.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; border: none; background: transparent;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.insertWidget(0, empty)
            return

        for session in sessions:
            is_active = session.session_id in active_ids
            row = SessionRow(session, is_active=is_active)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
