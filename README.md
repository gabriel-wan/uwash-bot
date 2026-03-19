# UWash - Real-time Laundry Intelligence

> Automated laundry tracking system for UTown Residences using IoT sensors, cloud backend, and multi-platform notifications.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Bot Framework | python-telegram-bot 22.x |
| API Framework | Flask + Flask-CORS |
| Database | SQLite3 |
| Hosting | Railway |

## Architecture

```
┌─────────────────┐     HTTPS POST      ┌─────────────────────────────────┐
│   ESP32 + SW-420│ ──────────────────► │         Railway Backend         │
│ (Vibration Sensor)                    │  ┌─────────────────────────────┐│
└─────────────────┘                     │  │  Flask API (:8080)          ││
                                        │  │  - POST /machine/update     ││
┌─────────────────┐     GET /api/status │  │  - GET  /api/{house}/status ││
│  React Dashboard│ ◄────────────────── │  │  - POST /api/start-cycle    ││
│    (Vercel)     │                     │  └──────────┬──────────────────┘│
└─────────────────┘                     │             │                   │
                                        │             ▼                   │
┌─────────────────┐     Telegram API    │  ┌─────────────────────────────┐│
│  Telegram Bot   │ ◄────────────────── │  │  SQLite Database            ││
│   (Polling)     │                     │  │  - Timers, Alarms, Prefs    ││
└─────────────────┘                     │  └─────────────────────────────┘│
                                        └─────────────────────────────────┘
```

## Features

- **Hardware Integration**: ESP32 sensors detect machine vibration and report status
- **Real-time Dashboard**: Web app shows live machine availability
- **Telegram Bot**: Start timers, check status, get notifications when laundry is done
- **Multi-House Support**: Supports multiple residences (Garuda, Phoenix, Tulpar, Quilin, ROC)
- **Alarm System**: Automatic notifications when timer expires

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/{house}/status` | GET | Dashboard status for a house |
| `/api/start-cycle` | POST | Start a machine cycle from dashboard |
| `/machine/update` | POST | Hardware sensor status update (requires `X-API-Key`) |
| `/status` | GET | Legacy bot status endpoint |

## Local Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/gabriel-wan/uwash-bot
   cd uwash-bot
   ```

2. **Create `.env` file**
   ```env
   TELEGRAM_BOT_API_KEY=your_bot_token
   SENSOR_API_KEY=your_hardware_api_key
   TIMER_DURATION_MINUTES=34
   CONVO_TIMEOUT_SECONDS=300
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run**
   ```bash
   python src/main.py
   ```

## Railway Deployment

1. Connect GitHub repo to Railway
2. Set environment variables:
   - `TELEGRAM_BOT_API_KEY`
   - `SENSOR_API_KEY`
   - `PORT` (Railway sets automatically)
3. Add a Volume mounted at `/app/data` for SQLite persistence
4. Deploy - Railway auto-deploys on push

## Hardware Setup (ESP32)

Configure the ESP32 with:
```cpp
const char* SERVER_URL = "https://your-railway-url.up.railway.app/machine/update";
const char* API_KEY = "your_sensor_api_key";
const char* HOUSE = "ROC";
const char* MACHINE_NAME = "Washer One";
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Display help and welcome message |
| `/select` | Start a laundry timer |
| `/status` | Check machine availability |

## Team

Built for NUS UTown Student Life Hackathon 2026

## License

MIT
