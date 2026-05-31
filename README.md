# Desktop Overlay

A translucent always-on-top system monitoring overlay widget built with PySide6.

## Features

- Real-time clock and date display
- CPU usage (percentage + progress bar)
- RAM usage (percentage + progress bar)
- Custom quote/text display (configurable via tray menu)
- Draggable and resizable window (position/size persisted)
- System tray integration with toggle/quicksettings

## Requirements

- Python 3.10+
- PySide6 >= 6.5.0
- psutil >= 5.9.0

## Usage

```bash
pip install -r requirements.txt
python main.py
```

Right-click the tray icon to toggle visibility, reload config, or check for updates.

## Update Mechanism

Built-in self-update via GitHub. Right-click tray icon → **Check for Updates** to pull the latest version from the `ai` branch.
