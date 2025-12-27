#!/usr/bin/env python3
"""
🚨 BTCP System Monitor - Telegram Live Alerts
==============================================
Monitora tutti i server BTCP e invia alert su Telegram quando qualcosa va giù.
"""

import asyncio
import aiohttp
import socket
import subprocess
import platform
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from dotenv import load_dotenv

# Carica variabili da .env
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAZIONE
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    # 🤖 Telegram Bot (da .env)
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),

    # ⏱️ Timing
    "CHECK_INTERVAL": int(os.getenv("CHECK_INTERVAL", 30)),
    "RETRY_INTERVAL": int(os.getenv("RETRY_INTERVAL", 10)),
    "TIMEOUT": int(os.getenv("TIMEOUT", 10)),

    # 📊 Alert
    "ALERT_ON_RECOVERY": True,      # Notifica quando torna online
    "CONSECUTIVE_FAILURES": 2,      # Alert dopo 2 fallimenti consecutivi
    "LOG_FILE": "btcp_monitor.log",

    # 🔄 GitHub Actions mode (single run)
    "RUN_ONCE": os.getenv("RUN_ONCE", "false").lower() == "true",
}

# ═══════════════════════════════════════════════════════════════════════════════
# SERVER BTCP DA MONITORARE
# ═══════════════════════════════════════════════════════════════════════════════

# 🖥️ Server (ping)
SERVERS = [
    {"name": "BTCPayServer PROD", "host": "51.75.90.145"},
    {"name": "Bitmoon API PROD", "host": "54.36.114.17"},
    {"name": "BTCPayServer STAGING", "host": "54.36.119.150"},
    {"name": "Bitmoon API STAGING", "host": "57.129.91.206"},
    {"name": "ARES (Bitcoin Core)", "host": "188.12.149.216"},
    {"name": "CRATOS", "host": "btcppl.mywire.org"},
]

# 🌐 Servizi Web (HTTP/HTTPS)
WEBSITES = [
    # BitcoinPeople
    {"name": "BitcoinPeople Main", "url": "https://bitcoinpeople.it", "expected_status": 200},
    {"name": "BitcoinPeople Pay", "url": "https://pay.bitcoinpeople.it", "expected_status": 200},
    {"name": "BPay", "url": "https://bpay.bitcoinpeople.it", "expected_status": 200},
    {"name": "Bagheera", "url": "https://bagheera.bitcoinpeople.it", "expected_status": 200},

    # Bitmoon
    {"name": "Bitmoon Main", "url": "https://bitmoon.it", "expected_status": 200},

    # Direct IP checks (backup)
    {"name": "BTCPay PROD (IP)", "url": "https://51.75.90.145", "expected_status": 200},
    {"name": "Bitmoon API PROD (IP)", "url": "https://54.36.114.17", "expected_status": 200},
]

# 🔌 Porte TCP da controllare
SERVICES = [
    # BTCPayServer PROD
    {"name": "BTCPay PROD SSH", "host": "51.75.90.145", "port": 22},
    {"name": "BTCPay PROD HTTPS", "host": "51.75.90.145", "port": 443},

    # Bitmoon API PROD
    {"name": "Bitmoon PROD SSH", "host": "54.36.114.17", "port": 22},
    {"name": "Bitmoon PROD HTTPS", "host": "54.36.114.17", "port": 443},

    # BTCPayServer STAGING
    {"name": "BTCPay STAGING SSH", "host": "54.36.119.150", "port": 22},
    {"name": "BTCPay STAGING HTTPS", "host": "54.36.119.150", "port": 443},

    # Bitmoon API STAGING
    {"name": "Bitmoon STAGING SSH", "host": "57.129.91.206", "port": 22},
    {"name": "Bitmoon STAGING HTTPS", "host": "57.129.91.206", "port": 443},

    # ARES - Bitcoin Core
    {"name": "ARES SSH", "host": "188.12.149.216", "port": 22},
    {"name": "ARES Bitcoin RPC", "host": "188.12.149.216", "port": 8332},

    # CRATOS
    {"name": "CRATOS SSH", "host": "btcppl.mywire.org", "port": 22},
]

# 🐳 Container Docker (opzionale - decommenta se usi Docker)
DOCKER_CONTAINERS = [
    # {"name": "btcpayserver"},
    # {"name": "postgres"},
    # {"name": "nbxplorer"},
]

# ⚙️ Servizi Systemd (opzionale)
SYSTEMD_SERVICES = [
    # {"name": "docker"},
    # {"name": "nginx"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# CODICE DEL MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

class Status(Enum):
    UP = "🟢"
    DOWN = "🔴"
    UNKNOWN = "🟡"

@dataclass
class Target:
    name: str
    type: str
    status: Status = Status.UNKNOWN
    last_check: Optional[datetime] = None
    last_status_change: Optional[datetime] = None
    consecutive_failures: int = 0
    response_time: float = 0.0
    error_message: str = ""
    config: dict = field(default_factory=dict)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(CONFIG["LOG_FILE"]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("📤 Telegram: Messaggio inviato")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"❌ Telegram error: {error}")
                        return False
        except Exception as e:
            logger.error(f"❌ Telegram exception: {e}")
            return False

    async def send_alert(self, target: Target, is_down: bool):
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if is_down:
            header = "🚨 <b>ALERT: SERVIZIO DOWN</b> 🚨"
            emoji = "🔴"
            status_text = "DOWN"
        else:
            header = "✅ <b>SERVIZIO RIPRISTINATO</b> ✅"
            emoji = "✅"
            status_text = "RECOVERED"

        message = f"""
{header}

{emoji} <b>{target.name}</b>
📋 Tipo: <code>{target.type}</code>
📊 Status: <b>{status_text}</b>
🕐 Ora: <code>{now}</code>
"""
        if target.error_message and is_down:
            message += f"❗ Errore: <code>{target.error_message}</code>\n"

        if target.response_time > 0 and not is_down:
            message += f"⚡ Response: <code>{target.response_time:.2f}ms</code>\n"

        if target.last_status_change and not is_down:
            duration = datetime.now() - target.last_status_change
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            message += f"⏱️ Downtime: <code>{hours}h {minutes}m {seconds}s</code>\n"

        await self.send_message(message)

    async def send_status_report(self, targets: list):
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        up_count = sum(1 for t in targets if t.status == Status.UP)
        down_count = sum(1 for t in targets if t.status == Status.DOWN)

        message = f"""
📊 <b>BTCP STATUS REPORT</b>
🕐 <code>{now}</code>

✅ Online: <b>{up_count}</b>
🔴 Offline: <b>{down_count}</b>
━━━━━━━━━━━━━━━━━━━━
"""
        # Prima i DOWN, poi gli UP
        for target in sorted(targets, key=lambda x: (x.status != Status.DOWN, x.name)):
            status_emoji = target.status.value
            if target.status == Status.DOWN and target.error_message:
                message += f"{status_emoji} {target.name}\n   ❗ <code>{target.error_message}</code>\n"
            else:
                message += f"{status_emoji} {target.name}\n"

        await self.send_message(message)


class SystemMonitor:
    def __init__(self):
        self.notifier = TelegramNotifier(
            CONFIG["TELEGRAM_BOT_TOKEN"],
            CONFIG["TELEGRAM_CHAT_ID"]
        )
        self.targets: list[Target] = []
        self._init_targets()

    def _init_targets(self):
        for srv in SERVERS:
            self.targets.append(Target(
                name=srv["name"],
                type="Server (Ping)",
                config={"host": srv["host"]}
            ))

        for svc in SERVICES:
            self.targets.append(Target(
                name=svc["name"],
                type=f"TCP:{svc['port']}",
                config={"host": svc["host"], "port": svc["port"]}
            ))

        for site in WEBSITES:
            self.targets.append(Target(
                name=site["name"],
                type="HTTP/HTTPS",
                config={"url": site["url"], "expected_status": site.get("expected_status", 200)}
            ))

        for container in DOCKER_CONTAINERS:
            self.targets.append(Target(
                name=container["name"],
                type="Docker",
                config={"container": container["name"]}
            ))

        for service in SYSTEMD_SERVICES:
            self.targets.append(Target(
                name=service["name"],
                type="Systemd",
                config={"service": service["name"]}
            ))

        logger.info(f"📋 Inizializzati {len(self.targets)} target da monitorare")

    async def check_ping(self, host: str) -> tuple[bool, float, str]:
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            start = datetime.now()

            result = await asyncio.create_subprocess_exec(
                'ping', param, '1', '-W', '5', host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(result.wait(), timeout=CONFIG["TIMEOUT"])

            elapsed = (datetime.now() - start).total_seconds() * 1000

            if result.returncode == 0:
                return True, elapsed, ""
            return False, 0, "Host unreachable"
        except asyncio.TimeoutError:
            return False, 0, "Ping timeout"
        except Exception as e:
            return False, 0, str(e)

    async def check_tcp_port(self, host: str, port: int) -> tuple[bool, float, str]:
        try:
            start = datetime.now()
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=CONFIG["TIMEOUT"])
            elapsed = (datetime.now() - start).total_seconds() * 1000
            writer.close()
            await writer.wait_closed()
            return True, elapsed, ""
        except asyncio.TimeoutError:
            return False, 0, f"Timeout porta {port}"
        except ConnectionRefusedError:
            return False, 0, f"Connessione rifiutata porta {port}"
        except Exception as e:
            return False, 0, str(e)

    async def check_http(self, url: str, expected_status: int = 200) -> tuple[bool, float, str]:
        try:
            start = datetime.now()
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=CONFIG["TIMEOUT"])) as resp:
                    elapsed = (datetime.now() - start).total_seconds() * 1000
                    if resp.status == expected_status:
                        return True, elapsed, ""
                    return False, elapsed, f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            return False, 0, "HTTP timeout"
        except aiohttp.ClientError as e:
            return False, 0, f"HTTP error: {type(e).__name__}"
        except Exception as e:
            return False, 0, str(e)

    async def check_docker(self, container: str) -> tuple[bool, float, str]:
        try:
            start = datetime.now()
            result = await asyncio.create_subprocess_exec(
                'docker', 'inspect', '-f', '{{.State.Running}}', container,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=CONFIG["TIMEOUT"])
            elapsed = (datetime.now() - start).total_seconds() * 1000

            if result.returncode == 0 and b'true' in stdout.lower():
                return True, elapsed, ""
            return False, 0, "Container non running"
        except Exception as e:
            return False, 0, str(e)

    async def check_systemd(self, service: str) -> tuple[bool, float, str]:
        try:
            start = datetime.now()
            result = await asyncio.create_subprocess_exec(
                'systemctl', 'is-active', service,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=CONFIG["TIMEOUT"])
            elapsed = (datetime.now() - start).total_seconds() * 1000

            if result.returncode == 0:
                return True, elapsed, ""
            return False, 0, f"Status: {stdout.decode().strip()}"
        except Exception as e:
            return False, 0, str(e)

    async def check_target(self, target: Target):
        is_up = False
        response_time = 0.0
        error_msg = ""

        if "Ping" in target.type:
            is_up, response_time, error_msg = await self.check_ping(target.config["host"])
        elif "TCP" in target.type:
            is_up, response_time, error_msg = await self.check_tcp_port(
                target.config["host"], target.config["port"]
            )
        elif "HTTP" in target.type:
            is_up, response_time, error_msg = await self.check_http(
                target.config["url"], target.config.get("expected_status", 200)
            )
        elif "Docker" in target.type:
            is_up, response_time, error_msg = await self.check_docker(target.config["container"])
        elif "Systemd" in target.type:
            is_up, response_time, error_msg = await self.check_systemd(target.config["service"])

        target.last_check = datetime.now()
        target.response_time = response_time
        target.error_message = error_msg

        previous_status = target.status

        if is_up:
            target.consecutive_failures = 0
            if previous_status == Status.DOWN:
                target.status = Status.UP
                target.last_status_change = datetime.now()
                logger.info(f"✅ {target.name} RECOVERED ({response_time:.2f}ms)")
                if CONFIG["ALERT_ON_RECOVERY"]:
                    await self.notifier.send_alert(target, is_down=False)
            else:
                target.status = Status.UP
        else:
            target.consecutive_failures += 1
            if target.consecutive_failures >= CONFIG["CONSECUTIVE_FAILURES"]:
                if previous_status != Status.DOWN:
                    target.status = Status.DOWN
                    target.last_status_change = datetime.now()
                    logger.error(f"🔴 {target.name} DOWN: {error_msg}")
                    await self.notifier.send_alert(target, is_down=True)

    async def run_checks(self):
        tasks = [self.check_target(target) for target in self.targets]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self):
        logger.info("=" * 60)
        logger.info("🚀 BTCP MONITOR STARTED")
        logger.info("=" * 60)

        # GitHub Actions mode: run once and exit
        if CONFIG["RUN_ONCE"]:
            logger.info("🔄 Running in single-check mode (GitHub Actions)")
            await self.run_checks()

            # Report only if there are DOWN services
            down_services = [t for t in self.targets if t.status == Status.DOWN]
            if down_services:
                await self.notifier.send_status_report(self.targets)

            logger.info("✅ Single check completed")
            return

        # Normal mode: continuous monitoring
        await self.notifier.send_message(
            "🚀 <b>BTCP Monitor Avviato</b>\n\n"
            f"📋 Target monitorati: <b>{len(self.targets)}</b>\n"
            f"⏱️ Intervallo: <b>{CONFIG['CHECK_INTERVAL']}s</b>\n\n"
            "Scrivi /status per vedere lo stato di tutti i servizi"
        )

        while True:
            try:
                await self.run_checks()
                await asyncio.sleep(CONFIG["CHECK_INTERVAL"])
            except KeyboardInterrupt:
                logger.info("⏹️ Monitor fermato")
                break
            except Exception as e:
                logger.error(f"❌ Errore: {e}")
                await asyncio.sleep(CONFIG["RETRY_INTERVAL"])


class TelegramCommandHandler:
    def __init__(self, monitor: SystemMonitor):
        self.monitor = monitor
        self.notifier = monitor.notifier
        self.last_update_id = 0

    async def get_updates(self):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.notifier.base_url}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 10}
                async with session.get(url, params=params, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", [])
        except:
            pass
        return []

    async def handle_command(self, text: str):
        text = text.lower().strip()

        if text in ["/status", "/stato", "status", "stato"]:
            await self.notifier.send_status_report(self.monitor.targets)
        elif text in ["/help", "/aiuto", "help"]:
            await self.notifier.send_message(
                "🤖 <b>Comandi</b>\n\n"
                "/status - Stato di tutti i servizi\n"
                "/help - Questo messaggio\n\n"
                "Riceverai alert automatici quando un servizio va DOWN o torna UP"
            )

    async def listen(self):
        while True:
            try:
                updates = await self.get_updates()
                for update in updates:
                    self.last_update_id = update["update_id"]
                    if "message" in update:
                        message = update["message"]
                        chat_id = str(message["chat"]["id"])
                        text = message.get("text", "")
                        if chat_id == CONFIG["TELEGRAM_CHAT_ID"]:
                            await self.handle_command(text)
                await asyncio.sleep(1)
            except:
                await asyncio.sleep(5)


async def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║            🚨 BTCP SYSTEM MONITOR 🚨                          ║
║         Alert live su Telegram quando qualcosa va giù         ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    monitor = SystemMonitor()

    # GitHub Actions mode: just run checks once
    if CONFIG["RUN_ONCE"]:
        await monitor.start()
        return

    # Normal mode: run monitor + command handler
    command_handler = TelegramCommandHandler(monitor)
    await asyncio.gather(
        monitor.start(),
        command_handler.listen()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Monitor terminato")
