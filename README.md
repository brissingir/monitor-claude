# RIAS Monitor

Windows system tray app that monitors your Claude Code usage in real-time — with session analytics, peak hour awareness, cost estimation, and historical trends.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.8-red)
![Windows](https://img.shields.io/badge/Windows-11-0078D6)
![Version](https://img.shields.io/badge/version-2.0-DC143C)

## Features

- **Real-time usage tracking** — 5-hour session and 7-day utilization with animated progress bars
- **Peak hours monitor** — live on/off-peak status (8 AM–2 PM ET weekdays) with countdown, ET/BRT timeline bars, and timezone cards
- **Today's Usage** — token breakdown for the current day (cache read/write, input, output) with cost estimate
- **Session intelligence** — scans Claude Code session logs, tracks tokens per model (Opus, Sonnet, Haiku)
- **Model breakdown** — stacked bar showing usage proportion per model with token detail
- **Peak hours heatmap** — 24-hour activity heatmap showing your usage patterns
- **Cost estimation** — calculates spending per session based on model-specific pricing
- **Trend chart** — 24h / 7d / 30d history with dual lines (5h session + 7d weekly)
- **Process monitor** — lists active Claude Code processes with memory, uptime, and kill button
- **Tabbed interface** — Dashboard, Sessions, Processes, Config
- **Global hotkey** — toggles popup (Ctrl+Shift+C preferred; auto-fallback if taken)
- **Export** — CSV and JSON export of usage and session data
- **Notifications** — Windows toast alerts at warning (70%) and critical (90%) thresholds
- **SQLite persistence** — 90-day history with automatic schema versioning and pruning
- **Auto-start** — optional Windows startup integration

## Screenshots

### Popup Window

```
┌──────────────────────────────────────────────────────────┐
│  R  RIAS Monitor                          Pro  ●  ✕      │
├──[ Dashboard ][ Sessions ][ Processes ][ Config ]─────────┤
│                                                           │
│  5-HOUR SESSION                                   74%     │
│  [████████████████████████░░░░░░░░░░░░░░░░░░░░]          │
│  Resets in 1h 23m                                         │
│                                                           │
│  7-DAY USAGE                                      85%     │
│  [█████████████████████████████████░░░░░░░░░░░]          │
│  Resets in 5d 18h                                         │
│                                                           │
│  TODAY'S USAGE ─────────────────────────────────────────  │
│  63.2M tokens                              ~$62.78        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Cache Rd │ │ Cache Wr │ │  Input   │ │  Output  │    │
│  │  48.1M   │ │   4.2M   │ │   8.9M   │ │   2.0M   │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                           │
│  ⚡ PEAK STATUS                                           │
│              OFF-PEAK                                     │
│         Peak starts in:                                   │
│            13:42:05                                       │
│                                                           │
│  EASTERN TIME (ET)                                        │
│  [░░░░░░░████████████░░░░░░░░░░░░░░░░░░░░░░░░░]          │
│  BRASÍLIA (BRT)                                           │
│  [░░░░░░░░████████████░░░░░░░░░░░░░░░░░░░░░░░]           │
│                                                           │
│  Updated just now                                     ↻   │
└──────────────────────────────────────────────────────────┘
```

### Tray Icon

A stylized **"R"** (RIAS) that changes color based on usage:
- Dark neutral — normal (< 70%)
- Amber — warning (70–90%)
- Red — critical (≥ 90%)

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

## Configuration

Settings are accessible in the **Config** tab inside the popup:

| Setting | Default | Description |
|---------|---------|-------------|
| Polling interval | 1 min | How often to check usage |
| Warning threshold | 70% | Shows amber notification |
| Critical threshold | 90% | Shows red notification |
| Notifications | On | Windows toast notifications |

Settings are saved to `%LOCALAPPDATA%\ClaudeUsageMonitor\settings.json`.

## How it works

1. **Auth** — reads the OAuth token from `~/.claude/.credentials.json` (managed by Claude Code)
2. **Polling** — calls the Anthropic usage API every minute with exponential backoff on errors
3. **Session scanning** — parses Claude Code JSONL session logs to extract token counts per model
4. **Persistence** — stores usage snapshots and session data in SQLite (90-day retention)
5. **Cost estimation** — applies per-model pricing (input/output/cache tokens) to calculate session costs
6. **Peak detection** — computes on/off-peak status against 8 AM–2 PM ET window with manual DST (no tzdata dependency)
7. **Notifications** — fires Windows toast alerts when usage crosses configurable thresholds

## Color Palette (RIAS)

| Element | Color |
|---------|-------|
| Background | `#0A0A0F` |
| Primary accent | `#DC143C` (Crimson) |
| Secondary accent | `#FF4500` (Ember) |
| Critical | `#FF2020` (Scarlet) |
| Warning | `#FFB020` (Amber) |
| Active indicator | `#F0F0F5` (White) |
| Text | `#F0F0F5` |

## Global Hotkey

The app registers the best available combo to toggle the popup. Priority order:

1. Ctrl+Shift+C
2. Ctrl+Shift+M *(recommended when Claude Code is open)*
3. Ctrl+Alt+M
4. Ctrl+Shift+U
5. Ctrl+Alt+U
6. Ctrl+Alt+C

The registered hotkey is shown in the tray tooltip and in `%LOCALAPPDATA%\ClaudeUsageMonitor\monitor.log`.

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
│   ├── popup_window.py   # Main tabbed popup (560px, 4 tabs, fade-in)
│   ├── tab_bar.py        # Custom tab bar with CRIMSON underline indicator
│   ├── data_cards.py     # Metric summary cards
│   ├── trend_chart.py    # Dual-line trend chart (CRIMSON_LIGHT + EMBER)
│   ├── session_list.py   # Session list with expand/collapse and token detail
│   ├── peak_monitor.py   # Peak hours widget (countdown, ET/BRT bars, tz cards)
│   ├── settings_tab.py   # Inline config tab
│   └── styles.py         # RIAS color palette and global QSS
├── requirements.txt
└── build.bat
```

## License

MIT
