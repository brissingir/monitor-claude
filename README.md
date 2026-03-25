# Monitor Claude

Windows system tray app that monitors your Claude API usage in real-time.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.8-green)
![Windows](https://img.shields.io/badge/Windows-11-0078D6)

## What it does

Sits in your system tray and shows your Claude usage at a glance:

- **5-Hour Session** utilization (Crimson bar)
- **7-Day** utilization (Royal Blue bar)
- Reset countdowns for each window
- Notifications when usage crosses warning/critical thresholds
- Auto-starts with Windows

## Screenshots

### System Tray Icon
A stylized **"C"** in Crimson with a Royal Blue accent — always visible in the taskbar.

### Popup Window
Click the tray icon to see the full dashboard:

```
┌──────────────────────────────────────────┐
│  Claude Usage                      ⚙  ✕  │
├──────────────────────────────────────────┤
│                                          │
│  5-Hour Session                    17%   │
│  [█████░░░░░░░░░░░░░░░░░░░░░░░░░]       │
│  Resets in 3h 42m                        │
│                                          │
│  7-Day Usage                       42%   │
│  [██████████████░░░░░░░░░░░░░░░░]       │
│  Resets in 5d 18h                        │
│                                          │
│  ─────────────────────────────────────── │
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

This creates a shortcut in `shell:startup` that launches the monitor on login.

## Configuration

Right-click the tray icon → **Settings**, or click the ⚙ button in the popup:

| Setting | Default | Description |
|---------|---------|-------------|
| Polling interval | 5 min | How often to check usage |
| Warning threshold | 70% | Shows orange notification |
| Critical threshold | 90% | Shows red notification |
| Notifications | On | Windows toast notifications |

Settings are saved to `%LOCALAPPDATA%\ClaudeUsageMonitor\settings.json`.

## How it works

1. Reads the OAuth token from `~/.claude/.credentials.json` (managed by Claude Code)
2. Polls `https://api.anthropic.com/api/oauth/usage` every 5 minutes
3. Displays results in a dark-themed popup with animated progress bars
4. Backs off automatically on rate limits (429) or network errors

## Color Palette

| Element | Color |
|---------|-------|
| Background | `#000000` |
| 5-Hour bar | `#B90E0A` (Crimson) |
| 7-Day bar | `#5B6FE8` (Royal Blue) |
| Text | `#FFFFFF` |

## Build executable

```bash
pip install pyinstaller
build.bat
```

Outputs `dist/ClaudeUsageMonitor.exe` — a single portable file.

## Project Structure

```
monitor-claude/
├── main.py              # Entry point, single-instance check
├── app.py               # System tray, popup, notifications
├── api_client.py        # HTTP client for usage API
├── auth.py              # OAuth token reader
├── polling_service.py   # Timer-based polling with backoff
├── models.py            # Data classes
├── config.py            # Settings persistence
├── autostart.py         # Windows startup shortcut manager
├── ui/
│   ├── popup_window.py  # Dark popup with usage bars
│   ├── settings_dialog.py
│   └── styles.py        # Colors and QSS
├── requirements.txt
└── build.bat
```

## License

MIT
