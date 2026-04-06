# ── RIAS Monitor — Color Palette ─────────────────────────────────────────────

# Primary crimson
CRIMSON         = "#DC143C"
CRIMSON_DARK    = "#B01030"
CRIMSON_LIGHT   = "#FF2050"
CRIMSON_GLOW    = "#DC143C40"

# Secondary accent
EMBER           = "#FF4500"
EMBER_DARK      = "#CC3700"
SCARLET         = "#FF2020"
WARNING_AMBER   = "#FFB020"

# Backgrounds (dark terminal style)
BG_BASE         = "#0A0A0F"
BG_SURFACE      = "#12121A"
BG_ELEVATED     = "#1A1A25"
BG_OVERLAY      = "#22222E"

# Legacy aliases used in existing code
BG_BLACK        = BG_BASE
BG_HOVER        = BG_ELEVATED

# Text
TEXT_PRIMARY    = "#F0F0F5"
TEXT_SECONDARY  = "#A0A0B0"
TEXT_MUTED      = "#606075"
TEXT_ACCENT     = "#DC143C"

# Borders
BORDER_SUBTLE   = "#1E1E2A"
BORDER_DEFAULT  = "#2A2A38"
BORDER_ACCENT   = "#DC143C30"

# Legacy alias
BORDER_COLOR    = BORDER_DEFAULT

# Status
STATUS_ACTIVE   = "#F0F0F5"   # white dot = active/ok
STATUS_WARNING  = "#FFB020"
STATUS_CRITICAL = "#FF2020"
STATUS_INACTIVE = "#404055"

# Legacy aliases (keep backward-compat for any remaining references)
ROYAL_BLUE      = EMBER       # was used for 7-day bar → now ember
ROYAL_BLUE_LIGHT = EMBER
CRITICAL_RED    = SCARLET
WARNING_ORANGE  = WARNING_AMBER
ICON_GREEN      = STATUS_ACTIVE


# ── Global QSS ───────────────────────────────────────────────────────────────

GLOBAL_QSS = f"""
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    border: none;
}}

/* ── Buttons ── */
QPushButton {{
    background: transparent;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    padding: 4px 10px;
    color: {TEXT_SECONDARY};
}}
QPushButton:hover {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border-color: {BORDER_DEFAULT};
}}
QPushButton:pressed {{
    background-color: {BG_OVERLAY};
}}

/* ── Horizontal separator lines ── */
QFrame[frameShape="4"] {{
    color: {BORDER_SUBTLE};
    max-height: 1px;
}}

/* ── Scrollbars (6px slim style) ── */
QScrollBar:vertical {{
    background: {BG_BASE};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_DEFAULT};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: {BG_BASE};
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_DEFAULT};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ── SpinBox ── */
QSpinBox {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QSpinBox:focus {{
    border-color: {CRIMSON};
}}
QSpinBox::up-button,
QSpinBox::down-button {{
    border: none;
    background: {BORDER_DEFAULT};
    width: 20px;
}}
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background: {BG_ELEVATED};
}}

/* ── CheckBox ── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 3px;
    background: {BG_SURFACE};
}}
QCheckBox::indicator:checked {{
    background-color: {CRIMSON};
    border-color: {CRIMSON};
}}
QCheckBox::indicator:hover {{
    border-color: {CRIMSON};
}}

/* ── Progress bar base ── */
QProgressBar {{
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    background-color: {BG_SURFACE};
    text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 3px;
}}

/* ── ScrollArea ── */
QScrollArea {{
    background: {BG_BASE};
    border: none;
}}
"""
