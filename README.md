# BTCP System Monitor

A Python-based monitoring tool that sends real-time Telegram alerts when your BTCP infrastructure goes down or recovers.

## Features

- **Server Ping** - Monitor server reachability
- **TCP Ports** - Check specific ports (SSH, HTTPS, Bitcoin RPC, etc.)
- **HTTP/HTTPS** - Monitor web endpoints and APIs
- **Docker Containers** - Track container status (optional)
- **Systemd Services** - Monitor system services (optional)
- **Telegram Alerts** - Instant notifications for DOWN/RECOVERY events
- **Telegram Commands** - `/status` and `/help` via bot

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example and add your Telegram credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Run the Monitor

```bash
python monitor.py
```

## Getting Telegram Credentials

### Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the token provided (format: `123456789:ABCdefGHI...`)

### Chat ID

1. Start a chat with your new bot
2. Send any message to it
3. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find `"chat":{"id":123456789}` - that's your Chat ID

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | - | Your Telegram bot token (required) |
| `TELEGRAM_CHAT_ID` | - | Your Telegram chat ID (required) |
| `CHECK_INTERVAL` | 30 | Seconds between checks |
| `RETRY_INTERVAL` | 10 | Seconds to wait after errors |
| `TIMEOUT` | 10 | Connection timeout in seconds |

## Monitored Targets

Edit `monitor.py` to customize:

```python
# Servers (ping)
SERVERS = [
    {"name": "My Server", "host": "192.168.1.1"},
]

# TCP Ports
SERVICES = [
    {"name": "SSH", "host": "192.168.1.1", "port": 22},
]

# Web endpoints
WEBSITES = [
    {"name": "API", "url": "https://api.example.com", "expected_status": 200},
]
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Show status of all monitored services |
| `/help` | Show available commands |

## Alert Examples

**Down Alert:**
```
🚨 ALERT: SERVIZIO DOWN 🚨

🔴 BTCPayServer PROD
📋 Tipo: Server (Ping)
📊 Status: DOWN
🕐 Ora: 27/12/2024 15:30:00
❗ Errore: Host unreachable
```

**Recovery Alert:**
```
✅ SERVIZIO RIPRISTINATO ✅

✅ BTCPayServer PROD
📋 Tipo: Server (Ping)
📊 Status: RECOVERED
🕐 Ora: 27/12/2024 15:35:00
⚡ Response: 12.34ms
⏱️ Downtime: 0h 5m 0s
```

## Running as a Service

Create a systemd service for persistent monitoring:

```bash
sudo nano /etc/systemd/system/btcp-monitor.service
```

```ini
[Unit]
Description=BTCP System Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/btcp-monitor
ExecStart=/usr/bin/python3 monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable btcp-monitor
sudo systemctl start btcp-monitor
```

## License

MIT
