# Color palette
BG_BLACK = "#000000"
BG_SURFACE = "#111111"
BG_HOVER = "#1A1A1A"
CRIMSON = "#B90E0A"
CRIMSON_LIGHT = "#D4110C"
ROYAL_BLUE = "#5B6FE8"
ROYAL_BLUE_LIGHT = "#7B8FFF"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#999999"
TEXT_MUTED = "#666666"
WARNING_ORANGE = "#FF8C00"
CRITICAL_RED = "#FF2020"
ICON_GREEN = "#2EA043"
BORDER_COLOR = "#222222"

GLOBAL_QSS = f"""
QWidget {{
    background-color: {BG_BLACK};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QLabel {{
    background: transparent;
    border: none;
}}
QPushButton {{
    background: transparent;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_SECONDARY};
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QFrame[frameShape="4"] {{
    color: {BORDER_COLOR};
    max-height: 1px;
}}
"""
