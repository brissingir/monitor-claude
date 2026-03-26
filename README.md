# Monitor Claude

Windows system tray app that monitors your Claude API usage in real-time with session analytics, cost estimation, and historical trends.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.8-green)
![Windows](https://img.shields.io/badge/Windows-11-0078D6)

## Features

- **Real-time usage tracking** — 5-hour session and 7-day utilization with animated progress bars
- **Session intelligence** — scans Claude Code session logs, tracks tokens per model (Opus, Sonnet, Haiku)
- **Cost estimation** — calculates spending per session based on model-specific pricing
- **Trend sparklines** — visual history of usage over time
- **Data cards** — at-a-glance metrics (total tokens, sessions, estimated cost)
- **Tabbed interface** — Usage, Sessions, and Settings tabs in a single popup
- **Global hotkey** — Ctrl+Shift+C to toggle popup (with automatic fallback if taken)
- **Export** — CSV and JSON export of usage and session data
- **Process monitor** — detects active Claude Code processes
- **Notifications** — Windows toast alerts at warning (70%) and critical (90%) thresholds
- **SQLite persistence** — 90-day history with automatic schema versioning and pruning
- **Auto-start** — optional Windows startup integration

## Screenshots

### System Tray Icon
A stylized **"C"** that changes color based on usage — green (normal), orange (warning), red (critical).

### Popup Window
Click the tray icon or press the hotkey to open the dashboard:

```
┌──────────────────────────────────────────┐
│  Claude Usage            ⚙  📊  ✕       │
├──[ Usage ][ Sessions ][ Settings ]───────┤
│                                          │
│  5-Hour Session                    29%   │
│  [█████████░░░░░░░░░░░░░░░░░░░░░]       │
│  Resets in 3h 42m            ▂▃▅▇▅▃▂    │
│                                          │
│  7-Day Usage                       63%   │
│  [███████████████████░░░░░░░░░░░]       │
│  Resets in 5d 18h            ▃▅▇▅▃▂▁    │
│                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Sessions │ │  Tokens  │ │  Cost   │   │
│  │    32    │ │  1.2M    │ │ $4.80   │   │
│  └─────────┘ └─────────┘ └─────────┘   │
│                                          │
│  Updated just now                    ↻   │
└──────────────────────────────────────────┘
```

## Setup

### Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/code) logged in (the app reads its OAuth token)

### Install

```bash
git clone https://github.com/brissingir/monitor-claude.git
cd monitor-claude
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

Or without a console window:

```bash
pythonw main.py
```

### Auto-start with Windows

Right-click the tray icon → **Start with Windows**

Or run manually:

```bash
python autostart.py
```

## Configuration

Settings are accessible directly in the **Settings** tab inside the popup:

| Setting | Default | Description |
|---------|---------|-------------|
| Polling interval | 1 min | How often to check usage |
| Warning threshold | 70% | Shows orange notification |
| Critical threshold | 90% | Shows red notification |
| Notifications | On | Windows toast notifications |

Settings are saved to `%LOCALAPPDATA%\ClaudeUsageMonitor\settings.json`.

## How it works

1. **Auth** — reads the OAuth token from `~/.claude/.credentials.json` (managed by Claude Code)
2. **Polling** — calls the Anthropic usage API every minute with exponential backoff on errors
3. **Session scanning** — parses Claude Code JSONL session logs to extract token counts per model
4. **Persistence** — stores usage snapshots and session data in SQLite (90-day retention, auto-pruning)
5. **Cost estimation** — applies per-model pricing (input/output/cache tokens) to calculate session costs
6. **Display** — dark-themed popup with progress bars, sparkline trends, data cards, and session list
7. **Notifications** — fires Windows toast alerts when usage crosses configurable thresholds

## Color Palette

| Element | Color |
|---------|-------|
| Background | `#000000` |
| 5-Hour bar | `#B90E0A` (Crimson) |
| 7-Day bar | `#5B6FE8` (Royal Blue) |
| Normal icon | `#4CAF50` (Green) |
| Text | `#FFFFFF` |

## Global Hotkey

The app registers **Ctrl+Shift+C** to toggle the popup. If that combination is already taken by another app, it automatically tries fallbacks in order:

1. Ctrl+Shift+C
2. Ctrl+Shift+U
3. Ctrl+Alt+U
4. Ctrl+Alt+C

The successfully registered hotkey is shown in the logs.

## Build executable

```bash
pip install pyinstaller
build.bat
```

Outputs `dist/ClaudeUsageMonitor.exe` — a single portable file.

## Project Structure

```
monitor-claude/
├── main.py               # Entry point, single-instance check, logging init
├── app.py                # System tray, popup, notifications, scanner integration
├── api_client.py         # HTTP client for Anthropic usage API
├── auth.py               # OAuth token reader
├── polling_service.py    # Threaded polling with exponential backoff
├── models.py             # Data classes (UsageData, SessionData, SessionTokenUsage)
├── config.py             # Settings persistence
├── data_store.py         # SQLite storage with schema versioning
├── session_scanner.py    # Claude Code session log parser
├── cost_estimator.py     # Per-model token cost calculation
├── process_monitor.py    # Active Claude process detection
├── hotkey.py             # Global hotkey with fallback registration
├── exporter.py           # CSV/JSON export
├── logging_config.py     # Structured logging setup
├── autostart.py          # Windows startup shortcut manager
├── ui/
│   ├── popup_window.py   # Main tabbed popup window
│   ├── tab_bar.py        # Custom tab bar widget
│   ├── data_cards.py     # Metric summary cards
│   ├── trend_chart.py    # Sparkline charts
│   ├── session_list.py   # Session list with token details
│   ├── settings_tab.py   # Inline settings (replaces modal dialog)
│   └── styles.py         # Colors and QSS
├── requirements.txt
└── build.bat
```

## License

MIT
