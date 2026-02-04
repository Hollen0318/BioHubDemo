# BioHubDemo (OptiLact Dashboard)

A small Flask + Socket.IO web dashboard that connects to a serial device (e.g., an Arduino-based optical sensor), streams live readings to the browser, and supports:
- Live visualization of incoming sensor data
- Manual recording sessions saved to disk
- Two “prediction” workflows (lactate + skin tone) that capture a 60-second window and return **placeholder** results (intended to be replaced by real ML inference)

The app runs locally and serves a single-page dashboard from `templates/index.html`.

---

## What’s in this repo

- `main.py` — Flask server, serial connection + streaming, recording, prediction workflows
- `templates/index.html` — dashboard UI (Bootstrap + Chart.js + Socket.IO client)
- `static/` — images/assets used by the UI
- `requirements.txt` — Python dependencies
- `test.py` — UI test harness that emits dummy data (no serial device required)

---

## Requirements

- Python 3.9+ recommended
- A serial device that outputs lines matching the expected format (see below)
- macOS/Linux/Windows supported (serial port names differ)

Python packages (from `requirements.txt`):
- Flask
- flask-socketio
- pyserial
- eventlet *(optional, depending on async mode; current code uses threading mode)*

---

## Install

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
